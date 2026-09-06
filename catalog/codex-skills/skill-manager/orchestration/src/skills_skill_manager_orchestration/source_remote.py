from __future__ import annotations

import shutil
import subprocess
import tarfile
import tempfile
from io import BytesIO
from pathlib import Path
from typing import Any

from .fleet_domain import (
    GIT_OBJECT_ID_PATTERN,
    FleetConfigError,
    SourceSkill,
    credential_free_fetch_url,
)
from .fleet_observe import git_tracked_status, normalize_git_remote, run_git
from .source_policy import validate_link_source


MATERIALIZATION_GIT_TIMEOUT_SECONDS = 300


def managed_source_root() -> Path:
    return Path.home() / ".cache" / "skill-manager" / "sources"


def managed_source_path(source_id: str) -> Path:
    return managed_source_root() / source_id


def validate_fetch_url(fetch_url: str, expected_origin: str) -> None:
    credential_free_fetch_url(fetch_url, "source fetch_url")
    try:
        identity = normalize_git_remote(fetch_url)
    except ValueError as exc:
        raise FleetConfigError("source fetch_url is invalid") from exc
    if identity != expected_origin:
        raise FleetConfigError("source fetch_url differs from source identity")


def materialize_source_checkout(
    source_id: str,
    destination: Path | str,
    expected_origin: str,
    revision: str,
    *,
    fetch_url: str,
) -> str:
    """Make one exact disposable checkout and return changed or unchanged."""
    expected = managed_source_path(source_id)
    target = Path(destination).expanduser()
    if target != expected:
        raise FleetConfigError(
            f"source {source_id} path must be the Skill Manager-owned path {expected}"
        )
    root = managed_source_root()
    _reject_symlink_ancestors(root)
    if target.is_symlink():
        raise FleetConfigError("managed source path must not be a symlink")
    validate_fetch_url(fetch_url, expected_origin)
    if target.exists() and _materialization_matches(
        target,
        expected_origin,
        revision,
        fetch_url,
    ):
        return "unchanged"
    if target.exists():
        _reject_linked_worktree(target)

    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    staged = Path(tempfile.mkdtemp(prefix=f".{source_id}-", dir=root))
    backup: Path | None = None
    try:
        _run_materialization_git(staged, "init", "--quiet")
        _run_materialization_git(
            staged,
            "remote",
            "add",
            "origin",
            fetch_url,
        )
        _run_materialization_git(
            staged,
            "fetch",
            "--quiet",
            "--depth=1",
            "--no-tags",
            "origin",
            revision,
        )
        _run_materialization_git(
            staged,
            "checkout",
            "--quiet",
            "--detach",
            "FETCH_HEAD",
        )
        _run_materialization_git(
            staged,
            "remote",
            "set-url",
            "origin",
            fetch_url,
        )
        if not _materialization_matches(
            staged,
            expected_origin,
            revision,
            fetch_url,
        ):
            raise RuntimeError("managed source checkout failed exact readback")
        if target.exists():
            backup = Path(
                tempfile.mkdtemp(prefix=f".{source_id}.replaced-", dir=root)
            )
            backup.rmdir()
            target.replace(backup)
        try:
            staged.replace(target)
        except BaseException:
            if backup is not None and backup.exists() and not target.exists():
                backup.replace(target)
            raise
        if backup is not None:
            _remove_managed_tree(backup)
        return "changed"
    finally:
        if staged.exists():
            _remove_managed_tree(staged)


def _materialization_matches(
    root: Path,
    expected_origin: str,
    revision: str,
    expected_fetch_url: str,
) -> bool:
    if not root.is_dir():
        return False
    try:
        return (
            Path(run_git(root, "rev-parse", "--show-toplevel")).resolve()
            == root.resolve()
            and normalize_git_remote(
                run_git(root, "config", "--get", "remote.origin.url")
            )
            == expected_origin
            and run_git(root, "config", "--get", "remote.origin.url")
            == expected_fetch_url
            and run_git(root, "rev-parse", "HEAD") == revision
            and not run_git(
                root,
                "status",
                "--ignored",
                "--porcelain",
                "--untracked-files=all",
            )
        )
    except (OSError, RuntimeError, ValueError):
        return False


