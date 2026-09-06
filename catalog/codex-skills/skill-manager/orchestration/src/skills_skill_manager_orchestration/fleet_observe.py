from __future__ import annotations

import hashlib
import json
import re
import subprocess
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from skills_frontmatter import scan_skill_dir

from .fleet_domain import (
    GIT_OBJECT_ID_PATTERN,
    canonical_digest,
    canonical_git_identity,
    string_list,
)
from .fleet_protocol import HostAuditRequest


@dataclass(frozen=True)
class GitPathEvidence:
    tracked_at_head: bool
    matches_worktree: bool
    error: str | None = None


@dataclass(frozen=True)
class GitWorktreeObservation:
    requested_root: Path
    resolved_root: Path | None
    head: str | None
    origin: str | None
    status: str | None
    tracked_status: str | None
    alias_tree_oids: dict[str, str | None]
    alias_errors: dict[str, str]
    visibility: dict[str, GitPathEvidence]
    errors: tuple[str, ...]


@dataclass(frozen=True)
class SourceEvidence:
    root: Path
    root_exists: bool
    worktree: GitWorktreeObservation


@dataclass(frozen=True)
class RepositoryEvidence:
    root: Path
    root_exists: bool
    worktree: GitWorktreeObservation
    registry_entries: tuple[Any, ...]
    owned_aliases: tuple[str, ...]
    ownership_error: str | None
    ownership_digest: str | None
    vendor_records: dict[str, dict[str, Any]]
    vendor_error: str | None
    vendor_lock_digest: str | None


@dataclass(frozen=True)
class HostEvidence:
    profile_digest: str | None
    global_entries: tuple[Any, ...]
    sources: dict[str, SourceEvidence]
    repositories: dict[str, RepositoryEvidence]
    metadata_errors: dict[Path, str | None]
    tree_digests: dict[Path, str | Exception]
    before_fingerprint: str


def normalize_git_remote(remote: str) -> str:
    value = remote.strip()
    parsed = urlparse(value)
    if parsed.scheme in {"ssh", "https"} and parsed.hostname:
        host = parsed.hostname
        if parsed.port is not None:
            host = f"{host}:{parsed.port}"
        path = parsed.path.lstrip("/")
    else:
        if parsed.scheme:
            raise ValueError("Git remote is not a supported network URL")
        scp_match = re.fullmatch(r"(?:[^@/]+@)?([^:/]+):(.+)", value)
        if scp_match is None:
            raise ValueError("Git remote is not a supported network URL")
        host, path = scp_match.groups()
    path = path.removesuffix(".git")
    return canonical_git_identity(f"{host}/{path}", "Git remote")


def run_git(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(root), *args],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "git command failed")
    return result.stdout.strip()


