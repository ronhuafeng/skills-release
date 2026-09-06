from __future__ import annotations

from pathlib import Path

from skills_symlink_plan import DesiredLink, LinkAction, CurrentEntry, dedupe_actions, plan_directory, plan_links


def write_skill(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    path.joinpath("SKILL.md").write_text("---\nname: sample\ndescription: Test.\n---\n", encoding="utf-8")


def test_plan_links_is_pure_over_desired_and_current(tmp_path: Path) -> None:
    source = tmp_path / "source"
    link = tmp_path / "skills" / "sample"

    plan = plan_links(
        "global",
        tmp_path / "skills",
        [DesiredLink("sample", source)],
        [CurrentEntry("sample", link, "file")],
    )

    assert [action.name for action in plan.conflicts] == ["sample"]
    assert not plan.create_links


def test_desired_real_skill_directory_is_a_conflict(tmp_path: Path) -> None:
    source = tmp_path / "source"
    existing = tmp_path / "skills" / "sample"

    plan = plan_links(
        "global",
        tmp_path / "skills",
        [DesiredLink("sample", source)],
        [CurrentEntry("sample", existing, "directory", has_skill=True)],
    )

    assert [action.name for action in plan.conflicts] == ["sample"]
    assert not plan.unchanged


def test_plan_directory_creates_missing_desired_symlink(tmp_path: Path) -> None:
    source = tmp_path / "source" / "sample"
    write_skill(source)

    plan = plan_directory("global", tmp_path / "skills", ["sample"], {"sample": source}, {})

    assert plan.create_dir is True
    assert [action.name for action in plan.create_links] == ["sample"]
    assert plan.create_links[0].target == source


def test_dedupe_actions_keeps_first_link_action(tmp_path: Path) -> None:
    first = LinkAction("sample", tmp_path / "sample", reason="first")
    second = LinkAction("sample", tmp_path / "sample", reason="second")

    assert dedupe_actions([first, second]) == [first]
