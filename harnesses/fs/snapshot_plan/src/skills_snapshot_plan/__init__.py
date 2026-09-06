from __future__ import annotations

import hashlib
import json
import os
import re
import stat
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Iterable


IGNORED_NAMES = {
    ".DS_Store",
    ".cache",
    ".coverage",
    ".git",
    ".hg",
    ".hypothesis",
    ".mypy_cache",
    ".nox",
    ".pytest_cache",
    ".ruff_cache",
    ".svn",
    ".tox",
    ".venv",
    "__pycache__",
    "htmlcov",
}


class SnapshotTargetKind(str, Enum):
    MISSING = "missing"
    SYMLINK = "symlink"
    DIRECTORY = "directory"
    OTHER = "other"


@dataclass(frozen=True)
class SnapshotAction:
    name: str
    source: Path | None
    target: Path
    source_digest: str | None = None
    target_digest: str | None = None
    current_target: str | None = None
    reason: str = ""


@dataclass
class SnapshotPlan:
    directory: Path
    create_dir: bool = False
    authoritative: bool = False
    create: list[SnapshotAction] = field(default_factory=list)
    update: list[SnapshotAction] = field(default_factory=list)
    overwrite: list[SnapshotAction] = field(default_factory=list)
    remove: list[SnapshotAction] = field(default_factory=list)
    replace_symlink: list[SnapshotAction] = field(default_factory=list)
    conflicts: list[SnapshotAction] = field(default_factory=list)
    unchanged: list[SnapshotAction] = field(default_factory=list)


@dataclass(frozen=True)
class SnapshotRecord:
    source_alias: str
    source_digest: str
    target_digest: str

    @classmethod
    def from_raw(cls, name: str, raw: object) -> SnapshotRecord:
        if not isinstance(raw, dict):
            raise ValueError("managed snapshot provenance is incomplete")
        source_alias = raw.get("source_alias")
        source_digest = raw.get("source_digest")
        target_digest = raw.get("target_digest")
        if source_alias != name:
            raise ValueError("managed snapshot provenance has the wrong source alias")
        if (
            not isinstance(source_digest, str)
            or not re.fullmatch(r"[0-9a-f]{64}", source_digest)
            or not isinstance(target_digest, str)
            or not re.fullmatch(r"[0-9a-f]{64}", target_digest)
        ):
            raise ValueError("managed snapshot provenance is incomplete")
        return cls(source_alias, source_digest, target_digest)

    def as_dict(self) -> dict[str, str]:
        return {
            "source_alias": self.source_alias,
            "source_digest": self.source_digest,
            "target_digest": self.target_digest,
        }


def validate_snapshot_name(name: str) -> str:
    if (
        not name
        or name in {".", ".."}
        or name.startswith(".")
        or "/" in name
        or "\\" in name
        or "\0" in name
    ):
        raise ValueError(f"invalid snapshot name: {name}")
    return name


def snapshot_target_kind(path: Path) -> SnapshotTargetKind:
    if path.is_symlink():
        return SnapshotTargetKind.SYMLINK
    if not path.exists():
        return SnapshotTargetKind.MISSING
    if path.is_dir():
        return SnapshotTargetKind.DIRECTORY
    return SnapshotTargetKind.OTHER


def is_ignored_snapshot_name(name: str) -> bool:
    return (
        name in IGNORED_NAMES or name.endswith(".pyc") or name.startswith(".coverage.")
    )


def _is_ignored(relative: Path) -> bool:
    return any(is_ignored_snapshot_name(part) for part in relative.parts)


