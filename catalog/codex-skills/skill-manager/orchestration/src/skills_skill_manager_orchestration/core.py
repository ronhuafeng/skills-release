from __future__ import annotations

import hashlib
import json
import os
import stat
import tomllib
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any

from skills_frontmatter import (
    duplicates,
    scan_skill_dir,
    scan_source_roots,
)
from skills_profile_toml import (
    load_profile,
    normalize_profile,
    profile_source_roots,
    profile_sources,
    render_profile,
    repo_profiles,
    repo_vendors,
)
from skills_snapshot_mutation import apply_plan as apply_snapshot_plan
from skills_snapshot_plan import (
    SnapshotAction,
    SnapshotPlan,
    SnapshotRecord,
    tree_digest,
)
from skills_snapshot_plan import (
    plan_directory as plan_snapshot_directory,
)
from skills_symlink_mutation import apply_plan as apply_link_plan
from skills_symlink_plan import (
    LinkAction,
    LinkPlan,
)
from skills_symlink_plan import (
    plan_directory as plan_link_directory,
)

from .enrollment import AcceptedFleetRevision
from .fleet_observe import normalize_git_remote, run_git
from .source_policy import (
    inspect_link_source,
    validate_link_source,
    validate_snapshot_source,
)

PLAN_VERSION = 3
VENDOR_PLAN_VERSION = 2


class IncompleteEvidence(Exception):
    pass


class BlockedOperation(Exception):
    pass


@dataclass(frozen=True)
class _ValidatedSyncPlan:
    payload: dict[str, Any]
    registry_items: list[dict[str, Any]]
    plans: list[LinkPlan]
    sources: dict[str, Path]
    reusable: dict[str, Path]


def fingerprint(path: Path) -> str:
    return hashlib.sha256(str(path.expanduser().resolve()).encode()).hexdigest()[:12]


def _lexical_absolute(path: Path | str, label: str) -> Path:
    expanded = Path(path).expanduser()
    if not expanded.is_absolute():
        raise ValueError(f"{label} must be an absolute path")
    return Path(os.path.normpath(str(expanded)))


def _public_scope(scope: str) -> dict[str, str]:
    if scope == "global":
        return {"kind": "global", "name": "global"}
    repo = _lexical_absolute(scope, "registry scope")
    return {"kind": "repo", "name": repo.name, "fingerprint": fingerprint(repo)}


def _validate_registry_directory(scope: str, directory: Path) -> None:
    if scope == "global":
        expected = _lexical_absolute(Path.home() / ".agents" / "skills", "registry")
        if directory != expected:
            raise ValueError(f"global registry must be {expected}")
    else:
        repo = _lexical_absolute(scope, "repository")
        expected = _lexical_absolute(repo / ".agents" / "skills", "registry")
        if directory != expected:
            raise ValueError(f"repo registry must be {expected}")
    if expected.parent.is_symlink() or expected.is_symlink():
        raise ValueError("registry path must not traverse a symlink")


def _validate_authority_profile(
    profile: dict[str, Any],
    profile_path: Path | None,
    authority: AcceptedFleetRevision,
) -> None:
    if render_profile(profile) != authority.profile_toml:
        raise ValueError("profile does not match accepted Fleet revision")
    if authority.profile_path is None:
        if profile_path is not None:
            raise ValueError("profile-free Fleet apply must not select a profile path")
        return
    if profile_path is None:
        raise ValueError("accepted Fleet revision requires its profile path")
    accepted_path = _lexical_absolute(authority.profile_path, "accepted profile")
    if _lexical_absolute(profile_path, "profile") != accepted_path:
        raise ValueError("profile path does not match accepted Fleet revision")


def _plan_profile_path(
    request: dict[str, Any],
    authority: AcceptedFleetRevision | None,
) -> Path | None:
    raw = request.get("profile_path")
    if raw is None:
        if authority is None:
            raise KeyError("profile_path")
        if authority.profile_path is not None:
            raise ValueError("profile_path is required outside profile-free Fleet apply")
        return None
    return _lexical_absolute(raw, "profile")


def _validate_authoritative_sources(
    sources: dict[str, Path],
    authority: AcceptedFleetRevision,
) -> None:
    if set(sources) != set(authority.source_revisions) or set(sources) != set(
        authority.source_tree_oids
    ):
        raise ValueError("sources do not match accepted Fleet revision")
    for alias, source in sorted(sources.items()):
        root = Path(run_git(source, "rev-parse", "--show-toplevel")).resolve()
        if run_git(root, "rev-parse", "HEAD") != authority.source_revisions[alias]:
            raise ValueError(f"source {alias} is not at its accepted revision")
        if run_git(
            root,
            "status",
            "--ignored",
            "--porcelain",
            "--untracked-files=all",
        ):
            raise ValueError(f"source {alias} checkout is not clean")
        try:
            relative = source.resolve().relative_to(root).as_posix()
        except ValueError as exc:
            raise ValueError(f"source {alias} is outside its checkout") from exc
        observed_tree = run_git(root, "rev-parse", f"HEAD:{relative}")
        if observed_tree != authority.source_tree_oids[alias]:
            raise ValueError(f"source {alias} tree differs from accepted revision")


def _validate_authoritative_repo(
    repo: Path,
    authority: AcceptedFleetRevision,
) -> None:
    repo_key = str(_lexical_absolute(repo, "repository"))
    expected_origin = authority.repo_origins.get(repo_key)
    if expected_origin is None:
        raise ValueError("repository is outside accepted Fleet authority")
    resolved = repo.resolve()
    observed_root = Path(run_git(repo, "rev-parse", "--show-toplevel")).resolve()
    if observed_root != resolved:
        raise ValueError("repository path is not its Git worktree root")
    observed_origin = normalize_git_remote(
        run_git(repo, "config", "--get", "remote.origin.url")
    )
    if observed_origin != expected_origin:
        raise ValueError("repository origin differs from accepted Fleet revision")


