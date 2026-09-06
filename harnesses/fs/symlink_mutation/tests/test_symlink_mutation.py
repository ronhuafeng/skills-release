from __future__ import annotations

from pathlib import Path

import pytest

from skills_symlink_mutation import apply_plan
from skills_symlink_plan import LinkAction, LinkPlan, plan_directory


def write_skill(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    path.joinpath("SKILL.md").write_text("---\nname: sample\ndescription: Test.\n---\n", encoding="utf-8")


def test_apply_plan_creates_only_desired_symlinks(tmp_path: Path) -> None:
    source = tmp_path / "sources" / "sample"
    write_skill(source)

    plan = plan_directory("global", tmp_path / "skills", ["sample"], {"sample": source}, {})
    apply_plan(plan)

    link = tmp_path / "skills" / "sample"
    assert link.is_symlink()
    assert link.resolve() == source.resolve()


def test_apply_plan_refuses_conflicts(tmp_path: Path) -> None:
    plan = LinkPlan(scope="global", directory=tmp_path)
    plan.conflicts.append(LinkAction("sample", tmp_path / "sample", reason="conflict"))

    with pytest.raises(RuntimeError, match="conflicts prevent apply"):
        apply_plan(plan)


def test_authoritative_plan_replaces_and_removes_real_entries(
    tmp_path: Path,
) -> None:
    source = tmp_path / "sources" / "sample"
    registry = tmp_path / "skills"
    write_skill(source)
    write_skill(registry / "sample")
    write_skill(registry / "stale")
    plan = LinkPlan(
        scope="global",
        directory=registry,
        authoritative=True,
        overwrite_entries=[LinkAction("sample", registry / "sample", source)],
        remove_entries=[LinkAction("stale", registry / "stale")],
    )

    apply_plan(plan)

    assert (registry / "sample").is_symlink()
    assert (registry / "sample").resolve() == source.resolve()
    assert not (registry / "stale").exists()


def test_authoritative_plan_rejects_action_outside_registry(tmp_path: Path) -> None:
    registry = tmp_path / "skills"
    outside = tmp_path / "outside"
    plan = LinkPlan(
        scope="global",
        directory=registry,
        authoritative=True,
        remove_entries=[LinkAction("outside", outside)],
    )

    with pytest.raises(RuntimeError, match="escapes registry"):
        apply_plan(plan)


def test_non_authoritative_plan_cannot_change_real_entries(tmp_path: Path) -> None:
    registry = tmp_path / "skills"
    write_skill(registry / "sample")
    plan = LinkPlan(
        scope="global",
        directory=registry,
        remove_entries=[LinkAction("sample", registry / "sample")],
    )

    with pytest.raises(RuntimeError, match="require an authoritative plan"):
        apply_plan(plan)
