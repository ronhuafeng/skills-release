from __future__ import annotations

import os
import pwd
import socket
import stat
import subprocess
import tempfile
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from skills_snapshot_plan import tree_digest

from .fleet_domain import (
    GIT_OBJECT_ID_PATTERN,
    FleetConfigError,
    FleetManifest,
    HostBinding,
    canonical_enrollment_id,
)


IDENTITY_SCHEMA_VERSION = 1


@dataclass(frozen=True)
class HostIdentity:
    enrollment_id: str


@dataclass(frozen=True)
class AcceptedFleetRevision:
    revision: str
    host_id: str
    enrollment_id: str
    profile_toml: str
    profile_path: str | None
    global_registry: str
    linked_scopes: dict[str, tuple[str, ...]]
    vendored_scopes: dict[str, tuple[str, ...]]
    repo_origins: dict[str, str]
    source_revisions: dict[str, str]
    source_tree_oids: dict[str, str]
    projected_source_digests: dict[str, str]

    def __post_init__(self) -> None:
        if not GIT_OBJECT_ID_PATTERN.fullmatch(self.revision):
            raise FleetConfigError("accepted revision must be a full lowercase commit")


def identity_path() -> Path:
    return Path.home() / ".config" / "skill-manager" / "identity.toml"


def current_host_user() -> tuple[str, str]:
    return socket.gethostname(), pwd.getpwuid(os.geteuid()).pw_name


def read_host_identity(path: Path | None = None) -> HostIdentity:
    target = identity_path() if path is None else path
    identity = _read_identity_contents(target)
    _validate_identity_permissions(target)
    return identity


def _read_identity_contents(target: Path) -> HostIdentity:
    if target.is_symlink() or not target.is_file():
        raise FleetConfigError(f"host identity is not a regular file: {target}")
    try:
        with target.open("rb") as handle:
            raw = tomllib.load(handle)
    except FileNotFoundError as exc:
        raise FleetConfigError(f"host identity not found: {target}") from exc
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise FleetConfigError(f"host identity is unreadable: {exc}") from exc
    if set(raw) != {"schema_version", "enrollment_id"}:
        raise FleetConfigError("host identity fields are invalid")
    if raw["schema_version"] != IDENTITY_SCHEMA_VERSION:
        raise FleetConfigError("host identity schema_version is incompatible")
    return HostIdentity(
        canonical_enrollment_id(
            raw["enrollment_id"],
            "host identity enrollment_id",
        )
    )


def enroll_host(manifest_path: Path, revision: str) -> dict[str, Any]:
    manifest = _load_published_manifest(manifest_path, revision)
    host, hostname, username = _select_current_host(manifest)
    _write_identity(HostIdentity(host.enrollment_id))
    if read_host_identity() != HostIdentity(host.enrollment_id):
        raise FleetConfigError("host identity readback does not match enrollment")
    return {
        "status": "enrolled",
        "host_id": host.host_id,
        "enrollment_id": host.enrollment_id,
        "hostname": hostname,
        "username": username,
        "config_revision": revision,
    }


def accept_current_fleet_revision(
    manifest_path: Path,
    revision: str,
    *,
    profile_free: bool = False,
    resolved_manifest: FleetManifest | None = None,
) -> AcceptedFleetRevision:
    from .fleet_render import render_manifest_host
    from .fleet_observe import normalize_git_remote, run_git
    from .host_transport import resolve_manifest_catalogs

    manifest = _load_published_manifest(manifest_path, revision)
    host, _, _ = _select_current_host(manifest)
    identity = read_host_identity()
    if identity.enrollment_id != host.enrollment_id:
        raise FleetConfigError("host enrollment identity does not match Fleet binding")
    if resolved_manifest is None:
        resolved = resolve_manifest_catalogs(manifest)
    else:
        if resolved_manifest.as_dict() != manifest.as_dict():
            raise FleetConfigError("resolved Fleet Manifest differs from published input")
        resolved = resolved_manifest
    rendered = render_manifest_host(resolved, host.host_id)
    rendered_profile = tomllib.loads(str(rendered["profile_toml"]))
    desired_aliases = set(host.desired_global(resolved.global_include))
    for binding in host.repo_bindings.values():
        desired_aliases.update(binding.include)
        desired_aliases.update(binding.vendor)
    for alias in sorted(desired_aliases):
        skill = resolved.resolved_skill(alias)
        source_id = skill.source_id
        source = resolved.sources[source_id]
        root = Path(host.source_bindings[source_id].path)
        if run_git(root, "rev-parse", "HEAD") != source.revision:
            raise FleetConfigError(f"source {source_id} is not at its pinned revision")
        if run_git(
            root,
            "status",
            "--ignored",
            "--porcelain",
            "--untracked-files=all",
        ):
            raise FleetConfigError(f"source {source_id} checkout is not clean")
        if run_git(root, "rev-parse", f"HEAD:{skill.relative_path}") != skill.tree_oid:
            raise FleetConfigError(f"source {source_id} Skill tree is not pinned")
    for repo_id, binding in host.repo_bindings.items():
        repo = Path(binding.path)
        observed_root = Path(
            run_git(repo, "rev-parse", "--show-toplevel")
        ).resolve()
        if observed_root != repo.resolve():
            raise FleetConfigError(f"repo {repo_id} path is not its Git root")
        observed_origin = normalize_git_remote(
            run_git(repo, "config", "--get", "remote.origin.url")
        )
        if observed_origin != resolved.repos[repo_id].remote:
            raise FleetConfigError(f"repo {repo_id} origin differs from Fleet binding")
    return AcceptedFleetRevision(
        revision=revision,
        host_id=host.host_id,
        enrollment_id=host.enrollment_id,
        profile_toml=str(rendered["profile_toml"]),
        profile_path=None if profile_free else host.profile,
        global_registry=host.global_registry,
        linked_scopes={
            binding.path: tuple(binding.include)
            for binding in host.repo_bindings.values()
        },
        vendored_scopes={
            binding.path: tuple(binding.vendor)
            for binding in host.repo_bindings.values()
        },
        repo_origins={
            binding.path: resolved.repos[repo_id].remote
            for repo_id, binding in host.repo_bindings.items()
        },
        source_revisions={
            alias: resolved.sources[resolved.resolved_skill(alias).source_id].revision
            for alias in sorted(desired_aliases)
        },
        source_tree_oids={
            alias: resolved.resolved_skill(alias).tree_oid
            for alias in sorted(desired_aliases)
        },
        projected_source_digests={
            alias: tree_digest(
                Path(rendered_profile["sources"][alias])
            )
            for alias in sorted(desired_aliases)
            if resolved.resolved_skill(alias).requires_projection
        },
    )