def _desired_for_scope(profile: dict[str, Any], scope: str) -> set[str]:
    if scope == "global":
        return set(profile.get("global", {}).get("include", []))
    repo = str(Path(scope).expanduser().resolve())
    repos = profile.get("repos", {})
    if not isinstance(repos, dict):
        return set()
    table = repos.get(repo, {})
    if not isinstance(table, dict):
        return set()
    return {
        str(name)
        for name in list(table.get("include", [])) + list(table.get("vendor", []))
    }


def _link_desired_for_scope(profile: dict[str, Any], scope: str) -> list[str]:
    if scope == "global":
        return [str(name) for name in profile.get("global", {}).get("include", [])]
    repo = str(Path(scope).expanduser().resolve())
    repos = profile.get("repos", {})
    if not isinstance(repos, dict):
        return []
    table = repos.get(repo, {})
    if not isinstance(table, dict):
        return []
    return [str(name) for name in table.get("include", [])]


def inspect_registry(
    profile_path: Path,
    registries: list[tuple[str, Path]],
    source_roots: list[Path],
) -> dict[str, Any]:
    if not profile_path.is_file():
        raise IncompleteEvidence("profile is missing")
    profile = normalize_profile(load_profile(profile_path))
    sources = scan_source_roots(source_roots)
    duplicate_aliases = duplicates(sources, "alias")
    duplicate_names = duplicates(sources, "frontmatter_name")
    profile_source_map = profile_sources(profile)
    profile_roots = profile_source_roots(profile)
    repos = repo_profiles(profile)
    vendors = repo_vendors(profile)
    registry_snapshots = []
    total_entries = 0
    for scope, directory in registries:
        public_scope = _public_scope(scope)
        directory = directory.expanduser().resolve(strict=False)
        _validate_registry_directory(scope, directory)
        entries = scan_skill_dir(directory)
        entry_qualifications = {
            entry.name: inspect_link_source(directory / entry.name)
            for entry in entries
        }
        total_entries += len(entries)
        desired = _desired_for_scope(profile, scope)
        vendor_state = {"version": 1, "snapshots": {}}
        vendor_lock: dict[str, Any] | None = None
        if scope != "global":
            state_path = (
                Path(scope).expanduser().resolve()
                / ".agents"
                / "skill-manager"
                / "vendor-lock.json"
            )
            vendor_state, vendor_lock = _inspect_vendor_state(state_path)
        managed_names = set(vendor_state["snapshots"])
        exposed = {entry.name for entry in entries if entry.has_skill}
        anomalies = {
            entry.name
            for entry in entries
            if not entry.exists
            or not entry.has_skill
            or entry.kind not in {"symlink", "directory"}
            or entry_qualifications[entry.name].errors
        }
        managed_status: dict[str, str] = {}
        for entry in entries:
            if entry.name not in managed_names:
                continue
            record = vendor_state["snapshots"].get(entry.name, {})
            if vendor_lock is not None and not vendor_lock["valid"]:
                status = "invalid-vendor-lock"
            elif entry.kind != "directory":
                status = "path-form-changed"
            else:
                try:
                    provenance = SnapshotRecord.from_raw(entry.name, record)
                    current_digest = tree_digest(directory / entry.name)
                except ValueError:
                    status = "invalid-provenance-or-content"
                else:
                    status = (
                        "current"
                        if current_digest == provenance.target_digest
                        else "drifted"
                    )
            managed_status[entry.name] = status
            if status != "current":
                anomalies.add(entry.name)
        missing_managed = managed_names - {entry.name for entry in entries}
        anomalies.update(missing_managed)
        managed_status.update({name: "missing" for name in missing_managed})
        registry_snapshots.append(
            {
                "scope": public_scope,
                "directory": {
                    "name": directory.name,
                    "fingerprint": fingerprint(directory),
                },
                "entries": [
                    {
                        "name": entry.name,
                        "kind": entry.kind,
                        "exists": entry.exists,
                        "has_skill": entry.has_skill,
                        "frontmatter_name": entry.frontmatter_name,
                        "openai_yaml_present": entry_qualifications[
                            entry.name
                        ].openai_metadata.present,
                        "allow_implicit_invocation": entry_qualifications[
                            entry.name
                        ].openai_metadata.allow_implicit_invocation,
                        "metadata_errors": list(
                            entry_qualifications[entry.name].errors
                        ),
                        "target_fingerprint": fingerprint(Path(entry.target))
                        if entry.target
                        else None,
                        "managed_snapshot": managed_status.get(entry.name) == "current",
                        "managed_snapshot_status": managed_status.get(entry.name),
                    }
                    for entry in entries
                ],
                "coverage": {
                    "desired": sorted(desired),
                    "missing_desired": sorted(desired - exposed),
                    "exposed_outside_profile": sorted(exposed - desired),
                },
                "vendor_lock": vendor_lock,
                "anomalies": sorted(anomalies),
                "managed_snapshots": len(managed_names),
                "managed_snapshot_anomalies": sorted(
                    name
                    for name, status in managed_status.items()
                    if status != "current"
                ),
            }
        )
    profile_source_qualifications = {
        alias: inspect_link_source(path)
        for alias, path in profile_source_map.items()
    }
    return {
        "status": "success",
        "profile": {
            "name": profile_path.name,
            "fingerprint": fingerprint(profile_path),
        },
        "counts": {
            "entries": total_entries,
            "sources": len(sources),
            "registries": len(registries),
        },
        "registries": registry_snapshots,
        "profile_sources": [
            {
                "alias": alias,
                "name": path.name,
                "fingerprint": fingerprint(path),
                "exists": path.is_dir(),
                "has_skill": (path / "SKILL.md").is_file(),
                "openai_yaml_present": profile_source_qualifications[
                    alias
                ].openai_metadata.present,
                "allow_implicit_invocation": profile_source_qualifications[
                    alias
                ].openai_metadata.allow_implicit_invocation,
                "metadata_errors": list(
                    profile_source_qualifications[alias].errors
                ),
            }
            for alias, path in sorted(profile_source_map.items())
        ],
        "profile_source_roots": [
            {
                "name": path.name,
                "fingerprint": fingerprint(path),
                "exists": path.is_dir(),
            }
            for path in profile_roots
        ],
        "repo_profiles": [
            {
                "repo": Path(repo).name,
                "fingerprint": fingerprint(Path(repo)),
                "include": sorted(names),
                "vendor": sorted(vendors.get(repo, [])),
            }
            for repo, names in sorted(repos.items())
        ],
        "duplicate_aliases": {
            name: len(paths) for name, paths in duplicate_aliases.items()
        },
        "duplicate_names": {
            name: len(paths) for name, paths in duplicate_names.items()
        },
        "profile_sections": sorted(profile),
    }


