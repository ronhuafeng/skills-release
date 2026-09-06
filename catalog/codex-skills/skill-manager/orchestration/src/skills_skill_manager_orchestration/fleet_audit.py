from __future__ import annotations

import tomllib
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from skills_frontmatter import scan_skill_dir
from skills_snapshot_plan import SnapshotRecord, manifest_digest, tree_manifest

from .enrollment import current_host_user, read_host_identity
from .fleet_domain import FLEET_SCHEMA_VERSION, canonical_digest
from .fleet_observe import (
    file_digest as _file_digest,
)
from .fleet_observe import (
    GitWorktreeObservation,
)
from .fleet_observe import (
    HostEvidence,
)
from .fleet_observe import (
    RepositoryEvidence,
)
from .fleet_observe import (
    SourceEvidence,
)
from .fleet_observe import (
    host_evidence_fingerprint,
)
from .fleet_observe import (
    load_owned_aliases as _load_owned_aliases,
)
from .fleet_observe import (
    load_vendor_records as _load_vendor_records,
)
from .fleet_observe import (
    observation_fingerprint as _observation_fingerprint,
)
from .fleet_observe import (
    observe_worktree,
)
from .fleet_protocol import HostAuditRequest, HostAuditResult
from .source_policy import validate_fleet_source


class _EvidenceCollector:
    def __init__(self) -> None:
        self.metadata_errors: dict[Path, str | None] = {}
        self.registry_scans: dict[Path, tuple[Any, ...]] = {}
        self.tree_digests: dict[Path, str | Exception] = {}
        self.tree_manifests: dict[Path, dict[str, dict[str, Any]] | Exception] = {}
        self.worktrees: dict[
            tuple[Path, tuple[str, ...], tuple[str, ...]], GitWorktreeObservation
        ] = {}

    def metadata_error(self, path: Path) -> str | None:
        resolved = path.resolve()
        if resolved not in self.metadata_errors:
            try:
                validate_fleet_source(resolved)
            except (OSError, ValueError) as exc:
                self.metadata_errors[resolved] = str(exc)
            else:
                self.metadata_errors[resolved] = None
        return self.metadata_errors[resolved]

    def registry(self, path: Path) -> tuple[Any, ...]:
        resolved = path.resolve()
        if resolved not in self.registry_scans:
            self.registry_scans[resolved] = tuple(scan_skill_dir(resolved))
        return self.registry_scans[resolved]

    def tree_digest(self, path: Path) -> str | Exception:
        resolved = path.resolve()
        if resolved not in self.tree_digests:
            tree = self.tree_manifest(resolved)
            self.tree_digests[resolved] = (
                tree if isinstance(tree, Exception) else manifest_digest(tree)
            )
        return self.tree_digests[resolved]

    def tree_manifest(
        self,
        path: Path,
    ) -> dict[str, dict[str, Any]] | Exception:
        resolved = path.resolve()
        if resolved not in self.tree_manifests:
            try:
                self.tree_manifests[resolved] = tree_manifest(resolved)
            except (OSError, ValueError) as exc:
                self.tree_manifests[resolved] = exc
        return self.tree_manifests[resolved]

    def visibility_paths(self, repo: Path, alias: str) -> list[str]:
        prefix = f".agents/skills/{alias}"
        tree = self.tree_manifest(repo / prefix)
        if isinstance(tree, Exception):
            return [prefix, f"{prefix}/SKILL.md"]
        return [
            prefix,
            *[
                f"{prefix}/{relative}"
                for relative, entry in sorted(tree.items())
                if entry.get("kind") != "directory"
            ],
        ]

    def worktree(
        self,
        root: Path,
        alias_paths: list[str],
        visibility_paths: list[str],
    ) -> GitWorktreeObservation:
        key = (
            root.resolve(),
            tuple(sorted(set(alias_paths))),
            tuple(sorted(set(visibility_paths))),
        )
        if key not in self.worktrees:
            self.worktrees[key] = observe_worktree(root, key[1], key[2])
        return self.worktrees[key]


