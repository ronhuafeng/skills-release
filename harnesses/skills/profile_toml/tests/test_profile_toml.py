from __future__ import annotations

from pathlib import Path

import pytest

from skills_profile_toml import (
    add_source,
    include_skill,
    remove_source,
    render_profile,
    repo_vendors,
    source_map,
    validate_source_path,
    vendor_skill,
)


def write_skill(path: Path, name: str = "sample") -> None:
    path.mkdir(parents=True, exist_ok=True)
    path.joinpath("SKILL.md").write_text(
        f"---\nname: {name}\ndescription: Test skill.\n---\n\n# Test\n",
        encoding="utf-8",
    )


def test_profile_edit_validates_sources_and_writes_canonical_toml(
    tmp_path: Path,
) -> None:
    source = tmp_path / "sources" / "sample"
    write_skill(source, name="frontmatter-name")
    profile: dict = {}

    changes = add_source(profile, "sample", source)
    assert any("differs from frontmatter name" in change for change in changes)

    include_skill(profile, "sample", global_scope=True)
    rendered = render_profile(profile)

    assert "[sources]" in rendered
    assert '[global]\ninclude = ["sample"]' in rendered
    assert source_map(profile)["sample"] == source.resolve()


def test_source_path_validation_does_not_own_skill_metadata_policy(
    tmp_path: Path,
) -> None:
    source = tmp_path / "sources" / "sample"
    source.mkdir(parents=True)
    (source / "SKILL.md").write_text(
        "---\nname: Sample\nlegacy-field: true\n---\n",
        encoding="utf-8",
    )

    assert validate_source_path(source) == source.resolve()


def test_include_without_source_reports_warning(tmp_path: Path) -> None:
    profile: dict = {}

    changes = include_skill(profile, "sample", global_scope=True)

    assert "has no [sources] mapping" in changes[1]
    assert '[global]\ninclude = ["sample"]' in render_profile(profile)


def test_remove_source_is_idempotent_and_preserves_includes(tmp_path: Path) -> None:
    source = tmp_path / "sources" / "sample"
    write_skill(source)
    profile: dict = {}
    add_source(profile, "sample", source)
    include_skill(profile, "sample", global_scope=True)

    assert remove_source(profile, "sample") == [
        f"remove source sample -> {source.resolve()}"
    ]
    assert remove_source(profile, "sample") == ["source sample already absent"]
    assert source_map(profile) == {}
    assert '[global]\ninclude = ["sample"]' in render_profile(profile)


def test_repo_vendor_is_canonical_and_exclusive_with_symlink_include(
    tmp_path: Path,
) -> None:
    source = tmp_path / "sources" / "sample"
    write_skill(source)
    repo = tmp_path / "repo"
    repo.mkdir()
    profile: dict = {}
    add_source(profile, "sample", source)

    assert vendor_skill(profile, "sample", repo=repo) == [
        f"vendor sample in repo {repo.resolve()}"
    ]
    assert repo_vendors(profile, repo) == {str(repo.resolve()): ["sample"]}
    assert 'vendor = ["sample"]' in render_profile(profile)

    with pytest.raises(ValueError, match="already vendored"):
        include_skill(profile, "sample", repo=repo)