def tree_manifest(
    root: Path | str, *, exclude_ignored: bool = True
) -> dict[str, dict[str, Any]]:
    base = Path(root).expanduser().resolve()
    if not base.is_dir() or not (base / "SKILL.md").is_file():
        raise ValueError(
            f"snapshot source is not a skill directory with SKILL.md: {base}"
        )
    manifest: dict[str, dict[str, Any]] = {}
    for current, directories, files in os.walk(base, topdown=True, followlinks=False):
        current_path = Path(current)
        if exclude_ignored:
            directories[:] = [
                name
                for name in directories
                if not _is_ignored((current_path / name).relative_to(base))
            ]
        directories[:] = sorted(directories)
        for name in sorted(directories + files):
            path = current_path / name
            relative = path.relative_to(base)
            if exclude_ignored and _is_ignored(relative):
                continue
            key = relative.as_posix()
            mode = stat.S_IMODE(path.lstat().st_mode)
            if path.is_symlink():
                target_text = os.readlink(path)
                if Path(target_text).is_absolute():
                    raise ValueError(f"snapshot symlink must be relative: {relative}")
                resolved = (path.parent / target_text).resolve()
                if not resolved.is_relative_to(base):
                    raise ValueError(
                        f"snapshot symlink escapes source root: {relative}"
                    )
                if not resolved.exists():
                    raise ValueError(
                        f"snapshot symlink targets missing content: {relative}"
                    )
                if _is_ignored(resolved.relative_to(base)):
                    raise ValueError(
                        f"snapshot symlink targets excluded content: {relative}"
                    )
                manifest[key] = {"kind": "symlink", "mode": mode, "target": target_text}
            elif path.is_dir():
                manifest[key] = {"kind": "directory", "mode": mode}
            elif path.is_file():
                manifest[key] = {
                    "kind": "file",
                    "mode": mode,
                    "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                }
            else:
                raise ValueError(f"unsupported snapshot entry: {relative}")
    return manifest


def manifest_digest(manifest: dict[str, dict[str, Any]]) -> str:
    encoded = json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def tree_digest(root: Path | str, *, exclude_ignored: bool = True) -> str:
    return manifest_digest(tree_manifest(root, exclude_ignored=exclude_ignored))


def plan_directory(
    directory: Path | str,
    desired_names: Iterable[str],
    sources: dict[str, Path],
    records: dict[str, dict[str, Any]] | None = None,
) -> SnapshotPlan:
    root = Path(directory).expanduser().resolve()
    plan = SnapshotPlan(directory=root, create_dir=not root.exists())
    managed = records or {}
    desired = [validate_snapshot_name(str(name)) for name in desired_names]
    desired_set = set(desired)
    for name in desired:
        source = sources.get(name)
        target = root / name
        if source is None:
            plan.conflicts.append(
                SnapshotAction(name, None, target, reason="no source mapping")
            )
            continue
        try:
            source_digest = tree_digest(source)
        except ValueError as exc:
            plan.conflicts.append(SnapshotAction(name, source, target, reason=str(exc)))
            continue
        target_kind = snapshot_target_kind(target)
        if name in managed:
            try:
                record = SnapshotRecord.from_raw(name, managed[name])
            except ValueError as exc:
                plan.conflicts.append(
                    SnapshotAction(
                        name,
                        source,
                        target,
                        source_digest=source_digest,
                        reason=str(exc),
                    )
                )
                continue
            if target_kind is not SnapshotTargetKind.DIRECTORY:
                plan.conflicts.append(
                    SnapshotAction(
                        name,
                        source,
                        target,
                        source_digest=source_digest,
                        reason="managed snapshot path changed form or is missing",
                    )
                )
                continue
            try:
                target_digest = tree_digest(target)
            except ValueError as exc:
                plan.conflicts.append(
                    SnapshotAction(
                        name,
                        source,
                        target,
                        source_digest=source_digest,
                        reason=str(exc),
                    )
                )
                continue
            action = SnapshotAction(
                name,
                source,
                target,
                source_digest=source_digest,
                target_digest=target_digest,
            )
            if target_digest != record.target_digest:
                plan.conflicts.append(
                    SnapshotAction(
                        **{
                            **action.__dict__,
                            "reason": "managed snapshot content drifted from provenance",
                        }
                    )
                )
            elif source_digest != record.source_digest:
                plan.update.append(
                    SnapshotAction(
                        **{**action.__dict__, "reason": "source content changed"}
                    )
                )
            else:
                plan.unchanged.append(
                    SnapshotAction(
                        **{
                            **action.__dict__,
                            "reason": "source and managed snapshot are unchanged",
                        }
                    )
                )
        elif target_kind is SnapshotTargetKind.SYMLINK:
            current_target = os.readlink(target)
            resolved_target = (
                (target.parent / current_target).resolve()
                if not Path(current_target).is_absolute()
                else Path(current_target).resolve()
            )
            if resolved_target != source:
                plan.conflicts.append(
                    SnapshotAction(
                        name,
                        source,
                        target,
                        source_digest=source_digest,
                        current_target=current_target,
                        reason="existing symlink does not expose the requested source",
                    )
                )
            else:
                plan.replace_symlink.append(
                    SnapshotAction(
                        name,
                        source,
                        target,
                        source_digest=source_digest,
                        current_target=current_target,
                        reason="desired snapshot currently exposed as matching symlink",
                    )
                )
        elif target_kind is SnapshotTargetKind.MISSING:
            plan.create.append(
                SnapshotAction(
                    name,
                    source,
                    target,
                    source_digest=source_digest,
                    reason="missing desired managed snapshot",
                )
            )
        elif target_kind is SnapshotTargetKind.DIRECTORY:
            plan.conflicts.append(
                SnapshotAction(
                    name,
                    source,
                    target,
                    source_digest=source_digest,
                    reason="real directory has no managed snapshot provenance",
                )
            )
        else:
            plan.conflicts.append(
                SnapshotAction(
                    name,
                    source,
                    target,
                    source_digest=source_digest,
                    reason="unsupported existing snapshot state",
                )
            )
    for raw_name, record in managed.items():
        name = validate_snapshot_name(str(raw_name))
        if name in desired_set:
            continue
        target = root / name
        target_kind = snapshot_target_kind(target)
        try:
            provenance = SnapshotRecord.from_raw(name, record)
        except ValueError as exc:
            plan.conflicts.append(SnapshotAction(name, None, target, reason=str(exc)))
            continue
        if target_kind is SnapshotTargetKind.MISSING:
            plan.conflicts.append(
                SnapshotAction(
                    name,
                    None,
                    target,
                    target_digest=provenance.target_digest,
                    reason="managed snapshot is missing",
                )
            )
        elif target_kind is SnapshotTargetKind.DIRECTORY:
            try:
                target_digest = tree_digest(target)
            except ValueError as exc:
                plan.conflicts.append(
                    SnapshotAction(name, None, target, reason=str(exc))
                )
                continue
            if target_digest != provenance.target_digest:
                plan.conflicts.append(
                    SnapshotAction(
                        name,
                        None,
                        target,
                        target_digest=target_digest,
                        reason="managed snapshot content drifted from provenance",
                    )
                )
            else:
                plan.remove.append(
                    SnapshotAction(
                        name,
                        None,
                        target,
                        target_digest=target_digest,
                        reason="outside desired vendor profile",
                    )
                )
        else:
            plan.conflicts.append(
                SnapshotAction(
                    name,
                    None,
                    target,
                    target_digest=provenance.target_digest,
                    reason="managed snapshot path changed form",
                )
            )
    return plan


__all__ = [
    "SnapshotAction",
    "SnapshotPlan",
    "SnapshotRecord",
    "SnapshotTargetKind",
    "manifest_digest",
    "is_ignored_snapshot_name",
    "plan_directory",
    "snapshot_target_kind",
    "tree_digest",
    "tree_manifest",
    "validate_snapshot_name",
]