def _capture_host_evidence(spec: HostAuditRequest) -> HostEvidence:
    collector = _EvidenceCollector()
    rendered_profile = tomllib.loads(spec.profile_toml)
    source_paths = {
        str(alias): Path(str(path)).resolve()
        for alias, path in rendered_profile.get("sources", {}).items()
    }
    global_entries = collector.registry(Path(spec.global_registry))
    sources: dict[str, SourceEvidence] = {}
    for source_id, source_root_text in sorted(spec.source_bindings.items()):
        root = Path(source_root_text)
        alias_paths = [
            alias.relative_path
            for alias in spec.sources[source_id].skills.values()
        ]
        sources[source_id] = SourceEvidence(
            root=root,
            root_exists=root.is_dir(),
            worktree=collector.worktree(root, alias_paths, []),
        )
        for alias_path in alias_paths:
            collector.metadata_error(root / alias_path)

    repositories: dict[str, RepositoryEvidence] = {}
    for repo_id, binding in sorted(spec.repo_bindings.items()):
        repo = Path(binding.path)
        registry = repo / ".agents" / "skills"
        entries = collector.registry(registry)
        try:
            declared_owned = tuple(_load_owned_aliases(repo))
            ownership_error = None
        except (OSError, RuntimeError, TypeError, ValueError) as exc:
            declared_owned = ()
            ownership_error = str(exc)
        try:
            vendor_records = _load_vendor_records(repo)
            vendor_error = None
        except (OSError, RuntimeError, TypeError, ValueError) as exc:
            vendor_records = {}
            vendor_error = str(exc)
        owned = sorted(
            set(declared_owned) - (set(binding.include) | set(binding.vendor))
        )
        required_visible = [
            *(
                relative
                for alias in binding.vendor
                for relative in collector.visibility_paths(repo, alias)
            ),
            *(
                [".agents/skill-manager/vendor-lock.json"]
                if binding.vendor
                else []
            ),
            *(
                [".agents/skill-manager/ownership.toml"] if owned else []
            ),
            *(
                relative
                for alias in owned
                for relative in collector.visibility_paths(repo, alias)
            ),
        ]
        repositories[repo_id] = RepositoryEvidence(
            root=repo,
            root_exists=repo.is_dir(),
            worktree=collector.worktree(repo, [], required_visible),
            registry_entries=entries,
            owned_aliases=declared_owned,
            ownership_error=ownership_error,
            ownership_digest=_file_digest(
                repo / ".agents" / "skill-manager" / "ownership.toml"
            ),
            vendor_records=vendor_records,
            vendor_error=vendor_error,
            vendor_lock_digest=_file_digest(
                repo / ".agents" / "skill-manager" / "vendor-lock.json"
            ),
        )
        for alias in set(binding.include) | {
            entry.name
            for entry in entries
            if entry.kind == "symlink" and entry.name in source_paths
        }:
            if alias in source_paths:
                collector.metadata_error(source_paths[alias])
        entries_by_name = {entry.name: entry for entry in entries}
        for alias in set(binding.vendor) | set(vendor_records):
            target = registry / alias
            entry = entries_by_name.get(alias)
            if entry is not None and entry.kind == "directory":
                collector.tree_digest(target)
                if alias in source_paths:
                    collector.tree_digest(source_paths[alias])

    evidence = HostEvidence(
        # The runtime profile is an in-memory projection of the Fleet Manifest.
        # Its configured compatibility path is not host authority or audit state.
        profile_digest=spec.profile_digest,
        global_entries=global_entries,
        sources=sources,
        repositories=repositories,
        metadata_errors=collector.metadata_errors,
        tree_digests=collector.tree_digests,
        before_fingerprint="",
    )
    return replace(
        evidence,
        before_fingerprint=host_evidence_fingerprint(spec, evidence),
    )


