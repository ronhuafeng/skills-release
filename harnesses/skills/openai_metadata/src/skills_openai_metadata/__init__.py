from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass(frozen=True)
class OpenAIMetadata:
    present: bool
    allow_implicit_invocation: bool | None
    errors: tuple[str, ...]


def inspect_openai_metadata(skill_dir: Path | str) -> OpenAIMetadata:
    metadata_path = Path(skill_dir) / "agents" / "openai.yaml"
    present = metadata_path.exists() or metadata_path.is_symlink()
    if not present:
        return OpenAIMetadata(False, True, ())
    if not metadata_path.is_file():
        return OpenAIMetadata(
            True, None, ("agents/openai.yaml is not a readable file",)
        )
    try:
        metadata = yaml.safe_load(metadata_path.read_text())
    except (OSError, UnicodeError, yaml.YAMLError):
        return OpenAIMetadata(
            True,
            None,
            ("agents/openai.yaml is unreadable or contains invalid YAML",),
        )
    if not isinstance(metadata, dict):
        return OpenAIMetadata(
            True, None, ("agents/openai.yaml must contain a YAML mapping",)
        )
    policy = metadata.get("policy", {})
    if not isinstance(policy, dict):
        return OpenAIMetadata(
            True, None, ("agents/openai.yaml policy must be a YAML mapping",)
        )
    if "allow_implicit_invocation" in policy and not isinstance(
        policy["allow_implicit_invocation"], bool
    ):
        return OpenAIMetadata(
            True,
            None,
            (
                "agents/openai.yaml "
                "policy.allow_implicit_invocation must be a boolean",
            ),
        )
    return OpenAIMetadata(
        True,
        policy.get("allow_implicit_invocation", True),
        (),
    )


def validate_openai_metadata(skill_dir: Path | str) -> OpenAIMetadata:
    metadata = inspect_openai_metadata(skill_dir)
    if metadata.errors:
        raise ValueError(metadata.errors[0])
    return metadata


__all__ = [
    "OpenAIMetadata",
    "inspect_openai_metadata",
    "validate_openai_metadata",
]