def _canonical_payload(value: dict[str, Any]) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def _digest(payload: dict[str, Any]) -> str:
    return hashlib.sha256(_canonical_payload(payload)).hexdigest()


def _file_digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes() if path.is_file() else b"").hexdigest()


def _source_metadata_digest(source: Path) -> str:
    files = {}
    for relative in ("SKILL.md", "agents/openai.yaml"):
        path = source / relative
        files[relative] = (
            hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None
        )
    return _digest(files)


def _directory_state_digest(root: Path) -> str:
    if not root.exists():
        return _digest({"kind": "missing"})
    entries: dict[str, dict[str, Any]] = {}
    for current, directories, files in os.walk(root, topdown=True, followlinks=False):
        current_path = Path(current)
        directories[:] = sorted(directories)
        for name in sorted(directories + files):
            entry = current_path / name
            relative = entry.relative_to(root).as_posix()
            mode = stat.S_IMODE(entry.lstat().st_mode)
            if entry.is_symlink():
                entries[relative] = {
                    "kind": "symlink",
                    "mode": mode,
                    "target": os.readlink(entry),
                }
            elif entry.is_dir():
                entries[relative] = {"kind": "directory", "mode": mode}
            elif entry.is_file():
                entries[relative] = {
                    "kind": "file",
                    "mode": mode,
                    "sha256": hashlib.sha256(entry.read_bytes()).hexdigest(),
                }
            else:
                entries[relative] = {"kind": "other", "mode": mode}
    return _digest(entries)


