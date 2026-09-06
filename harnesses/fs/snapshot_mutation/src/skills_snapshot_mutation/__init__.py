from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path

from skills_snapshot_plan import (
    SnapshotAction,
    SnapshotPlan,
    is_ignored_snapshot_name,
    tree_digest,
)


def _ignored(_directory: str, names: list[str]) -> set[str]:
    return {name for name in names if is_ignored_snapshot_name(name)}


def _stage(action: SnapshotAction) -> Path:
    if action.source is None:
        raise RuntimeError(f"missing source for snapshot: {action.name}")
    action.target.parent.mkdir(parents=True, exist_ok=True)
    temporary_root = Path(
        tempfile.mkdtemp(prefix=f".{action.name}.vendor-", dir=action.target.parent)
    )
    staged = temporary_root / action.name
    try:
        shutil.copytree(action.source, staged, symlinks=True, ignore=_ignored)
        if action.source_digest is None or tree_digest(staged) != action.source_digest:
            raise RuntimeError(
                f"staged snapshot digest does not match plan: {action.name}"
            )
    except Exception:
        shutil.rmtree(temporary_root, ignore_errors=True)
        raise
    return staged


def _install_create(action: SnapshotAction) -> None:
    if action.target.exists() or action.target.is_symlink():
        raise RuntimeError(
            f"refusing to overwrite existing snapshot target: {action.target}"
        )
    staged = _stage(action)
    temporary_root = staged.parent
    try:
        os.replace(staged, action.target)
    finally:
        shutil.rmtree(temporary_root, ignore_errors=True)


def _install_update(action: SnapshotAction) -> None:
    if not action.target.is_dir() or action.target.is_symlink():
        raise RuntimeError(
            f"managed snapshot target changed before update: {action.target}"
        )
    staged = _stage(action)
    temporary_root = staged.parent
    backup = Path(
        tempfile.mkdtemp(prefix=f".{action.name}.backup-", dir=action.target.parent)
    )
    backup.rmdir()
    os.replace(action.target, backup)
    try:
        os.replace(staged, action.target)
    except Exception:
        os.replace(backup, action.target)
        raise
    else:
        shutil.rmtree(backup)
    finally:
        shutil.rmtree(temporary_root, ignore_errors=True)


def _install_overwrite(action: SnapshotAction) -> None:
    staged = _stage(action)
    temporary_root = staged.parent
    backup = temporary_root / "previous"
    had_target = action.target.exists() or action.target.is_symlink()
    if had_target:
        os.replace(action.target, backup)
    try:
        os.replace(staged, action.target)
    except Exception:
        if had_target:
            os.replace(backup, action.target)
        raise
    else:
        if backup.is_symlink() or backup.is_file():
            backup.unlink()
        elif backup.is_dir():
            shutil.rmtree(backup)
    finally:
        shutil.rmtree(temporary_root, ignore_errors=True)


def _replace_symlink(action: SnapshotAction) -> None:
    if not action.target.is_symlink() or action.current_target is None:
        raise RuntimeError(
            f"snapshot symlink changed before replacement: {action.target}"
        )
    staged = _stage(action)
    temporary_root = staged.parent
    action.target.unlink()
    try:
        os.replace(staged, action.target)
    except Exception:
        action.target.symlink_to(action.current_target)
        raise
    finally:
        shutil.rmtree(temporary_root, ignore_errors=True)


def _remove_snapshot(action: SnapshotAction, *, authoritative: bool) -> None:
    if not action.target.exists() and not action.target.is_symlink():
        return
    if authoritative:
        if action.target.is_symlink() or action.target.is_file():
            action.target.unlink()
        elif action.target.is_dir():
            shutil.rmtree(action.target)
        return
    if action.target.is_symlink() or not action.target.is_dir():
        raise RuntimeError(
            f"refusing to remove changed managed snapshot path: {action.target}"
        )
    if (
        action.target_digest is None
        or tree_digest(action.target) != action.target_digest
    ):
        raise RuntimeError(
            f"refusing to remove drifted managed snapshot: {action.target}"
        )
    shutil.rmtree(action.target)


def apply_plan(plan: SnapshotPlan) -> None:
    if plan.conflicts:
        raise RuntimeError("snapshot conflicts prevent apply")
    if plan.overwrite and not plan.authoritative:
        raise RuntimeError("snapshot overwrite requires an authoritative plan")
    if plan.create_dir:
        plan.directory.mkdir(parents=True, exist_ok=True)
    for action in [
        *plan.create,
        *plan.update,
        *plan.overwrite,
        *plan.replace_symlink,
        *plan.remove,
    ]:
        if action.target.parent.resolve(strict=False) != plan.directory.resolve(
            strict=False
        ):
            raise RuntimeError(f"snapshot action escapes registry: {action.target}")
    for action in plan.create:
        _install_create(action)
    for action in plan.update:
        _install_update(action)
    for action in plan.overwrite:
        _install_overwrite(action)
    for action in plan.replace_symlink:
        _replace_symlink(action)
    for action in plan.remove:
        _remove_snapshot(action, authoritative=plan.authoritative)


__all__ = ["apply_plan"]