def _batch_objects(
    root: Path,
    paths: tuple[str, ...],
) -> tuple[dict[str, tuple[str, str] | None], str | None]:
    if not paths:
        return {}, None
    if any("\n" in path or "\r" in path for path in paths):
        return {}, "Git evidence paths may not contain newlines"
    completed = subprocess.run(
        [
            "git",
            "-C",
            str(root),
            "cat-file",
            "--batch-check=%(objectname) %(objecttype)",
        ],
        input="".join(f"HEAD:{path}\n" for path in paths),
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        return {}, completed.stderr.strip() or "git cat-file batch failed"
    lines = completed.stdout.splitlines()
    if len(lines) != len(paths):
        return {}, "git cat-file batch returned an unexpected result count"
    objects: dict[str, tuple[str, str] | None] = {}
    for path, line in zip(paths, lines, strict=True):
        if line.endswith(" missing"):
            objects[path] = None
            continue
        parts = line.split(" ", 1)
        if len(parts) != 2:
            return {}, f"git cat-file returned invalid evidence for {path}"
        objects[path] = (parts[0], parts[1])
    return objects, None


def _status_entries(root: Path) -> tuple[list[tuple[str, str]], str | None]:
    completed = subprocess.run(
        [
            "git",
            "-C",
            str(root),
            "status",
            "--porcelain=v1",
            "-z",
            "--untracked-files=normal",
            "--no-renames",
        ],
        check=False,
        capture_output=True,
    )
    if completed.returncode != 0:
        return (
            [],
            completed.stderr.decode(errors="replace").strip()
            or "git status failed",
        )
    entries: list[tuple[str, str]] = []
    for raw in completed.stdout.split(b"\0"):
        if not raw:
            continue
        line = raw.decode(errors="surrogateescape")
        if len(line) < 4 or line[2] != " ":
            return [], "git status returned invalid porcelain evidence"
        entries.append((line[:2], line[3:]))
    return entries, None


def _render_status(entries: list[tuple[str, str]]) -> str:
    def quote(path: str) -> str:
        if any(character.isspace() or character in {'"', "\\"} for character in path):
            return json.dumps(path, ensure_ascii=False)
        return path

    return "\n".join(f"{code} {quote(path)}" for code, path in entries).strip()


def _path_changed(relative: str, entries: list[tuple[str, str]]) -> bool:
    prefix = relative.rstrip("/") + "/"
    return any(path == relative or path.startswith(prefix) for _, path in entries)


def observe_worktree(
    root: Path | str,
    alias_paths: tuple[str, ...] | list[str],
    visibility_paths: tuple[str, ...] | list[str],
) -> GitWorktreeObservation:
    requested_root = Path(root).expanduser()
    aliases = tuple(sorted(set(alias_paths)))
    visibility = tuple(sorted(set(visibility_paths)))
    errors: list[str] = []
    resolved_root: Path | None = None
    head: str | None = None
    origin: str | None = None
    entries: list[tuple[str, str]] = []

    try:
        resolved_root = Path(
            run_git(requested_root, "rev-parse", "--show-toplevel")
        ).resolve()
    except (OSError, RuntimeError) as exc:
        errors.append(str(exc))
    try:
        head = run_git(requested_root, "rev-parse", "HEAD")
    except (OSError, RuntimeError) as exc:
        errors.append(str(exc))
    try:
        origin = normalize_git_remote(
            run_git(requested_root, "config", "--get", "remote.origin.url")
        )
    except (OSError, RuntimeError, ValueError) as exc:
        errors.append(str(exc))
    try:
        entries, status_error = _status_entries(requested_root)
    except OSError as exc:
        status_error = str(exc)
    if status_error is not None:
        errors.append(status_error)
        status = None
        tracked_status = None
    else:
        status = _render_status(entries)
        tracked_status = _render_status(
            [(code, path) for code, path in entries if code != "??"]
        )

    objects, batch_error = _batch_objects(
        requested_root,
        tuple(dict.fromkeys((*aliases, *visibility))),
    )
    alias_tree_oids: dict[str, str | None] = {}
    alias_errors: dict[str, str] = {}
    for path in aliases:
        item = objects.get(path)
        if batch_error is not None:
            alias_tree_oids[path] = None
            alias_errors[path] = batch_error
        elif item is None:
            alias_tree_oids[path] = None
            alias_errors[path] = f"committed source alias is not a tree: {path}"
        elif item[1] != "tree":
            alias_tree_oids[path] = None
            alias_errors[path] = f"committed source alias is not a tree: {path}"
        elif not GIT_OBJECT_ID_PATTERN.fullmatch(item[0]):
            alias_tree_oids[path] = None
            alias_errors[path] = f"invalid Git tree object ID: {path}"
        else:
            alias_tree_oids[path] = item[0]

    path_evidence: dict[str, GitPathEvidence] = {}
    for path in visibility:
        if batch_error is not None:
            path_evidence[path] = GitPathEvidence(False, False, batch_error)
            continue
        tracked_at_head = objects.get(path) is not None
        path_evidence[path] = GitPathEvidence(
            tracked_at_head=tracked_at_head,
            matches_worktree=(
                tracked_at_head
                and status_error is None
                and not _path_changed(
                    path,
                    [(code, changed) for code, changed in entries if code != "??"],
                )
            ),
            error=status_error,
        )
    return GitWorktreeObservation(
        requested_root=requested_root,
        resolved_root=resolved_root,
        head=head,
        origin=origin,
        status=status,
        tracked_status=tracked_status,
        alias_tree_oids=alias_tree_oids,
        alias_errors=alias_errors,
        visibility=path_evidence,
        errors=tuple(dict.fromkeys(errors)),
    )


def git_tracked_status(root: Path) -> str:
    return run_git(root, "status", "--porcelain", "--untracked-files=no")


def file_digest(path: Path) -> str | None:
    if not path.is_file():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


def registry_fingerprint(directory: Path) -> list[dict[str, Any]]:
    if not directory.is_dir():
        return []
    return _registry_entries_fingerprint(tuple(scan_skill_dir(directory)))


def _registry_entries_fingerprint(entries: tuple[Any, ...]) -> list[dict[str, Any]]:
    return [
        {
            "name": entry.name,
            "kind": entry.kind,
            "exists": entry.exists,
            "target": entry.target,
        }
        for entry in entries
    ]


def _source_fingerprint_facts(
    *,
    root_exists: bool,
    observed: GitWorktreeObservation,
    alias_paths: dict[str, str],
) -> dict[str, Any]:
    facts: dict[str, Any] = {
        "root_exists": root_exists,
        "head": observed.head,
        "status": observed.tracked_status,
        "origin": observed.origin,
        "aliases": {
            alias: (
                observed.alias_tree_oids[path]
                if path not in observed.alias_errors
                else f"error:{observed.alias_errors[path]}"
            )
            for alias, path in alias_paths.items()
        },
    }
    if observed.errors:
        facts["git_error"] = list(observed.errors)
    return facts


def _repository_fingerprint_facts(
    *,
    root_exists: bool,
    observed: GitWorktreeObservation,
    registry: list[dict[str, Any]],
    vendor_lock_digest: str | None,
    ownership_digest: str | None,
) -> dict[str, Any]:
    facts: dict[str, Any] = {
        "root_exists": root_exists,
        "registry": registry,
        "vendor_lock": vendor_lock_digest,
        "ownership": ownership_digest,
        "head": observed.head,
        "status": observed.status,
        "origin": observed.origin,
    }
    if observed.errors:
        facts["git_error"] = list(observed.errors)
    return facts


def host_evidence_fingerprint(
    spec: HostAuditRequest,
    evidence: HostEvidence,
) -> str:
    facts: dict[str, Any] = {
        "profile": evidence.profile_digest,
        "global_registry": _registry_entries_fingerprint(
            evidence.global_entries
        ),
        "sources": {},
        "repos": {},
    }
    for source_id, source in sorted(evidence.sources.items()):
        observed = source.worktree
        alias_paths = {
            alias: alias_data.relative_path
            for alias, alias_data in sorted(spec.sources[source_id].skills.items())
        }
        facts["sources"][source_id] = _source_fingerprint_facts(
            root_exists=source.root_exists,
            observed=observed,
            alias_paths=alias_paths,
        )
    for repo_id, repository in sorted(evidence.repositories.items()):
        observed = repository.worktree
        facts["repos"][repo_id] = _repository_fingerprint_facts(
            root_exists=repository.root_exists,
            observed=observed,
            registry=_registry_entries_fingerprint(repository.registry_entries),
            vendor_lock_digest=repository.vendor_lock_digest,
            ownership_digest=repository.ownership_digest,
        )
    return canonical_digest(facts)


def observation_fingerprint(spec: HostAuditRequest) -> str:
    facts: dict[str, Any] = {
        "profile": spec.profile_digest,
        "global_registry": registry_fingerprint(Path(spec.global_registry)),
        "sources": {},
        "repos": {},
    }
    for source_id, source_root_text in sorted(spec.source_bindings.items()):
        root = Path(source_root_text)
        alias_paths = {
            alias: alias_data.relative_path
            for alias, alias_data in sorted(spec.sources[source_id].skills.items())
        }
        observed = observe_worktree(root, list(alias_paths.values()), [])
        facts["sources"][source_id] = _source_fingerprint_facts(
            root_exists=root.is_dir(),
            observed=observed,
            alias_paths=alias_paths,
        )
    for repo_id, binding in sorted(spec.repo_bindings.items()):
        repo = Path(binding.path)
        observed = observe_worktree(repo, [], [])
        facts["repos"][repo_id] = _repository_fingerprint_facts(
            root_exists=repo.is_dir(),
            observed=observed,
            registry=registry_fingerprint(repo / ".agents" / "skills"),
            vendor_lock_digest=file_digest(
                repo / ".agents" / "skill-manager" / "vendor-lock.json"
            ),
            ownership_digest=file_digest(
                repo / ".agents" / "skill-manager" / "ownership.toml"
            ),
        )
    return canonical_digest(facts)


def git_blob_at_head(repo: Path, relative: str) -> bytes | None:
    result = subprocess.run(
        ["git", "-C", str(repo), "show", f"HEAD:{relative}"],
        check=False,
        capture_output=True,
    )
    if result.returncode == 0:
        return result.stdout
    existence = subprocess.run(
        ["git", "-C", str(repo), "cat-file", "-e", f"HEAD:{relative}"],
        check=False,
        capture_output=True,
    )
    if existence.returncode != 0:
        return None
    raise RuntimeError(
        result.stderr.decode(errors="replace").strip()
        or f"unable to read committed path: {relative}"
    )


def load_owned_aliases(repo: Path) -> list[str]:
    content = git_blob_at_head(repo, ".agents/skill-manager/ownership.toml")
    if content is None:
        return []
    raw = tomllib.loads(content.decode())
    if raw.get("schema_version") != 1:
        raise ValueError("ownership.toml schema_version must be 1")
    return sorted(string_list(raw.get("owned", []), "ownership owned"))


def load_vendor_records(repo: Path) -> dict[str, dict[str, Any]]:
    content = git_blob_at_head(repo, ".agents/skill-manager/vendor-lock.json")
    if content is None:
        return {}
    raw = json.loads(content)
    if not isinstance(raw, dict) or raw.get("version") != 1:
        raise ValueError("vendor lock version must be 1")
    snapshots = raw.get("snapshots")
    if not isinstance(snapshots, dict):
        raise TypeError("vendor lock snapshots must be an object")
    return snapshots


__all__ = [
    "file_digest",
    "git_tracked_status",
    "load_owned_aliases",
    "load_vendor_records",
    "normalize_git_remote",
    "registry_fingerprint",
    "run_git",
]