def _select_current_host(
    manifest: FleetManifest,
) -> tuple[HostBinding, str, str]:
    hostname, username = current_host_user()
    matches = [
        host
        for host in manifest.hosts.values()
        if host.hostname == hostname and host.username == username
    ]
    if len(matches) != 1:
        raise FleetConfigError(
            "fleet manifest must select exactly one host for current hostname and username"
        )
    return matches[0], hostname, username


def _load_published_manifest(
    manifest_path: Path,
    revision: str,
) -> FleetManifest:
    if not GIT_OBJECT_ID_PATTERN.fullmatch(revision):
        raise FleetConfigError("config revision must be a full lowercase commit")
    checkout = _git(manifest_path.parent, "rev-parse", "--show-toplevel")
    root = Path(checkout)
    try:
        relative_manifest = manifest_path.resolve().relative_to(root.resolve())
    except ValueError as exc:
        raise FleetConfigError("fleet manifest must be inside its Git checkout") from exc
    if _git(
        root,
        "status",
        "--ignored",
        "--porcelain",
        "--untracked-files=all",
    ):
        raise FleetConfigError("Fleet config worktree must be clean")
    if _git(root, "rev-parse", "HEAD") != revision:
        raise FleetConfigError("config revision must equal HEAD")
    manifest_bytes = manifest_path.read_bytes()
    committed_manifest = subprocess.run(
        ["git", "show", f"{revision}:{relative_manifest.as_posix()}"],
        cwd=root,
        capture_output=True,
        check=False,
    )
    if (
        committed_manifest.returncode != 0
        or committed_manifest.stdout != manifest_bytes
    ):
        raise FleetConfigError(
            "fleet manifest must exactly match a file in the config revision"
        )
    _git(root, "fetch", "--quiet", "--no-tags", "origin", "main")
    published = subprocess.run(
        ["git", "merge-base", "--is-ancestor", revision, "FETCH_HEAD"],
        cwd=root,
        text=True,
        capture_output=True,
        check=False,
    )
    if published.returncode != 0:
        raise FleetConfigError("config revision must be published on origin/main")
    return FleetManifest.from_raw(tomllib.loads(manifest_bytes.decode()))


def _git(root: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=root,
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        raise FleetConfigError(f"Git revision validation failed during {args[0]}")
    return completed.stdout.strip()


def _write_identity(identity: HostIdentity) -> None:
    path = identity_path()
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    path.parent.chmod(0o700)
    if os.path.lexists(path):
        _accept_existing_identity(path, identity)
        return
    content = (
        f"schema_version = {IDENTITY_SCHEMA_VERSION}\n"
        f'enrollment_id = "{identity.enrollment_id}"\n'
    )
    descriptor, temporary_name = tempfile.mkstemp(
        dir=path.parent,
        prefix=".identity.",
        text=True,
    )
    temporary = Path(temporary_name)
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "w") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(temporary, path)
        except FileExistsError:
            _accept_existing_identity(path, identity)
        else:
            read_host_identity(path)
    finally:
        temporary.unlink(missing_ok=True)


def _accept_existing_identity(path: Path, expected: HostIdentity) -> None:
    existing = _read_identity_contents(path)
    if existing != expected:
        raise FleetConfigError(
            "host identity already contains a different enrollment_id"
        )
    path.parent.chmod(0o700)
    path.chmod(0o600)
    if read_host_identity(path) != expected:
        raise FleetConfigError("host identity readback does not match enrollment")


def _validate_identity_permissions(path: Path) -> None:
    directory_mode = stat.S_IMODE(path.parent.stat().st_mode)
    file_mode = stat.S_IMODE(path.stat().st_mode)
    if directory_mode != 0o700 or file_mode != 0o600:
        raise FleetConfigError(
            "host identity permissions must be directory 0700 and file 0600"
        )


__all__ = [
    "AcceptedFleetRevision",
    "HostIdentity",
    "accept_current_fleet_revision",
    "current_host_user",
    "enroll_host",
    "identity_path",
    "read_host_identity",
]
