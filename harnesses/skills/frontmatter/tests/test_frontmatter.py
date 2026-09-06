from __future__ import annotations

from pathlib import Path

import pytest

from skills_frontmatter import (
    read_frontmatter,
    scan_source_roots,
    scan_skill_dir,
    validate_frontmatter,
    validate_identity,
)


def write_skill(path: Path, name: str = "sample", description: str = "Test skill.") -> None:
    path.mkdir(parents=True, exist_ok=True)
    path.joinpath("SKILL.md").write_text(
        f"---\nname: {name}\ndescription: {description}\n---\n\n# Test\n",
        encoding="utf-8",
    )


def test_read_frontmatter_from_skill_dir(tmp_path: Path) -> None:
    skill = tmp_path / "sample"
    write_skill(skill)

    assert read_frontmatter(skill)["name"] == "sample"
    assert read_frontmatter(skill)["description"] == "Test skill."


def test_scan_skill_dir_reports_entries(tmp_path: Path) -> None:
    write_skill(tmp_path / "sample")

    entries = scan_skill_dir(tmp_path)

    assert entries[0].name == "sample"
    assert entries[0].frontmatter_name == "sample"


def test_scan_source_roots_finds_skill_frontmatter(tmp_path: Path) -> None:
    root = tmp_path / "catalog"
    write_skill(root / "group" / "sample")

    candidates = scan_source_roots([root])

    assert len(candidates) == 1
    assert candidates[0].alias == "sample"
    assert candidates[0].frontmatter_name == "sample"


def test_validate_frontmatter_accepts_official_fields(tmp_path: Path) -> None:
    skill = tmp_path / "sample"
    write_skill(skill)
    skill_md = skill / "SKILL.md"
    skill_md.write_text(
        skill_md.read_text().replace(
            "description: Test skill.\n",
            "description: Test skill.\nlicense: MIT\nmetadata:\n  owner: test\n",
        )
    )

    assert validate_frontmatter(skill)["name"] == "sample"


def test_validate_identity_accepts_non_identity_fields(tmp_path: Path) -> None:
    skill = tmp_path / "sample"
    write_skill(skill)
    skill_md = skill / "SKILL.md"
    skill_md.write_text(
        skill_md.read_text().replace(
            "description: Test skill.\n",
            "description: Test skill.\ndisable-model-invocation: true\n",
        )
    )

    identity = validate_identity(skill)

    assert identity["name"] == "sample"
    assert identity["description"] == "Test skill."


@pytest.mark.parametrize(
    ("frontmatter", "message"),
    [
        (
            "name: sample\ndescription: Test skill.\nunsupported-field: true",
            "unexpected SKILL.md frontmatter field",
        ),
        ("name: Sample\ndescription: Test skill.", "name must use hyphen-case"),
        ("name: sample", "description must be a non-empty string"),
        (
            "name: sample\ndescription: Invalid <description>.",
            "description cannot contain angle brackets",
        ),
    ],
)
def test_validate_frontmatter_rejects_invalid_schema(
    tmp_path: Path, frontmatter: str, message: str
) -> None:
    skill = tmp_path / "sample"
    skill.mkdir()
    (skill / "SKILL.md").write_text(f"---\n{frontmatter}\n---\n")

    with pytest.raises(ValueError, match=message):
        validate_frontmatter(skill)
