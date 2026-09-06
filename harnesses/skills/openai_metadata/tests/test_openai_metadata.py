from pathlib import Path

import pytest

from skills_openai_metadata import (
    inspect_openai_metadata,
    validate_openai_metadata,
)


def test_missing_metadata_uses_implicit_invocation_default(tmp_path: Path) -> None:
    metadata = inspect_openai_metadata(tmp_path)

    assert metadata.present is False
    assert metadata.allow_implicit_invocation is True
    assert metadata.errors == ()


def test_explicit_invocation_policy_is_reported(tmp_path: Path) -> None:
    path = tmp_path / "agents" / "openai.yaml"
    path.parent.mkdir()
    path.write_text("policy:\n  allow_implicit_invocation: false\n")

    metadata = validate_openai_metadata(tmp_path)

    assert metadata.present is True
    assert metadata.allow_implicit_invocation is False


def test_null_invocation_policy_is_invalid(tmp_path: Path) -> None:
    path = tmp_path / "agents" / "openai.yaml"
    path.parent.mkdir()
    path.write_text("policy:\n  allow_implicit_invocation: null\n")

    with pytest.raises(
        ValueError,
        match=(
            "agents/openai.yaml policy.allow_implicit_invocation must be a boolean"
        ),
    ):
        validate_openai_metadata(tmp_path)


@pytest.mark.parametrize(
    ("content", "message"),
    [
        ("policy: [", "unreadable or contains invalid YAML"),
        ("- policy", "must contain a YAML mapping"),
        ("policy: false\n", "policy must be a YAML mapping"),
    ],
)
def test_invalid_metadata_shapes_are_rejected(
    tmp_path: Path, content: str, message: str
) -> None:
    path = tmp_path / "agents" / "openai.yaml"
    path.parent.mkdir()
    path.write_text(content)

    with pytest.raises(ValueError, match=message):
        validate_openai_metadata(tmp_path)


def test_non_file_metadata_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "agents" / "openai.yaml"
    path.mkdir(parents=True)

    with pytest.raises(ValueError, match="is not a readable file"):
        validate_openai_metadata(tmp_path)
