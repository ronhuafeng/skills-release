from __future__ import annotations

from pathlib import Path

import pytest

from skills_snapshot_mutation import apply_plan
from skills_snapshot_plan import (
    SnapshotAction,
    SnapshotPlan,
    plan_directory,
    tree_digest,
)


def write_skill(path: Path, description: str = "Demo") -> None:
    path.mkdir(parents=True, exist_ok=True)
    (path / "SKILL.md").write_text(
        f"---\nname: demo\ndescription: {description}.\n---\n"
    )


def test_apply_snapshot_plan_creates_real_directory(tmp_path: Path) -> None:
    source = tmp_path / "source"
    registry = tmp_path / "registry"
    write_skill(source)
    plan = plan_directory(registry, ["demo"], {"demo": source}, {})

    apply_plan(plan)

    assert (registry / "demo").is_dir()
    assert not (registry / "demo").is_symlink()
    assert tree_digest(registry / "demo") == tree_digest(source)


def test_apply_snapshot_plan_refuses_conflicts(tmp_path: Path) -> None:
    plan = SnapshotPlan(directory=tmp_path)
    plan.conflicts.append(
        SnapshotAction("demo", None, tmp_path / "demo", reason="conflict")
    )

    with pytest.raises(RuntimeError, match="conflicts prevent apply"):
        apply_plan(plan)


def test_authoritative_plan_overwrites_drift_and_removes_real_entry(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    registry = tmp_path / "registry"
    target = registry / "demo"
    stale = registry / "stale"
    write_skill(source, "Current")
    write_skill(target, "Drifted")
    write_skill(stale, "Stale")
    plan = SnapshotPlan(
        directory=registry,
        authoritative=True,
        overwrite=[
            SnapshotAction(
                "demo",
                source,
                target,
                source_digest=tree_digest(source),
            )
        ],
        remove=[SnapshotAction("stale", None, stale)],
    )

    apply_plan(plan)

    assert tree_digest(target) == tree_digest(source)
    assert not stale.exists()


def test_authoritative_plan_rejects_action_outside_registry(tmp_path: Path) -> None:
    registry = tmp_path / "registry"
    plan = SnapshotPlan(
        directory=registry,
        authoritative=True,
        remove=[SnapshotAction("outside", None, tmp_path / "outside")],
    )

    with pytest.raises(RuntimeError, match="escapes registry"):
        apply_plan(plan)


def test_non_authoritative_plan_cannot_overwrite_snapshot(tmp_path: Path) -> None:
    source = tmp_path / "source"
    registry = tmp_path / "registry"
    write_skill(source)
    plan = SnapshotPlan(
        directory=registry,
        overwrite=[
            SnapshotAction(
                "demo",
                source,
                registry / "demo",
                source_digest=tree_digest(source),
            )
        ],
    )

    with pytest.raises(RuntimeError, match="requires an authoritative plan"):
        apply_plan(plan)