def audit_host(spec: HostAuditRequest) -> dict[str, Any]:
    started_at = datetime.now(UTC).isoformat()
    evidence = _capture_host_evidence(spec)
    identity_result = _observe_host_identity(spec)
    before = canonical_digest(
        {
            "host_evidence": evidence.before_fingerprint,
            "identity": identity_result,
        }
    )
    drift_codes: set[str] = set()
    blockers: list[str] = []
    evidence_gaps: list[str] = []

    if not identity_result["matches"]:
        drift_codes.add("identity_drift")
        evidence_gaps.append("host enrollment identity")

    observed_profile_digest = evidence.profile_digest
    desired_profile_digest = spec.profile_digest
    profile_matches = observed_profile_digest == desired_profile_digest
    if not profile_matches:
        drift_codes.add("profile_drift")
    profile_result = {
        "path": spec.profile,
        "desired_digest": desired_profile_digest,
        "observed_digest": observed_profile_digest,
        "matches": profile_matches,
    }

    manifest_sources = spec.sources
    source_results: dict[str, Any] = {}
    for source_id, source_root_text in sorted(spec.source_bindings.items()):
        source = manifest_sources[source_id]
        root = Path(source_root_text)
        source_evidence = evidence.sources[source_id]
        observed_worktree = source_evidence.worktree
        expected_origin = source.origin
        expected_revision = source.revision
        observed_origin: str | None = None
        observed_revision: str | None = None
        clean_worktree: bool | None = None
        aliases_result: dict[str, Any] = {}
        try:
            if observed_worktree.errors:
                raise RuntimeError("; ".join(observed_worktree.errors))
            if observed_worktree.resolved_root != root.resolve():
                raise RuntimeError("source binding is not the Git worktree root")
            observed_origin = observed_worktree.origin
            observed_revision = observed_worktree.head
            clean_worktree = not bool(observed_worktree.tracked_status)
        except (OSError, RuntimeError) as exc:
            blockers.append(f"source {source_id}: {exc}")
            evidence_gaps.append(f"source {source_id} Git identity")
        else:
            if (
                observed_origin != expected_origin
                or observed_revision != expected_revision
            ):
                drift_codes.add("source_identity_drift")
            if not clean_worktree:
                drift_codes.add("source_content_drift")

        for alias, alias_spec in sorted(source.skills.items()):
            skill = root / alias_spec.relative_path
            observed_tree_oid: str | None = None
            metadata_valid = False
            alias_errors: list[str] = []
            alias_git_error = observed_worktree.alias_errors.get(
                alias_spec.relative_path
            )
            observed_tree_oid = observed_worktree.alias_tree_oids.get(
                alias_spec.relative_path
            )
            if alias_git_error is not None:
                alias_errors.append(alias_git_error)
                evidence_gaps.append(f"source alias {alias} content")
            metadata_error = evidence.metadata_errors.get(skill.resolve())
            if metadata_error is None:
                metadata_valid = True
            else:
                alias_errors.append(metadata_error)
                drift_codes.add("source_metadata_invalid")
            expected_tree_oid = alias_spec.tree_oid
            if (
                observed_tree_oid is not None
                and observed_tree_oid != expected_tree_oid
            ):
                drift_codes.add("source_content_drift")
            aliases_result[str(alias)] = {
                "path": str(skill),
                "expected_tree_oid": expected_tree_oid,
                "observed_tree_oid": observed_tree_oid,
                "metadata_valid": metadata_valid,
                "errors": alias_errors,
            }
        source_results[source_id] = {
            "path": str(root),
            "expected_origin": expected_origin,
            "observed_origin": observed_origin,
            "expected_revision": expected_revision,
            "observed_revision": observed_revision,
            "clean_worktree": clean_worktree,
            "aliases": aliases_result,
        }

    rendered_profile = tomllib.loads(spec.profile_toml)
    declared_source_paths = {
        str(alias): str(path)
        for alias, path in rendered_profile.get("sources", {}).items()
    }
    desired_global = sorted(rendered_profile.get("global", {}).get("include", []))
    source_paths = {
        str(alias): Path(str(path)).resolve()
        for alias, path in rendered_profile.get("sources", {}).items()
    }
    global_registry = Path(spec.global_registry)
    observed_entries = evidence.global_entries
    global_entries_by_name = {entry.name: entry for entry in observed_entries}
    observed_global = sorted(
        entry.name for entry in observed_entries if entry.has_skill
    )
    registry_errors: dict[str, list[str]] = {}
    global_link_results: dict[str, dict[str, Any]] = {}
    if observed_global != desired_global:
        drift_codes.add("registry_drift")
    for alias in desired_global:
        link = global_registry / alias
        entry = global_entries_by_name.get(alias)
        global_errors: list[str] = []
        metadata_valid = False
        observed_path = (
            (link.parent / entry.target).resolve()
            if entry is not None
            and entry.kind == "symlink"
            and entry.target is not None
            else None
        )
        observed_target = str(observed_path) if observed_path is not None else None
        if observed_path is None:
            global_errors.append("desired global entry is not a symlink")
        elif alias not in source_paths or observed_path != source_paths[alias]:
            global_errors.append("global link target does not match declared source")
        else:
            metadata_error = evidence.metadata_errors.get(observed_path)
            if metadata_error is None:
                metadata_valid = True
            else:
                global_errors.append(metadata_error)
        if global_errors:
            registry_errors[alias] = global_errors
            drift_codes.add("registry_drift")
        global_link_results[alias] = {
            "desired_target": declared_source_paths.get(alias),
            "observed_target": observed_target,
            "metadata_valid": metadata_valid,
            "errors": global_errors,
        }
    registry_result = {
        "global": {
            "path": str(global_registry),
            "desired": desired_global,
            "observed": observed_global,
            "links": global_link_results,
            "errors": registry_errors,
        }
    }

    manifest_repos = spec.repos
    repo_results: dict[str, Any] = {}
    for repo_id, binding in sorted(spec.repo_bindings.items()):
        repo_spec = manifest_repos[repo_id]
        repo = Path(binding.path)
        repo_evidence = evidence.repositories[repo_id]
        observed_worktree = repo_evidence.worktree
        repo_drift: set[str] = set()
        repo_blockers: list[str] = []
        expected_remote = repo_spec.remote
        observed_remote: str | None = None
        desired_links = list(binding.include)
        desired_vendors = list(binding.vendor)
        try:
            if observed_worktree.errors:
                raise RuntimeError("; ".join(observed_worktree.errors))
            if observed_worktree.resolved_root != repo.resolve():
                raise RuntimeError("repo binding is not the Git worktree root")
            observed_remote = observed_worktree.origin
        except (OSError, RuntimeError) as exc:
            repo_blockers.append(str(exc))
            evidence_gaps.append(f"repo {repo_id} identity")
        else:
            if observed_remote != expected_remote:
                repo_drift.add("repo_identity_mismatch")
                repo_blockers.append(
                    "bound repo remote does not match expected identity"
                )

        if repo_blockers or "repo_identity_mismatch" in repo_drift:
            identity_gap = f"repo {repo_id} intended target identity"
            if identity_gap not in evidence_gaps:
                evidence_gaps.append(identity_gap)
            drift_codes.update(repo_drift)
            blockers.extend(f"repo {repo_id}: {item}" for item in repo_blockers)
            repo_results[repo_id] = {
                "path": str(repo),
                "status": "incomplete",
                "inspection_blocked": True,
                "expected_remote": expected_remote,
                "observed_remote": observed_remote,
                "desired_aliases": {
                    "linked": desired_links,
                    "vendored": desired_vendors,
                    "owned": None,
                },
                "observed_aliases": None,
                "managed_snapshots": None,
                "links": None,
                "ownership": None,
                "git_visibility": None,
                "worktree_status": None,
                "unknown_directories": None,
                "unexpected_links": None,
                "unexpected_vendor_records": None,
                "registry_errors": None,
                "drift_codes": sorted(repo_drift),
                "blockers": repo_blockers,
            }
            continue

        repo_registry = repo / ".agents" / "skills"
        entries = {entry.name: entry for entry in repo_evidence.registry_entries}
        ownership_path = repo / ".agents" / "skill-manager" / "ownership.toml"
        declared_owned = list(repo_evidence.owned_aliases)
        if repo_evidence.ownership_error is not None:
            declared_owned = []
            repo_blockers.append(
                "invalid ownership declaration: " + repo_evidence.ownership_error
            )
            evidence_gaps.append(f"repo {repo_id} ownership")
        ownership_overlap = sorted(
            set(declared_owned) & (set(desired_links) | set(desired_vendors))
        )
        if ownership_overlap:
            repo_blockers.append(
                "committed ownership declaration overlaps linked or vendored "
                f"aliases: {', '.join(ownership_overlap)}"
            )
            evidence_gaps.append(f"repo {repo_id} disjoint ownership")
        owned = sorted(set(declared_owned) - set(ownership_overlap))
        vendor_records = repo_evidence.vendor_records
        if repo_evidence.vendor_error is not None:
            vendor_records = {}
            repo_blockers.append("invalid vendor lock: " + repo_evidence.vendor_error)
            evidence_gaps.append(f"repo {repo_id} vendor provenance")

        linked: list[str] = []
        vendored: list[str] = []
        observed_owned: list[str] = []
        managed_snapshots: dict[str, dict[str, str | None]] = {}
        repo_link_results: dict[str, dict[str, Any]] = {}
        registry_alias_errors: dict[str, list[str]] = {}
        observed_link_candidates = {
            alias
            for alias, entry in entries.items()
            if entry.kind == "symlink" and alias in source_paths
        }
        for alias in sorted(set(desired_links) | observed_link_candidates):
            entry = entries.get(alias)
            link = repo_registry / alias
            link_errors: list[str] = []
            metadata_valid = False
            observed_path = (
                (link.parent / entry.target).resolve()
                if entry is not None
                and entry.kind == "symlink"
                and entry.target is not None
                else None
            )
            observed_target = str(observed_path) if observed_path is not None else None
            if observed_path is None:
                link_errors.append("desired repo link is missing or not a symlink")
            elif alias not in source_paths or observed_path != source_paths[alias]:
                link_errors.append("repo link target does not match declared source")
            else:
                metadata_error = evidence.metadata_errors.get(observed_path)
                if metadata_error is None:
                    metadata_valid = True
                    linked.append(alias)
                else:
                    link_errors.append(metadata_error)
            if link_errors:
                registry_alias_errors[alias] = link_errors
                repo_drift.add("registry_drift")
            repo_link_results[alias] = {
                "desired_target": declared_source_paths.get(alias),
                "observed_target": observed_target,
                "metadata_valid": metadata_valid,
                "errors": link_errors,
            }

        for alias in sorted(set(desired_vendors) | set(vendor_records)):
            entry = entries.get(alias)
            target = repo_registry / alias
            vendor_errors: list[str] = []
            record_source_digest: str | None = None
            record_target_digest: str | None = None
            source_digest: str | None = None
            target_digest: str | None = None
            if entry is None or entry.kind != "directory":
                vendor_errors.append(
                    "desired managed snapshot is missing or not a directory"
                )
            else:
                try:
                    record = SnapshotRecord.from_raw(
                        alias,
                        vendor_records.get(alias),
                    )
                    target_value = evidence.tree_digests[target.resolve()]
                    source_value = evidence.tree_digests[
                        source_paths[alias].resolve()
                    ]
                    if isinstance(target_value, Exception):
                        raise target_value
                    if isinstance(source_value, Exception):
                        raise source_value
                    target_digest = target_value
                    source_digest = source_value
                except (KeyError, OSError, ValueError) as exc:
                    vendor_errors.append(str(exc))
                else:
                    record_source_digest = record.source_digest
                    record_target_digest = record.target_digest
                    if (
                        record.source_digest != source_digest
                        or record.target_digest != target_digest
                        or source_digest != target_digest
                    ):
                        vendor_errors.append(
                            "managed snapshot provenance does not match"
                        )
                    else:
                        vendored.append(alias)
            managed_snapshots[alias] = {
                "record_source_digest": record_source_digest,
                "record_target_digest": record_target_digest,
                "source_digest": source_digest,
                "target_digest": target_digest,
            }
            if vendor_errors:
                registry_alias_errors[alias] = vendor_errors
                repo_drift.add("vendor_provenance_drift")
        unexpected_vendor_records = sorted(set(vendor_records) - set(desired_vendors))
        if unexpected_vendor_records:
            repo_drift.add("vendor_provenance_drift")

        for alias in owned:
            entry = entries.get(alias)
            if entry is not None and entry.kind == "directory":
                observed_owned.append(alias)
            else:
                registry_alias_errors.setdefault(alias, []).append(
                    "declared repo-owned skill is missing or not a directory"
                )
                repo_drift.add("registry_drift")

        expected_aliases = (
            set(desired_links)
            | set(desired_vendors)
            | set(vendor_records)
            | set(owned)
        )
        unknown_directories = sorted(
            name
            for name, entry in entries.items()
            if entry.kind == "directory" and name not in expected_aliases
        )
        unexpected_links = sorted(
            name
            for name, entry in entries.items()
            if entry.kind == "symlink" and name not in set(desired_links)
        )
        if unknown_directories:
            repo_drift.add("repo_ownership_unknown")
            evidence_gaps.append(f"repo {repo_id} ownership for {unknown_directories}")
        if unexpected_links:
            repo_drift.add("registry_drift")

        required_visible = list(observed_worktree.visibility)
        missing_visibility = sorted(
            relative
            for relative in required_visible
            if not observed_worktree.visibility[relative].matches_worktree
        )
        if missing_visibility:
            repo_drift.add("git_visibility_drift")

        drift_codes.update(repo_drift)
        blockers.extend(f"repo {repo_id}: {item}" for item in repo_blockers)
        if repo_blockers or "repo_ownership_unknown" in repo_drift:
            repo_status = "incomplete"
        elif repo_drift:
            repo_status = "drifted"
        else:
            repo_status = "converged"
        repo_results[repo_id] = {
            "path": str(repo),
            "status": repo_status,
            "inspection_blocked": False,
            "expected_remote": expected_remote,
            "observed_remote": observed_remote,
            "desired_aliases": {
                "linked": desired_links,
                "vendored": desired_vendors,
                "owned": declared_owned,
            },
            "observed_aliases": {
                "linked": linked,
                "vendored": vendored,
                "owned": observed_owned,
            },
            "managed_snapshots": managed_snapshots,
            "links": repo_link_results,
            "ownership": {
                "path": str(ownership_path),
                "declared": declared_owned,
                "accepted": owned,
                "matches_committed": (
                    observed_worktree.visibility[
                        ".agents/skill-manager/ownership.toml"
                    ].matches_worktree
                    if declared_owned
                    else None
                ),
            },
            "unknown_directories": unknown_directories,
            "unexpected_links": unexpected_links,
            "unexpected_vendor_records": unexpected_vendor_records,
            "registry_errors": registry_alias_errors,
            "git_visibility": {
                "required": sorted(required_visible),
                "missing": missing_visibility,
            },
            "worktree_status": observed_worktree.status if not repo_blockers else None,
            "drift_codes": sorted(repo_drift),
            "blockers": repo_blockers,
        }

    after = canonical_digest(
        {
            "host_evidence": _observation_fingerprint(spec),
            "identity": _observe_host_identity(spec),
        }
    )
    if after != before:
        drift_codes.add("concurrent_change")
        blockers.append("host state changed during audit")
    if blockers or evidence_gaps:
        status = "incomplete"
    elif drift_codes:
        status = "drifted"
    else:
        status = "converged"
    result = {
        "schema_version": FLEET_SCHEMA_VERSION,
        "host_id": spec.host_id,
        "transport": spec.transport,
        "endpoint": spec.endpoint,
        "status": status,
        "runtime": {
            "path": spec.runtime,
            "protocol_version": FLEET_SCHEMA_VERSION,
            "available": True,
        },
        "identity": identity_result,
        "profile": profile_result,
        "sources": source_results,
        "repos": repo_results,
        "registries": registry_result,
        "drift_codes": sorted(drift_codes),
        "blockers": blockers,
        "evidence_gaps": evidence_gaps,
        "observation": {
            "started_at": started_at,
            "completed_at": datetime.now(UTC).isoformat(),
            "before_fingerprint": before,
            "after_fingerprint": after,
        },
    }
    return HostAuditResult.from_raw(
        result,
        expected_request=spec,
    ).as_dict()


def _observe_host_identity(spec: HostAuditRequest) -> dict[str, Any]:
    observed_enrollment_id: str | None = None
    identity_errors: list[str] = []
    observed_hostname, observed_username = current_host_user()
    try:
        observed_enrollment_id = read_host_identity().enrollment_id
    except (OSError, ValueError) as exc:
        identity_errors.append(str(exc))
    return {
        "expected": {
            "enrollment_id": spec.enrollment_id,
            "hostname": spec.hostname,
            "username": spec.username,
        },
        "observed": {
            "enrollment_id": observed_enrollment_id,
            "hostname": observed_hostname,
            "username": observed_username,
        },
        "matches": (
            observed_enrollment_id == spec.enrollment_id
            and observed_hostname == spec.hostname
            and observed_username == spec.username
        ),
        "errors": identity_errors,
    }


__all__ = ["audit_host"]