def _jsonable(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {key: _jsonable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    return value


def _write_plan_artifact(payload: dict[str, Any], artifact_path: Path) -> str:
    digest = _digest(payload)
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_text(
        json.dumps({"digest": digest, "payload": payload}, indent=2, sort_keys=True)
        + "\n"
    )
    return digest


def _read_plan_artifact(
    artifact_path: Path,
    expected_digest: str,
    *,
    version: int,
    label: str,
    operation: str | None = None,
) -> dict[str, Any]:
    artifact = json.loads(artifact_path.read_text())
    payload = artifact.get("payload")
    if not isinstance(payload, dict) or artifact.get("digest") != _digest(payload):
        raise BlockedOperation(f"{label} artifact digest is invalid")
    if payload.get("version") != version or (
        operation is not None and payload.get("operation") != operation
    ):
        raise BlockedOperation(f"{label} artifact version is unsupported")
    if artifact["digest"] != expected_digest:
        raise BlockedOperation(f"approved digest does not match {label} artifact")
    return payload


def _request_managed_names(request: dict[str, Any]) -> set[str] | None:
    raw = request.get("managed_names")
    if raw is None:
        return None
    if not isinstance(raw, list) or any(not isinstance(name, str) for name in raw):
        raise ValueError("managed_names must be an array of Skill names")
    return set(raw)


def plan_sync(
    request: dict[str, Any],
    artifact_path: Path,
    *,
    authority: AcceptedFleetRevision | None = None,
) -> dict[str, Any]:
    if "accepted_revision" in request:
        raise ValueError("accepted_revision is available only to Fleet apply")
    profile_path = _plan_profile_path(request, authority)
    profile = normalize_profile(request["profile"])
    sources = {
        str(name): Path(path).expanduser().resolve()
        for name, path in request.get("sources", {}).items()
    }
    if sources != profile_sources(profile):
        raise ValueError("link request sources must exactly match profile sources")
    requested_managed_names = _request_managed_names(request)
    accepted_revision = None if authority is None else authority.revision
    if authority is not None and requested_managed_names is not None:
        raise ValueError("Fleet apply derives managed names from accepted authority")
    if authority is not None:
        _validate_authority_profile(profile, profile_path, authority)
        _validate_authoritative_sources(sources, authority)
    validated_source_names = (
        set(sources)
        if requested_managed_names is None or authority is not None
        else requested_managed_names & set(sources)
    )
    for name in validated_source_names:
        validate_link_source(sources[name])
    source_metadata_digests = {
        name: _source_metadata_digest(sources[name])
        for name in sorted(validated_source_names)
    }
    source_content_digests = (
        {
            name: _directory_state_digest(sources[name])
            for name in sorted(validated_source_names)
        }
        if accepted_revision is not None
        else {}
    )
    reusable = {
        str(name): Path(path).expanduser().resolve()
        for name, path in request.get("reusable_targets", {}).items()
    }
    raw_registries = request.get("registries")
    if not isinstance(raw_registries, list) or not raw_registries:
        raise ValueError("registries must be a non-empty list")
    registry_plans = []
    seen_directories: set[Path] = set()
    for raw in raw_registries:
        if not isinstance(raw, dict):
            raise TypeError("each registry must be an object")
        directory = _lexical_absolute(raw["directory"], "registry")
        if directory in seen_directories:
            raise ValueError("registry directories must be unique")
        seen_directories.add(directory)
        scope = str(raw.get("scope", "global"))
        _public_scope(scope)
        _validate_registry_directory(scope, directory)
        managed_names = requested_managed_names
        if authority is not None:
            if scope == "global":
                expected_global = _lexical_absolute(
                    authority.global_registry,
                    "accepted global registry",
                )
                if directory != expected_global:
                    raise ValueError(
                        "global registry does not match accepted Fleet revision"
                    )
                managed_names = None
            else:
                if scope not in authority.linked_scopes:
                    raise ValueError("repo is not linked by accepted Fleet revision")
                _validate_authoritative_repo(Path(scope), authority)
                managed_names = set(authority.linked_scopes[scope])
        desired = [str(item) for item in raw.get("desired", [])]
        if desired != _link_desired_for_scope(profile, scope):
            raise ValueError(
                "desired links must exactly match the profile include list for each scope"
            )
        plan = plan_link_directory(scope, directory, desired, sources, reusable)
        if authority is not None:
            plan = _authoritative_link_plan(
                plan,
                set(desired),
                sources,
                reusable,
                managed_names,
            )
        if managed_names is not None:
            plan = _restrict_link_plan(plan, managed_names)
        registry_plans.append(
            {
                "scope": scope,
                "directory": str(directory),
                "before_digest": _directory_state_digest(directory),
                "desired": desired,
                "managed_names": (
                    None if managed_names is None else sorted(managed_names)
                ),
                "plan": _jsonable(asdict(plan)),
            }
        )
    payload = {
        "version": PLAN_VERSION,
        "accepted_revision": accepted_revision,
        "profile_path": None if profile_path is None else str(profile_path),
        "profile_before_digest": (
            None if profile_path is None else _file_digest(profile_path)
        ),
        "profile_content": render_profile(profile),
        "sources": {name: str(path) for name, path in sources.items()},
        "source_metadata_digests": source_metadata_digests,
        "source_content_digests": source_content_digests,
        "managed_names": None
        if requested_managed_names is None
        else sorted(requested_managed_names),
        "reusable_targets": {name: str(path) for name, path in reusable.items()},
        "registries": registry_plans,
    }
    digest = _write_plan_artifact(payload, artifact_path)
    plans = [_link_plan(item["plan"]) for item in registry_plans]
    destructive = sum(
        len(plan.retarget_links)
        + len(plan.remove_links)
        + len(plan.overwrite_entries)
        + len(plan.remove_entries)
        for plan in plans
    )
    blocked = any(plan.unresolved or plan.conflicts for plan in plans)
    action_counts = {
        "create": sum(len(plan.create_links) for plan in plans),
        "retarget": sum(len(plan.retarget_links) for plan in plans),
        "remove": sum(len(plan.remove_links) for plan in plans),
        "unresolved": sum(len(plan.unresolved) for plan in plans),
        "conflicts": sum(len(plan.conflicts) for plan in plans),
        "unchanged": sum(len(plan.unchanged) for plan in plans),
    }
    if accepted_revision is not None:
        action_counts.update(
            overwrite=sum(len(plan.overwrite_entries) for plan in plans),
            remove=action_counts["remove"]
            + sum(len(plan.remove_entries) for plan in plans),
            preserved=sum(len(plan.unmanaged) for plan in plans),
        )
    return {
        "status": "blocked" if blocked else "success",
        "version": PLAN_VERSION,
        "digest": digest,
        "actions": action_counts,
        "registries": [
            {
                "scope": _public_scope(item["scope"]),
                "actions": {
                    "create": len(plan.create_links),
                    "retarget": len(plan.retarget_links),
                    "remove": len(plan.remove_links),
                    "unresolved": len(plan.unresolved),
                    "conflicts": len(plan.conflicts),
                    "unchanged": len(plan.unchanged),
                    **(
                        {
                            "overwrite": len(plan.overwrite_entries),
                            "remove_entries": len(plan.remove_entries),
                            "preserved": len(plan.unmanaged),
                        }
                        if accepted_revision is not None
                        else {}
                    ),
                },
            }
            for item, plan in zip(registry_plans, plans, strict=True)
        ],
        "destructive_approval_required": (
            destructive > 0 and accepted_revision is None
        ),
    }


def _link_plan(raw: dict[str, Any]) -> LinkPlan:
    def actions(name: str) -> list[LinkAction]:
        return [
            LinkAction(
                name=item["name"],
                link=Path(item["link"]),
                target=Path(item["target"]) if item.get("target") else None,
                current_target=item.get("current_target"),
                reason=item.get("reason", ""),
            )
            for item in raw.get(name, [])
        ]

    return LinkPlan(
        scope=raw["scope"],
        directory=Path(raw["directory"]),
        create_dir=raw.get("create_dir", False),
        authoritative=raw.get("authoritative", False),
        create_links=actions("create_links"),
        retarget_links=actions("retarget_links"),
        remove_links=actions("remove_links"),
        overwrite_entries=actions("overwrite_entries"),
        remove_entries=actions("remove_entries"),
        broken_links=actions("broken_links"),
        unresolved=actions("unresolved"),
        conflicts=actions("conflicts"),
        unchanged=actions("unchanged"),
        unmanaged=actions("unmanaged"),
    )


def _restrict_link_plan(plan: LinkPlan, managed_names: set[str]) -> LinkPlan:
    def managed(actions: list[LinkAction]) -> list[LinkAction]:
        return [action for action in actions if action.name in managed_names]

    return LinkPlan(
        scope=plan.scope,
        directory=plan.directory,
        create_dir=plan.create_dir and bool(managed_names),
        authoritative=plan.authoritative,
        create_links=managed(plan.create_links),
        retarget_links=managed(plan.retarget_links),
        remove_links=managed(plan.remove_links),
        overwrite_entries=managed(plan.overwrite_entries),
        remove_entries=managed(plan.remove_entries),
        broken_links=managed(plan.broken_links),
        unresolved=managed(plan.unresolved),
        conflicts=managed(plan.conflicts),
        unchanged=managed(plan.unchanged),
        unmanaged=plan.unmanaged,
    )


def _authoritative_link_plan(
    plan: LinkPlan,
    desired: set[str],
    sources: dict[str, Path],
    reusable: dict[str, Path],
    managed_names: set[str] | None,
) -> LinkPlan:
    def is_authoritative(name: str) -> bool:
        return (
            plan.scope == "global" or name in (managed_names or set())
        )

    overwrite = list(plan.overwrite_entries)
    remaining_conflicts: list[LinkAction] = []
    for action in plan.conflicts:
        target = sources.get(action.name) or reusable.get(action.name)
        if action.name in desired and is_authoritative(action.name) and target:
            overwrite.append(replace(action, target=target, reason="authoritative name"))
        else:
            remaining_conflicts.append(action)
    remove_entries = list(plan.remove_entries)
    preserved: list[LinkAction] = []
    for action in plan.unmanaged:
        if action.name not in desired and is_authoritative(action.name):
            remove_entries.append(replace(action, reason="outside authoritative scope"))
        else:
            preserved.append(action)
    return replace(
        plan,
        authoritative=True,
        overwrite_entries=overwrite,
        remove_entries=remove_entries,
        conflicts=remaining_conflicts,
        unmanaged=preserved,
    )


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    temporary.write_text(text)
    temporary.replace(path)


def _validate_sync_artifact_authority(
    payload: dict[str, Any],
    registry_items: list[dict[str, Any]],
    plans: list[LinkPlan],
    sources: dict[str, Path],
    authority: AcceptedFleetRevision | None,
) -> None:
    accepted_revision = payload.get("accepted_revision")
    if accepted_revision is None:
        if any(plan.authoritative for plan in plans):
            raise BlockedOperation("authoritative link plan requires Fleet authority")
        return
    if authority is None or authority.revision != accepted_revision:
        raise BlockedOperation("link artifact requires matching Fleet authority")
    if not all(plan.authoritative for plan in plans):
        raise BlockedOperation("Fleet link artifact has inconsistent authority")
    try:
        profile = normalize_profile(tomllib.loads(payload["profile_content"]))
        _validate_authority_profile(
            profile,
            (
                None
                if payload.get("profile_path") is None
                else Path(payload["profile_path"])
            ),
            authority,
        )
        if sources != profile_sources(profile):
            raise ValueError("artifact sources differ from accepted profile")
        _validate_authoritative_sources(sources, authority)
        for item, plan in zip(registry_items, plans, strict=True):
            if item.get("desired") != _link_desired_for_scope(profile, plan.scope):
                raise ValueError("link artifact desired scope differs from profile")
            managed = item.get("managed_names")
            if plan.scope == "global":
                expected = _lexical_absolute(
                    authority.global_registry,
                    "accepted global registry",
                )
                if Path(item["directory"]) != expected or managed is not None:
                    raise ValueError("global artifact scope differs from authority")
            else:
                configured = authority.linked_scopes.get(plan.scope)
                if configured is None or set(managed or []) != set(configured):
                    raise ValueError("repo artifact scope differs from authority")
                _validate_authoritative_repo(Path(plan.scope), authority)
    except (
        KeyError,
        OSError,
        RuntimeError,
        TypeError,
        ValueError,
        tomllib.TOMLDecodeError,
    ) as exc:
        raise BlockedOperation("link artifact Fleet authority is invalid") from exc


def _validated_sync_plan(
    artifact_path: Path,
    expected_digest: str,
    approve_destructive: bool,
    authority: AcceptedFleetRevision | None,
) -> _ValidatedSyncPlan:
    payload = _read_plan_artifact(
        artifact_path,
        expected_digest,
        version=PLAN_VERSION,
        label="plan",
    )
    registry_items = payload["registries"]
    plans = [_link_plan(item["plan"]) for item in registry_items]
    for plan in plans:
        _validate_registry_directory(plan.scope, plan.directory)
    if any(plan.unresolved or plan.conflicts for plan in plans):
        raise BlockedOperation("plan contains unresolved entries or conflicts")
    if (
        any(
            plan.remove_links
            or plan.retarget_links
            or plan.overwrite_entries
            or plan.remove_entries
            for plan in plans
        )
        and payload.get("accepted_revision") is None
        and not approve_destructive
    ):
        raise BlockedOperation("remove or retarget actions require explicit approval")
    profile_path = (
        None if payload.get("profile_path") is None else Path(payload["profile_path"])
    )
    if profile_path is not None and _file_digest(profile_path) != payload["profile_before_digest"]:
        raise BlockedOperation("profile changed after plan")
    sources = {name: Path(path) for name, path in payload["sources"].items()}
    _validate_sync_artifact_authority(
        payload,
        registry_items,
        plans,
        sources,
        authority,
    )
    for name, expected_metadata_digest in payload["source_metadata_digests"].items():
        source = sources[name]
        try:
            validate_link_source(source)
        except ValueError as exc:
            raise BlockedOperation(
                f"source {name} metadata changed after plan"
            ) from exc
        if _source_metadata_digest(source) != expected_metadata_digest:
            raise BlockedOperation(f"source {name} metadata changed after plan")
    for name, expected_content_digest in payload.get(
        "source_content_digests", {}
    ).items():
        try:
            observed_content_digest = _directory_state_digest(sources[name])
        except OSError as exc:
            raise BlockedOperation(f"source {name} content changed after plan") from exc
        if observed_content_digest != expected_content_digest:
            raise BlockedOperation(f"source {name} content changed after plan")
    reusable = {name: Path(path) for name, path in payload["reusable_targets"].items()}
    for item, plan in zip(registry_items, plans, strict=True):
        if _directory_state_digest(Path(item["directory"])) != item["before_digest"]:
            raise BlockedOperation("link state changed after plan")
        current = plan_link_directory(
            plan.scope, Path(item["directory"]), item["desired"], sources, reusable
        )
        managed_names = item.get("managed_names", payload.get("managed_names"))
        if payload.get("accepted_revision") is not None:
            current = _authoritative_link_plan(
                current,
                set(item["desired"]),
                sources,
                reusable,
                None if managed_names is None else set(managed_names),
            )
        if managed_names is not None:
            current = _restrict_link_plan(current, set(managed_names))
        if _jsonable(asdict(current)) != item["plan"]:
            raise BlockedOperation("link state changed after plan")
    return _ValidatedSyncPlan(
        payload=payload,
        registry_items=registry_items,
        plans=plans,
        sources=sources,
        reusable=reusable,
    )


def revalidate_sync_plan(
    artifact_path: Path,
    expected_digest: str,
    approve_destructive: bool,
    *,
    authority: AcceptedFleetRevision | None = None,
) -> None:
    _validated_sync_plan(
        artifact_path,
        expected_digest,
        approve_destructive,
        authority,
    )


def apply_sync_plan(
    artifact_path: Path,
    expected_digest: str,
    approve_destructive: bool,
    *,
    authority: AcceptedFleetRevision | None = None,
) -> dict[str, Any]:
    validated = _validated_sync_plan(
        artifact_path,
        expected_digest,
        approve_destructive,
        authority,
    )
    payload = validated.payload
    registry_items = validated.registry_items
    plans = validated.plans
    sources = validated.sources
    reusable = validated.reusable
    profile_path = (
        None if payload.get("profile_path") is None else Path(payload["profile_path"])
    )
    if profile_path is not None:
        _atomic_write(profile_path, payload["profile_content"])
    for plan in plans:
        apply_link_plan(plan)
    if profile_path is not None and (
        render_profile(normalize_profile(load_profile(profile_path)))
        != payload["profile_content"]
    ):
        raise BlockedOperation("post-apply profile verification failed")
    for item, plan in zip(registry_items, plans, strict=True):
        after = plan_link_directory(
            plan.scope, Path(item["directory"]), item["desired"], sources, reusable
        )
        managed_names = item.get("managed_names", payload.get("managed_names"))
        if payload.get("accepted_revision") is not None:
            after = _authoritative_link_plan(
                after,
                set(item["desired"]),
                sources,
                reusable,
                None if managed_names is None else set(managed_names),
            )
        if managed_names is not None:
            after = _restrict_link_plan(after, set(managed_names))
        if (
            after.create_links
            or after.retarget_links
            or after.remove_links
            or after.overwrite_entries
            or after.remove_entries
            or after.unresolved
            or after.conflicts
        ):
            raise BlockedOperation("post-apply plan is not clean")
    applied = sum(
        len(plan.create_links)
        + len(plan.retarget_links)
        + len(plan.remove_links)
        + len(plan.overwrite_entries)
        + len(plan.remove_entries)
        for plan in plans
    )
    return {
        "status": "success",
        "digest": expected_digest,
        "applied_actions": applied,
        "registries": len(plans),
    }


def _load_vendor_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"version": 1, "snapshots": {}}
    value = json.loads(path.read_text())
    if (
        not isinstance(value, dict)
        or value.get("version") != 1
        or not isinstance(value.get("snapshots"), dict)
    ):
        raise ValueError("vendor state must contain version 1 and a snapshots object")
    return value


def _inspect_vendor_state(path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    empty_state: dict[str, Any] = {"version": 1, "snapshots": {}}
    if not path.exists():
        return empty_state, {"present": False, "valid": True, "errors": []}
    try:
        value = json.loads(path.read_text())
    except json.JSONDecodeError:
        return empty_state, {
            "present": True,
            "valid": False,
            "errors": ["vendor lock is not valid JSON"],
        }
    except (OSError, UnicodeError):
        return empty_state, {
            "present": True,
            "valid": False,
            "errors": ["vendor lock cannot be read"],
        }
    snapshots = value.get("snapshots") if isinstance(value, dict) else None
    inspectable_snapshots = (
        {name: record for name, record in snapshots.items() if isinstance(name, str)}
        if isinstance(snapshots, dict)
        else {}
    )
    errors: list[str] = []
    if (
        not isinstance(value, dict)
        or value.get("version") != 1
        or not isinstance(snapshots, dict)
    ):
        errors.append("vendor lock must contain version 1 and a snapshots object")
    if isinstance(snapshots, dict) and len(inspectable_snapshots) != len(snapshots):
        errors.append("vendor lock snapshot names must be strings")
    return {"version": 1, "snapshots": inspectable_snapshots}, {
        "present": True,
        "valid": not errors,
        "errors": errors,
    }


def _snapshot_plan_json(plan: SnapshotPlan) -> dict[str, Any]:
    return _jsonable(asdict(plan))


def _snapshot_plan(raw: dict[str, Any]) -> SnapshotPlan:
    def actions(name: str) -> list[SnapshotAction]:
        return [
            SnapshotAction(
                name=item["name"],
                source=Path(item["source"]) if item.get("source") else None,
                target=Path(item["target"]),
                source_digest=item.get("source_digest"),
                target_digest=item.get("target_digest"),
                current_target=item.get("current_target"),
                reason=item.get("reason", ""),
            )
            for item in raw.get(name, [])
        ]

    return SnapshotPlan(
        directory=Path(raw["directory"]),
        create_dir=raw.get("create_dir", False),
        authoritative=raw.get("authoritative", False),
        create=actions("create"),
        update=actions("update"),
        overwrite=actions("overwrite"),
        remove=actions("remove"),
        replace_symlink=actions("replace_symlink"),
        conflicts=actions("conflicts"),
        unchanged=actions("unchanged"),
    )


def _restrict_snapshot_plan(plan: SnapshotPlan, managed_names: set[str]) -> SnapshotPlan:
    def managed(actions: list[SnapshotAction]) -> list[SnapshotAction]:
        return [action for action in actions if action.name in managed_names]

    return SnapshotPlan(
        directory=plan.directory,
        create_dir=plan.create_dir and bool(managed_names),
        authoritative=plan.authoritative,
        create=managed(plan.create),
        update=managed(plan.update),
        overwrite=managed(plan.overwrite),
        remove=managed(plan.remove),
        replace_symlink=managed(plan.replace_symlink),
        conflicts=managed(plan.conflicts),
        unchanged=managed(plan.unchanged),
    )


def _vendor_action_counts(plan: SnapshotPlan) -> dict[str, int]:
    counts = {
        "create": len(plan.create),
        "update": len(plan.update),
        "remove": len(plan.remove),
        "replace_symlink": len(plan.replace_symlink),
        "conflicts": len(plan.conflicts),
        "unchanged": len(plan.unchanged),
    }
    if plan.authoritative:
        counts["overwrite"] = len(plan.overwrite)
    return counts


def _authoritative_snapshot_plan(
    plan: SnapshotPlan,
    desired: set[str],
) -> SnapshotPlan:
    overwrite = list(plan.overwrite)
    remove = list(plan.remove)
    conflicts: list[SnapshotAction] = []
    for action in plan.conflicts:
        if action.name in desired and action.source is not None:
            overwrite.append(replace(action, reason="authoritative name"))
        elif action.name not in desired:
            remove.append(replace(action, reason="outside authoritative scope"))
        else:
            conflicts.append(action)
    return replace(
        plan,
        authoritative=True,
        overwrite=overwrite,
        remove=remove,
        conflicts=conflicts,
    )


def _vendor_request(
    request: dict[str, Any],
    authority: AcceptedFleetRevision | None,
) -> tuple[
    Path | None, dict[str, Any], Path, Path, Path, dict[str, Path], list[str], dict[str, Any]
]:
    profile_path = _plan_profile_path(request, authority)
    profile = normalize_profile(request["profile"])
    repo = Path(request["repo"]).expanduser().resolve()
    if not repo.is_dir():
        raise ValueError(f"repo path is not a directory: {repo}")
    registry = Path(request["registry"]).expanduser().resolve()
    expected_registry = repo / ".agents" / "skills"
    if registry != expected_registry:
        raise ValueError(f"vendor registry must be {expected_registry}")
    state_path = Path(request["state_path"]).expanduser().resolve()
    expected_state = repo / ".agents" / "skill-manager" / "vendor-lock.json"
    if state_path != expected_state:
        raise ValueError(f"vendor state must be {expected_state}")
    sources = {
        str(name): Path(path).expanduser().resolve()
        for name, path in request.get("sources", {}).items()
    }
    if sources != profile_sources(profile):
        raise ValueError("vendor request sources must exactly match profile sources")
    desired = [str(name) for name in request.get("desired", [])]
    repo_table = profile.get("repos", {}).get(str(repo), {})
    if (
        not isinstance(repo_table, dict)
        or list(repo_table.get("vendor", [])) != desired
    ):
        raise ValueError(
            "desired snapshots must exactly match the repo profile vendor list"
        )
    managed_names = _request_managed_names(request)
    for name in desired:
        if managed_names is not None and name not in managed_names:
            continue
        source = sources.get(name)
        if source is not None:
            validate_snapshot_source(source)
    state = _load_vendor_state(state_path)
    return profile_path, profile, repo, registry, state_path, sources, desired, state


def plan_vendor(
    request: dict[str, Any],
    artifact_path: Path,
    *,
    authority: AcceptedFleetRevision | None = None,
) -> dict[str, Any]:
    if "accepted_revision" in request:
        raise ValueError("accepted_revision is available only to Fleet apply")
    profile_path, profile, repo, registry, state_path, sources, desired, state = (
        _vendor_request(request, authority)
    )
    plan = plan_snapshot_directory(registry, desired, sources, state["snapshots"])
    requested_managed_names = _request_managed_names(request)
    accepted_revision = None if authority is None else authority.revision
    if authority is not None and requested_managed_names is not None:
        raise ValueError("Fleet apply derives managed names from accepted authority")
    managed_names = requested_managed_names
    if authority is not None:
        _validate_authority_profile(profile, profile_path, authority)
        _validate_authoritative_sources(sources, authority)
        repo_key = str(repo)
        if repo_key not in authority.vendored_scopes:
            raise ValueError("repo is not vendored by accepted Fleet revision")
        _validate_authoritative_repo(repo, authority)
        configured = set(authority.vendored_scopes[repo_key])
        if configured != set(desired):
            raise ValueError("vendor scope does not match accepted Fleet revision")
        proven_snapshots: set[str] = set()
        for name, record in state["snapshots"].items():
            try:
                SnapshotRecord.from_raw(name, record)
            except ValueError as exc:
                raise ValueError(
                    f"managed snapshot provenance is invalid: {name}"
                ) from exc
            proven_snapshots.add(name)
        managed_names = configured | proven_snapshots
        plan = _authoritative_snapshot_plan(plan, set(desired))
    if managed_names is not None:
        plan = _restrict_snapshot_plan(plan, managed_names)
    payload = {
        "operation": "vendor",
        "version": VENDOR_PLAN_VERSION,
        "accepted_revision": accepted_revision,
        "profile_path": None if profile_path is None else str(profile_path),
        "profile_before_digest": (
            None if profile_path is None else _file_digest(profile_path)
        ),
        "profile_content": render_profile(profile),
        "repo": str(repo),
        "registry": str(registry),
        "state_path": str(state_path),
        "state_before_digest": _file_digest(state_path),
        "sources": {name: str(path) for name, path in sources.items()},
        "desired": desired,
        "managed_names": None if managed_names is None else sorted(managed_names),
        "plan": _snapshot_plan_json(plan),
    }
    digest = _write_plan_artifact(payload, artifact_path)
    counts = _vendor_action_counts(plan)
    return {
        "status": "blocked" if plan.conflicts else "success",
        "version": VENDOR_PLAN_VERSION,
        "digest": digest,
        "scope": _public_scope(str(repo)),
        "actions": counts,
        "destructive_approval_required": bool(
            (plan.remove or plan.replace_symlink or plan.overwrite)
            and accepted_revision is None
        ),
    }


def apply_vendor_plan(
    artifact_path: Path,
    expected_digest: str,
    approve_destructive: bool,
    *,
    authority: AcceptedFleetRevision | None = None,
) -> dict[str, Any]:
    payload, plan, sources, current_state = _validated_vendor_plan(
        artifact_path,
        expected_digest,
        approve_destructive,
        authority,
    )
    profile_path = (
        None if payload.get("profile_path") is None else Path(payload["profile_path"])
    )
    state_path = Path(payload["state_path"])
    if profile_path is not None:
        _atomic_write(profile_path, payload["profile_content"])
    apply_snapshot_plan(plan)
    snapshots = dict(current_state["snapshots"])
    for action in plan.create + plan.update + plan.overwrite + plan.replace_symlink:
        if action.source_digest is None:
            raise BlockedOperation(f"snapshot source digest is missing: {action.name}")
        target_digest = tree_digest(action.target)
        if target_digest != action.source_digest:
            raise BlockedOperation(f"post-copy snapshot digest mismatch: {action.name}")
        snapshots[action.name] = SnapshotRecord(
            source_alias=action.name,
            source_digest=action.source_digest,
            target_digest=target_digest,
        ).as_dict()
    for action in plan.remove:
        snapshots.pop(action.name, None)
    _atomic_write(
        state_path,
        json.dumps({"version": 1, "snapshots": snapshots}, indent=2, sort_keys=True)
        + "\n",
    )
    if profile_path is not None and (
        render_profile(normalize_profile(load_profile(profile_path)))
        != payload["profile_content"]
    ):
        raise BlockedOperation("post-apply profile verification failed")
    after = plan_snapshot_directory(
        Path(payload["registry"]), payload["desired"], sources, snapshots
    )
    managed_names = payload.get("managed_names")
    if payload.get("accepted_revision") is not None:
        after = _authoritative_snapshot_plan(after, set(payload["desired"]))
    if managed_names is not None:
        after = _restrict_snapshot_plan(after, set(managed_names))
    if (
        after.create
        or after.update
        or after.overwrite
        or after.remove
        or after.replace_symlink
        or after.conflicts
    ):
        raise BlockedOperation("post-apply vendor plan is not clean")
    return {
        "status": "success",
        "digest": expected_digest,
        "applied_actions": len(plan.create)
        + len(plan.update)
        + len(plan.overwrite)
        + len(plan.remove)
        + len(plan.replace_symlink),
        "snapshots": len(snapshots),
    }


def revalidate_vendor_plan(
    artifact_path: Path,
    expected_digest: str,
    approve_destructive: bool,
    *,
    authority: AcceptedFleetRevision | None = None,
) -> None:
    _validated_vendor_plan(
        artifact_path,
        expected_digest,
        approve_destructive,
        authority,
    )


def _validate_vendor_artifact_paths(payload: dict[str, Any]) -> None:
    repo = _lexical_absolute(payload["repo"], "repository")
    registry = _lexical_absolute(payload["registry"], "vendor registry")
    _validate_registry_directory(str(repo), registry)
    state_path = _lexical_absolute(payload["state_path"], "vendor state")
    expected_state = _lexical_absolute(
        repo / ".agents" / "skill-manager" / "vendor-lock.json",
        "vendor state",
    )
    if state_path != expected_state:
        raise ValueError(f"vendor state must be {expected_state}")
    if expected_state.parent.is_symlink() or expected_state.is_symlink():
        raise ValueError("vendor state path must not traverse a symlink")


def _validate_vendor_artifact_authority(
    payload: dict[str, Any],
    plan: SnapshotPlan,
    sources: dict[str, Path],
    current_state: dict[str, Any],
    authority: AcceptedFleetRevision | None,
) -> None:
    accepted_revision = payload.get("accepted_revision")
    if accepted_revision is None:
        if plan.authoritative:
            raise BlockedOperation("authoritative vendor plan requires Fleet authority")
        return
    if authority is None or authority.revision != accepted_revision:
        raise BlockedOperation("vendor artifact requires matching Fleet authority")
    if not plan.authoritative:
        raise BlockedOperation("Fleet vendor artifact has inconsistent authority")
    try:
        profile = normalize_profile(tomllib.loads(payload["profile_content"]))
        _validate_authority_profile(
            profile,
            (
                None
                if payload.get("profile_path") is None
                else Path(payload["profile_path"])
            ),
            authority,
        )
        if sources != profile_sources(profile):
            raise ValueError("artifact sources differ from accepted profile")
        _validate_authoritative_sources(sources, authority)
        repo = str(_lexical_absolute(payload["repo"], "repository"))
        configured = authority.vendored_scopes.get(repo)
        if configured is None or set(payload["desired"]) != set(configured):
            raise ValueError("vendor artifact scope differs from authority")
        _validate_authoritative_repo(Path(repo), authority)
        proven: set[str] = set()
        for name, record in current_state["snapshots"].items():
            SnapshotRecord.from_raw(name, record)
            proven.add(name)
        if set(payload.get("managed_names") or []) != set(configured) | proven:
            raise ValueError("vendor artifact managed scope differs from authority")
    except (
        KeyError,
        OSError,
        RuntimeError,
        TypeError,
        ValueError,
        tomllib.TOMLDecodeError,
    ) as exc:
        raise BlockedOperation("vendor artifact Fleet authority is invalid") from exc


def _validated_vendor_plan(
    artifact_path: Path,
    expected_digest: str,
    approve_destructive: bool,
    authority: AcceptedFleetRevision | None,
) -> tuple[dict[str, Any], SnapshotPlan, dict[str, Path], dict[str, Any]]:
    payload = _read_plan_artifact(
        artifact_path,
        expected_digest,
        version=VENDOR_PLAN_VERSION,
        label="vendor plan",
        operation="vendor",
    )
    try:
        _validate_vendor_artifact_paths(payload)
    except (KeyError, TypeError, ValueError) as exc:
        raise BlockedOperation("vendor artifact target paths are invalid") from exc
    plan = _snapshot_plan(payload["plan"])
    if plan.conflicts:
        raise BlockedOperation("vendor plan contains conflicts")
    if (
        (plan.remove or plan.replace_symlink or plan.overwrite)
        and payload.get("accepted_revision") is None
        and not approve_destructive
    ):
        raise BlockedOperation(
            "remove or replace-symlink actions require explicit approval"
        )
    profile_path = (
        None if payload.get("profile_path") is None else Path(payload["profile_path"])
    )
    state_path = Path(payload["state_path"])
    if profile_path is not None and _file_digest(profile_path) != payload["profile_before_digest"]:
        raise BlockedOperation("profile changed after vendor plan")
    if _file_digest(state_path) != payload["state_before_digest"]:
        raise BlockedOperation("vendor state changed after plan")
    sources = {name: Path(path) for name, path in payload["sources"].items()}
    current_state = _load_vendor_state(state_path)
    _validate_vendor_artifact_authority(
        payload,
        plan,
        sources,
        current_state,
        authority,
    )
    current = plan_snapshot_directory(
        Path(payload["registry"]),
        payload["desired"],
        sources,
        current_state["snapshots"],
    )
    managed_names = payload.get("managed_names")
    if payload.get("accepted_revision") is not None:
        current = _authoritative_snapshot_plan(current, set(payload["desired"]))
    if managed_names is not None:
        current = _restrict_snapshot_plan(current, set(managed_names))
    if _snapshot_plan_json(current) != payload["plan"]:
        raise BlockedOperation("snapshot or source state changed after plan")
    return payload, plan, sources, current_state
