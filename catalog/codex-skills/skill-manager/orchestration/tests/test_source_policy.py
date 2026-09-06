from __future__ import annotations

from pathlib import Path

from skills_skill_manager_orchestration.source_policy import (
    inspect_link_source,
    validate_link_source,
)


def write_legacy_skill(path: Path) -> None:
    path.mkdir(parents=True)
    (path / "SKILL.md").write_text(
        "---\n"
        "name: demo\n"
        "description: Demo skill.\n"
        "disable-model-invocation: true\n"
        "---\n",
        encoding="utf-8",
    )
    metadata = path / "agents" / "openai.yaml"
    metadata.parent.mkdir()
    metadata.write_text(
        "policy:\n  allow_implicit_invocation: false\n",
        encoding="utf-8",
    )


def test_link_policy_accepts_identity_and_uses_openai_invocation_policy(
    tmp_path: Path,
) -> None:
    source = tmp_path / "demo"
    write_legacy_skill(source)

    qualification = validate_link_source(source)

    assert qualification.frontmatter is not None
    assert qualification.openai_metadata.allow_implicit_invocation is False


def test_link_inspection_reports_identity_and_invocation_errors(
    tmp_path: Path,
) -> None:
    source = tmp_path / "demo"
    source.mkdir()
    (source / "SKILL.md").write_text(
        "---\nname: Demo\ndescription: Demo skill.\n---\n",
        encoding="utf-8",
    )
    metadata = source / "agents" / "openai.yaml"
    metadata.parent.mkdir()
    metadata.write_text(
        "policy:\n  allow_implicit_invocation: invalid\n",
        encoding="utf-8",
    )

    qualification = inspect_link_source(source)

    assert qualification.valid is False
    assert qualification.errors == (
        "SKILL.md frontmatter name must use hyphen-case",
        "agents/openai.yaml policy.allow_implicit_invocation must be a boolean",
    )