def _reject_linked_worktree(root: Path) -> None:
    try:
        common = Path(
            run_git(
                root,
                "rev-parse",
                "--path-format=absolute",
                "--git-common-dir",
            )
        )
    except (OSError, RuntimeError):
        return
    resolved = root.resolve()
    if common.resolve() != (resolved / ".git").resolve():
        raise FleetConfigError(
            "managed source path is a linked development worktree; refusing replacement"
        )


def _reject_symlink_ancestors(root: Path) -> None:
    home = Path.home()
    current = root
    while current != home:
        if current.is_symlink():
            raise FleetConfigError("managed source path must not traverse a symlink")
        if home not in current.parents:
            raise FleetConfigError("managed source root must remain inside the user home")
        current = current.parent


def _run_materialization_git(root: Path, *args: str) -> None:
    try:
        result = subprocess.run(
            ["git", "-C", str(root), *args],
            check=False,
            capture_output=True,
            text=True,
            timeout=MATERIALIZATION_GIT_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("managed source Git operation timed out") from exc
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "managed source Git operation failed")


def _remove_managed_tree(path: Path) -> None:
    if path.is_symlink() or path.is_file():
        path.unlink()
    else:
        shutil.rmtree(path)


def observe_remote_candidate(
    source_root: Path | str,
    expected_origin: str,
) -> str:
    resolved = _validated_source_root(source_root, expected_origin)

    try:
        result = subprocess.run(
            ["git", "-C", str(resolved), "ls-remote", "--exit-code", "origin", "HEAD"],
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("remote source observation timed out") from exc
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "remote source observation failed")
    candidates = [
        line.split(maxsplit=1)[0]
        for line in result.stdout.splitlines()
        if line.endswith("\tHEAD")
    ]
    if len(candidates) != 1 or not GIT_OBJECT_ID_PATTERN.fullmatch(candidates[0]):
        raise RuntimeError("remote source HEAD is invalid")
    return candidates[0]


