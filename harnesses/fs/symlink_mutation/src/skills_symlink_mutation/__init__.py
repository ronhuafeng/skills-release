from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path

from skills_symlink_plan import LinkPlan, dedupe_actions


def apply_plan(plan: LinkPlan) -> None:
    if plan.unresolved or plan.conflicts:
        raise RuntimeError(f"{plan.scope}: unresolved entries or conflicts prevent apply")
    if (plan.remove_entries or plan.overwrite_entries) and not plan.authoritative:
        raise RuntimeError("real-entry actions require an authoritative plan")
    if plan.create_dir:
        plan.directory.mkdir(parents=True, exist_ok=True)

    for action in [*plan.remove_entries, *plan.overwrite_entries]:
        _require_contained(plan, action.link)

    for action in dedupe_actions(plan.remove_entries):
        _remove_entry(action.link)

    for action in dedupe_actions(plan.overwrite_entries):
        if action.target is None:
            raise RuntimeError(f"missing target for overwrite: {action.link}")
        _replace_with_symlink(action.link, action.target)

    for action in dedupe_actions(plan.remove_links):
        if action.link.is_symlink():
            action.link.unlink()
        elif action.link.exists():
            raise RuntimeError(f"refusing to remove non-symlink: {action.link}")

    for action in plan.retarget_links:
        if not action.link.is_symlink():
            raise RuntimeError(f"refusing to retarget non-symlink: {action.link}")
        if action.target is None:
            raise RuntimeError(f"missing target for retarget: {action.link}")
        action.link.unlink()
        action.link.symlink_to(action.target)

    for action in plan.create_links:
        if action.link.exists() or action.link.is_symlink():
            raise RuntimeError(f"refusing to overwrite existing path: {action.link}")
        if action.target is None:
            raise RuntimeError(f"missing target for create: {action.link}")
        action.link.symlink_to(action.target)


def _require_contained(plan: LinkPlan, target: Path) -> None:
    if target.parent.resolve(strict=False) != plan.directory.resolve(strict=False):
        raise RuntimeError(f"link action escapes registry: {target}")


def _remove_entry(target: Path) -> None:
    if target.is_symlink() or target.is_file():
        target.unlink()
    elif target.is_dir():
        shutil.rmtree(target)


def _replace_with_symlink(target: Path, source: Path) -> None:
    staging = Path(tempfile.mkdtemp(prefix=f".{target.name}.replace-", dir=target.parent))
    staged = staging / "new"
    backup = staging / "old"
    staged.symlink_to(source)
    try:
        os.replace(target, backup)
        try:
            os.replace(staged, target)
        except Exception:
            os.replace(backup, target)
            raise
        _remove_entry(backup)
    finally:
        shutil.rmtree(staging, ignore_errors=True)
