from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from skills_frontmatter import validate_identity
from skills_openai_metadata import OpenAIMetadata, inspect_openai_metadata
from skills_profile_toml import validate_source_path


@dataclass(frozen=True)
class SkillSourceQualification:
    frontmatter: dict[str, Any] | None
    openai_metadata: OpenAIMetadata
    errors: tuple[str, ...]

    @property
    def valid(self) -> bool:
        return not self.errors


def _inspect_source(
    path: Path | str,
    frontmatter_validator: Callable[[Path | str], dict[str, Any]],
) -> SkillSourceQualification:
    errors: list[str] = []
    frontmatter: dict[str, Any] | None = None
    try:
        source = validate_source_path(path)
        frontmatter = frontmatter_validator(source)
    except ValueError as exc:
        message = str(exc)
        if message.startswith("source path "):
            message = message.split(": ", 1)[0]
        errors.append(message)
    metadata = inspect_openai_metadata(path)
    errors.extend(metadata.errors)
    return SkillSourceQualification(
        frontmatter=frontmatter,
        openai_metadata=metadata,
        errors=tuple(errors),
    )


def inspect_link_source(path: Path | str) -> SkillSourceQualification:
    return _inspect_source(path, validate_identity)


def _require(
    qualification: SkillSourceQualification,
) -> SkillSourceQualification:
    if qualification.errors:
        raise ValueError(qualification.errors[0])
    return qualification


def validate_link_source(path: Path | str) -> SkillSourceQualification:
    return _require(inspect_link_source(path))


def validate_snapshot_source(path: Path | str) -> SkillSourceQualification:
    return _require(_inspect_source(path, validate_identity))


def validate_fleet_source(path: Path | str) -> SkillSourceQualification:
    return _require(_inspect_source(path, validate_identity))


__all__ = [
    "SkillSourceQualification",
    "inspect_link_source",
    "validate_fleet_source",
    "validate_link_source",
    "validate_snapshot_source",
]