def inspect_source_candidate(
    source_root: Path | str,
    expected_origin: str,
    pinned_revision: str,
    candidate_revision: str,
) -> dict[str, SourceSkill]:
    if not GIT_OBJECT_ID_PATTERN.fullmatch(candidate_revision):
        raise FleetConfigError("candidate revision must be a full commit")
    resolved = _validated_candidate_checkout(
        source_root,
        expected_origin,
        pinned_revision,
        candidate_revision,
    )
    if not _git_object_exists(resolved, f"{candidate_revision}^{{commit}}"):
        result = subprocess.run(
            [
                "git",
                "-C",
                str(resolved),
                "fetch",
                "--quiet",
                "--no-tags",
                "origin",
                "HEAD",
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or "candidate fetch failed")
        if not _git_object_exists(resolved, f"{candidate_revision}^{{commit}}"):
            raise FleetConfigError("observed candidate is no longer available remotely")
    ancestry = subprocess.run(
        [
            "git",
            "-C",
            str(resolved),
            "merge-base",
            "--is-ancestor",
            pinned_revision,
            candidate_revision,
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    if ancestry.returncode != 0:
        raise FleetConfigError("candidate revision is not a forward source update")
    return _catalog_at_revision(resolved, candidate_revision)


def inspect_source_revision(
    source_root: Path | str,
    expected_origin: str,
    revision: str,
) -> dict[str, SourceSkill]:
    if not GIT_OBJECT_ID_PATTERN.fullmatch(revision):
        raise FleetConfigError("source revision must be a full commit")
    resolved = _validated_source_root(source_root, expected_origin)
    if not _git_object_exists(resolved, f"{revision}^{{commit}}"):
        raise FleetConfigError("pinned source revision is unavailable")
    return _catalog_at_revision(resolved, revision)


def _catalog_at_revision(
    resolved: Path,
    revision: str,
) -> dict[str, SourceSkill]:
    discovered = {
        Path(path).parent.as_posix()
        for path in run_git(
            resolved, "ls-tree", "-r", "--name-only", revision
        ).splitlines()
        if path == "SKILL.md" or path.endswith("/SKILL.md")
    }
    paths: list[str] = []
    for path in sorted(discovered, key=lambda value: (len(Path(value).parts), value)):
        if not any(Path(parent) in Path(path).parents for parent in paths):
            paths.append(path)
    skills: dict[str, SourceSkill] = {}
    with tempfile.TemporaryDirectory(prefix="skills-source-candidate-") as directory:
        extracted = Path(directory)
        for relative_path in paths:
            object_name = f"{revision}:{relative_path}"
            tree_oid = run_git(resolved, "rev-parse", object_name)
            if not GIT_OBJECT_ID_PATTERN.fullmatch(tree_oid):
                raise FleetConfigError(f"source Skill tree is invalid: {relative_path}")
            if run_git(resolved, "cat-file", "-t", tree_oid) != "tree":
                raise FleetConfigError(f"source Skill path is not a directory: {relative_path}")
            archive = subprocess.run(
                ["git", "-C", str(resolved), "archive", revision, relative_path],
                check=False,
                capture_output=True,
                timeout=30,
            )
            if archive.returncode != 0:
                raise RuntimeError(
                    archive.stderr.decode(errors="replace").strip()
                    or f"source Skill archive failed: {relative_path}"
                )
            _extract_archive(archive.stdout, extracted)
            qualification = validate_link_source(extracted / relative_path)
            assert qualification.frontmatter is not None
            alias = str(qualification.frontmatter["name"])
            if alias in skills:
                raise FleetConfigError(f"source Skill name is duplicated: {alias}")
            skills[alias] = SourceSkill(relative_path=relative_path, tree_oid=tree_oid)
    return dict(sorted(skills.items()))


def refresh_source_checkout(
    source_root: Path | str,
    expected_origin: str,
    before_revision: str,
    after_revision: str,
    skills: dict[str, dict[str, Any]],
) -> None:
    expected_catalog = {
        alias: SourceSkill.from_raw(alias, value)
        for alias, value in skills.items()
    }
    observed_catalog = inspect_source_candidate(
        source_root,
        expected_origin,
        before_revision,
        after_revision,
    )
    if observed_catalog != expected_catalog:
        raise FleetConfigError("candidate Skill catalog differs from the reviewed source")
    resolved = Path(source_root).resolve()
    if run_git(resolved, "rev-parse", "HEAD") != after_revision:
        result = subprocess.run(
            ["git", "-C", str(resolved), "checkout", "--quiet", "--detach", after_revision],
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or "source checkout update failed")
    if run_git(resolved, "rev-parse", "HEAD") != after_revision or git_tracked_status(resolved):
        raise RuntimeError("source checkout failed post-update verification")


def _validated_candidate_checkout(
    source_root: Path | str,
    expected_origin: str,
    pinned_revision: str,
    candidate_revision: str,
) -> Path:
    resolved = _validated_source_root(source_root, expected_origin)
    if run_git(resolved, "rev-parse", "HEAD") not in {
        pinned_revision,
        candidate_revision,
    }:
        raise FleetConfigError("source checkout differs from the reviewed revisions")
    if git_tracked_status(resolved):
        raise FleetConfigError("source checkout contains tracked changes")
    return resolved


def _validated_source_root(
    source_root: Path | str,
    expected_origin: str,
) -> Path:
    root = Path(source_root)
    if not root.is_absolute() or not root.is_dir():
        raise FleetConfigError("source root must be an existing absolute directory")
    resolved = root.resolve()
    if Path(run_git(resolved, "rev-parse", "--show-toplevel")).resolve() != resolved:
        raise FleetConfigError("source root must be the Git worktree root")
    if normalize_git_remote(
        run_git(resolved, "config", "--get", "remote.origin.url")
    ) != expected_origin:
        raise FleetConfigError("source origin differs from accepted identity")
    return resolved


def _git_object_exists(root: Path, object_name: str) -> bool:
    return subprocess.run(
        ["git", "-C", str(root), "cat-file", "-e", object_name],
        check=False,
        capture_output=True,
    ).returncode == 0


def _extract_archive(content: bytes, destination: Path) -> None:
    root = destination.resolve()
    with tarfile.open(fileobj=BytesIO(content), mode="r:") as archive:
        for member in archive.getmembers():
            target = (root / member.name).resolve()
            if root != target and root not in target.parents:
                raise FleetConfigError("candidate archive contains an unsafe path")
        archive.extractall(root, filter="data")


__all__ = [
    "inspect_source_candidate",
    "inspect_source_revision",
    "managed_source_path",
    "managed_source_root",
    "materialize_source_checkout",
    "observe_remote_candidate",
    "refresh_source_checkout",
    "validate_fetch_url",
]
