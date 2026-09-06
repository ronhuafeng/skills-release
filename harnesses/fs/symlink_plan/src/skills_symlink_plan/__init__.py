from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True)
class DesiredLink:
    name: str
    target: Path | None
    valid: bool = True
    reason: str = ""


@dataclass(frozen=True)
class CurrentEntry:
    name: str
    path: Path
    kind: str
    target: Path | None = None
    target_text: str | None = None
    has_skill: bool = False


@dataclass(frozen=True)
class LinkAction:
    name: str
    link: Path
    target: Path | None = None
    current_target: str | None = None
    reason: str = ""


@dataclass
class LinkPlan:
    scope: str
    directory: Path
    create_dir: bool = False
    authoritative: bool = False
    create_links: list[LinkAction] = field(default_factory=list)
    retarget_links: list[LinkAction] = field(default_factory=list)
    remove_links: list[LinkAction] = field(default_factory=list)
    overwrite_entries: list[LinkAction] = field(default_factory=list)
    remove_entries: list[LinkAction] = field(default_factory=list)
    broken_links: list[LinkAction] = field(default_factory=list)
    unresolved: list[LinkAction] = field(default_factory=list)
    conflicts: list[LinkAction] = field(default_factory=list)
    unchanged: list[LinkAction] = field(default_factory=list)
    unmanaged: list[LinkAction] = field(default_factory=list)


def validate_link_name(name: str) -> str:
    if (
        not name
        or name in {".", ".."}
        or name.startswith(".")
        or "/" in name
        or "\\" in name
        or "\0" in name
    ):
        raise ValueError(f"invalid link name: {name}")
    return name


def resolve_link_target(link: Path) -> Path:
    target = Path(os.readlink(link)).expanduser()
    if not target.is_absolute():
        target = link.parent / target
    return target.resolve(strict=False)


def valid_skill_source(path: Path) -> bool:
    return path.exists() and path.is_dir() and (path / "SKILL.md").exists()


def current_entries_from_directory(directory: Path | str) -> list[CurrentEntry]:
    root = Path(directory)
    if not root.exists():
        return []
    entries: list[CurrentEntry] = []
    for child in sorted(root.iterdir(), key=lambda p: p.name):
        if child.is_symlink():
            target_text = os.readlink(child)
            try:
                target = resolve_link_target(child)
            except OSError:
                target = None
            entries.append(
                CurrentEntry(
                    name=child.name,
                    path=child,
                    kind="symlink",
                    target=target,
                    target_text=target_text,
                    has_skill=bool(target and valid_skill_source(target)),
                )
            )
        elif child.is_dir():
            entries.append(CurrentEntry(name=child.name, path=child, kind="directory", has_skill=(child / "SKILL.md").exists()))
        else:
            entries.append(CurrentEntry(name=child.name, path=child, kind="file"))
    return entries


def resolve_source(name: str, sources: dict[str, Path], reusable_targets: dict[str, Path]) -> Path | None:
    source = sources.get(name)
    if source is not None:
        return source
    return reusable_targets.get(name)


def desired_links_from_sources(
    desired_names: Iterable[str],
    sources: dict[str, Path],
    reusable_targets: dict[str, Path] | None = None,
) -> list[DesiredLink]:
    reusable = reusable_targets or {}
    links: list[DesiredLink] = []
    for raw_name in desired_names:
        name = validate_link_name(str(raw_name))
        target = resolve_source(name, sources, reusable)
        if target is None:
            links.append(DesiredLink(name=name, target=None, valid=False, reason="no source mapping or reusable existing symlink target"))
        elif not valid_skill_source(target):
            links.append(DesiredLink(name=name, target=target, valid=False, reason="source is not a skill directory with SKILL.md"))
        else:
            links.append(DesiredLink(name=name, target=target))
    return links


def plan_links(
    scope: str,
    directory: Path | str,
    desired: Iterable[DesiredLink],
    current_entries: Iterable[CurrentEntry],
    *,
    create_dir: bool = False,
) -> LinkPlan:
    root = Path(directory)
    desired_by_name = {validate_link_name(item.name): item for item in desired}
    desired_set = set(desired_by_name)
    plan = LinkPlan(scope=scope, directory=root, create_dir=create_dir)
    existing_names: set[str] = set()

    for entry in current_entries:
        existing_names.add(entry.name)
        if entry.name.startswith("."):
            plan.unmanaged.append(LinkAction(entry.name, entry.path, reason="hidden entry"))
            continue

        desired_link = desired_by_name.get(entry.name)
        if entry.kind == "symlink":
            target_text = entry.target_text
            if entry.target is None or not entry.path.exists():
                action = LinkAction(entry.name, entry.path, current_target=target_text, reason="broken symlink")
                plan.broken_links.append(action)
                if entry.name not in desired_set:
                    plan.remove_links.append(action)
                elif desired_link is None or not desired_link.valid or desired_link.target is None:
                    plan.unresolved.append(
                        LinkAction(
                            entry.name,
                            entry.path,
                            target=desired_link.target if desired_link else None,
                            current_target=target_text,
                            reason=desired_link.reason if desired_link else "broken desired symlink has no source",
                        )
                    )
                else:
                    plan.retarget_links.append(
                        LinkAction(entry.name, entry.path, target=desired_link.target, current_target=target_text, reason="repair broken desired symlink")
                    )
                continue

            if entry.name not in desired_set:
                plan.remove_links.append(LinkAction(entry.name, entry.path, current_target=target_text, reason="outside desired profile"))
                continue
            if desired_link is not None and desired_link.valid and desired_link.target is not None and entry.target != desired_link.target:
                plan.retarget_links.append(
                    LinkAction(entry.name, entry.path, target=desired_link.target, current_target=target_text, reason="target differs from profile source")
                )
            else:
                plan.unchanged.append(LinkAction(entry.name, entry.path, current_target=target_text, reason="desired symlink exists"))
            continue

        if entry.name in desired_set:
            plan.conflicts.append(
                LinkAction(
                    entry.name,
                    entry.path,
                    reason="desired name exists but is not a managed symlink",
                )
            )
        else:
            plan.unmanaged.append(LinkAction(entry.name, entry.path, reason="real entry outside symlink management"))

    for name, desired_link in desired_by_name.items():
        if name in existing_names:
            continue
        if not desired_link.valid or desired_link.target is None:
            plan.unresolved.append(LinkAction(name, root / name, target=desired_link.target, reason=desired_link.reason))
            continue
        plan.create_links.append(LinkAction(name, root / name, target=desired_link.target, reason="missing desired symlink"))
    return plan


def existing_symlink_targets(directory: Path | str) -> dict[str, Path]:
    targets: dict[str, Path] = {}
    for entry in current_entries_from_directory(directory):
        if entry.kind == "symlink" and entry.target is not None:
            targets[entry.name] = entry.target
    return targets


def plan_directory(
    scope: str,
    directory: Path | str,
    desired_names: Iterable[str],
    sources: dict[str, Path],
    reusable_targets: dict[str, Path] | None = None,
) -> LinkPlan:
    root = Path(directory)
    desired = desired_links_from_sources(desired_names, sources, reusable_targets)
    return plan_links(scope, root, desired, current_entries_from_directory(root), create_dir=not root.exists())


def dedupe_actions(actions: Iterable[LinkAction]) -> list[LinkAction]:
    seen: set[Path] = set()
    result: list[LinkAction] = []
    for action in actions:
        if action.link in seen:
            continue
        seen.add(action.link)
        result.append(action)
    return result
