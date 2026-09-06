from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import yaml


ALLOWED_FRONTMATTER_FIELDS = {
    "allowed-tools",
    "description",
    "license",
    "metadata",
    "name",
}
MAX_SKILL_NAME_LENGTH = 64


@dataclass(frozen=True)
class SkillEntry:
    name: str
    kind: str
    target: str | None
    exists: bool
    has_skill: bool
    frontmatter_name: str | None


@dataclass(frozen=True)
class SourceCandidate:
    alias: str
    path: str
    frontmatter_name: str | None


def skill_md_path(skill_md_or_dir: Path | str) -> Path:
    path = Path(skill_md_or_dir)
    return path / "SKILL.md" if path.is_dir() else path


def read_frontmatter(skill_md_or_dir: Path | str) -> dict[str, Any]:
    skill_md = skill_md_path(skill_md_or_dir)
    if not skill_md.exists():
        return {}
    try:
        handle = skill_md.open("r", encoding="utf-8", errors="replace")
    except OSError:
        return {}
    with handle:
        first = handle.readline()
        if first.strip() != "---":
            return {}
        lines: list[str] = []
        for line in handle:
            if line.strip() == "---":
                break
            lines.append(line.rstrip("\n"))
    data: dict[str, Any] = {}
    for line in lines:
        if ":" not in line or line.startswith((" ", "\t")):
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip().strip("\"'")
        if value.lower() == "true":
            data[key] = True
        elif value.lower() == "false":
            data[key] = False
        else:
            data[key] = value
    return data


def _load_frontmatter(skill_md_or_dir: Path | str) -> dict[str, Any]:
    skill_md = skill_md_path(skill_md_or_dir)
    if not skill_md.is_file():
        raise ValueError("SKILL.md not found")
    try:
        content = skill_md.read_text()
    except (OSError, UnicodeError) as exc:
        raise ValueError("SKILL.md is unreadable") from exc
    match = re.match(r"^---\r?\n(.*?)\r?\n---(?:\r?\n|$)", content, re.DOTALL)
    if not match:
        raise ValueError("SKILL.md has invalid YAML frontmatter")
    try:
        frontmatter = yaml.safe_load(match.group(1))
    except yaml.YAMLError as exc:
        raise ValueError("SKILL.md frontmatter contains invalid YAML") from exc
    if not isinstance(frontmatter, dict):
        raise ValueError("SKILL.md frontmatter must be a YAML mapping")
    return frontmatter


def _validate_identity(frontmatter: dict[str, Any]) -> None:
    name = frontmatter.get("name")
    if not isinstance(name, str) or not name.strip():
        raise ValueError("SKILL.md frontmatter name must be a non-empty string")
    normalized_name = name.strip()
    if not re.fullmatch(r"[a-z0-9-]+", normalized_name):
        raise ValueError("SKILL.md frontmatter name must use hyphen-case")
    if (
        normalized_name.startswith("-")
        or normalized_name.endswith("-")
        or "--" in normalized_name
    ):
        raise ValueError(
            "SKILL.md frontmatter name cannot start or end with a hyphen "
            "or contain consecutive hyphens"
        )
    if len(normalized_name) > MAX_SKILL_NAME_LENGTH:
        raise ValueError(
            f"SKILL.md frontmatter name exceeds {MAX_SKILL_NAME_LENGTH} characters"
        )
    description = frontmatter.get("description")
    if not isinstance(description, str) or not description.strip():
        raise ValueError(
            "SKILL.md frontmatter description must be a non-empty string"
        )
    normalized_description = description.strip()
    if "<" in normalized_description or ">" in normalized_description:
        raise ValueError(
            "SKILL.md frontmatter description cannot contain angle brackets"
        )
    if len(normalized_description) > 1024:
        raise ValueError(
            "SKILL.md frontmatter description exceeds 1024 characters"
        )


def validate_identity(skill_md_or_dir: Path | str) -> dict[str, Any]:
    frontmatter = _load_frontmatter(skill_md_or_dir)
    _validate_identity(frontmatter)
    return frontmatter


def validate_frontmatter(skill_md_or_dir: Path | str) -> dict[str, Any]:
    frontmatter = _load_frontmatter(skill_md_or_dir)
    unexpected = sorted(
        str(key) for key in frontmatter if key not in ALLOWED_FRONTMATTER_FIELDS
    )
    if unexpected:
        raise ValueError(
            "unexpected SKILL.md frontmatter field(s): " + ", ".join(unexpected)
        )
    _validate_identity(frontmatter)
    return frontmatter


def skill_entry(path: Path | str) -> SkillEntry:
    resolved = Path(path)
    is_link = resolved.is_symlink()
    target = os.readlink(resolved) if is_link else None
    exists = resolved.exists()
    skill_md = resolved / "SKILL.md"
    has_skill = exists and skill_md.exists()
    frontmatter = read_frontmatter(skill_md) if has_skill else {}
    if is_link:
        kind = "symlink"
    elif resolved.is_dir():
        kind = "directory"
    else:
        kind = "file"
    return SkillEntry(
        name=resolved.name,
        kind=kind,
        target=target,
        exists=exists,
        has_skill=has_skill,
        frontmatter_name=frontmatter.get("name") if isinstance(frontmatter.get("name"), str) else None,
    )


def scan_skill_dir(root: Path | str) -> list[SkillEntry]:
    resolved = Path(root)
    entries: list[SkillEntry] = []
    if not resolved.exists():
        return entries
    for child in sorted(resolved.iterdir(), key=lambda p: p.name):
        if child.name.startswith("."):
            continue
        entries.append(skill_entry(child))
    return entries


def skip_scan_dir(path: Path) -> bool:
    return path.name in {".git", "node_modules", "__pycache__"} or path.name.startswith(".")


def source_candidate(alias: str, path: Path) -> SourceCandidate:
    frontmatter = read_frontmatter(path / "SKILL.md")
    return SourceCandidate(
        alias=alias,
        path=str(path),
        frontmatter_name=frontmatter.get("name") if isinstance(frontmatter.get("name"), str) else None,
    )


def scan_source_roots(roots: Iterable[Path | str]) -> list[SourceCandidate]:
    candidates: list[SourceCandidate] = []
    seen: set[Path] = set()
    for root_like in roots:
        root = Path(root_like).expanduser().resolve(strict=False)
        if not root.exists() or not root.is_dir():
            continue
        stack = [root]
        while stack:
            current = stack.pop()
            resolved = current.resolve(strict=False)
            if resolved in seen:
                continue
            seen.add(resolved)
            if current != root and skip_scan_dir(current):
                continue
            skill_md = current / "SKILL.md"
            if skill_md.exists():
                candidates.append(source_candidate(current.name, current.resolve(strict=False)))
                continue
            if current != root and current.is_symlink():
                continue
            try:
                children = sorted((child for child in current.iterdir() if child.is_dir()), key=lambda p: p.name)
            except OSError:
                continue
            stack.extend(reversed(children))
    return sorted(candidates, key=lambda c: (c.alias, c.path))


def duplicates(candidates: Iterable[SourceCandidate], attr: str) -> dict[str, list[str]]:
    by_key: dict[str, set[str]] = {}
    for candidate in candidates:
        key = getattr(candidate, attr)
        if not key:
            continue
        by_key.setdefault(str(key), set()).add(candidate.path)
    return {key: sorted(paths) for key, paths in sorted(by_key.items()) if len(paths) > 1}
