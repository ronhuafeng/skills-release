from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from skills_snapshot_plan import SnapshotRecord, plan_directory, tree_digest


def test_snapshot_record_requires_sha256_digests() -> None:
    with pytest.raises(ValueError, match="provenance is incomplete"):
        SnapshotRecord.from_raw(
            "demo",
            {
                "source_alias": "demo",
                "source_digest": "",
                "target_digest": "not-a-digest",
            },
        )


def write_skill(path: Path, description: str = "Demo") -> None:
    path.mkdir(parents=True, exist_ok=True)
    (path / "SKILL.md").write_text(
        f"---\nname: demo\ndescription: {description}.\n---\n"
    )


def test_tree_digest_tracks_content_and_mode_but_ignores_runtime_cache(
    tmp_path: Path,
) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    write_skill(first)
    write_skill(second)
    for root in (first, second):
        (root / "run.sh").write_text("#!/bin/sh\n")
        (root / "run.sh").chmod(0o755)
    (second / ".pytest_cache").mkdir()
    (second / ".pytest_cache" / "noise").write_text("ignored")

    assert tree_digest(first) == tree_digest(second)
    assert tree_digest(first, exclude_ignored=False) != tree_digest(
        second, exclude_ignored=False
    )
    (second / "run.sh").chmod(0o644)
    assert tree_digest(first) != tree_digest(second)


def test_tree_digest_tracks_openai_metadata(tmp_path: Path) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    write_skill(first)
    write_skill(second)
    for root in (first, second):
        (root / "agents").mkdir()
        (root / "agents" / "openai.yaml").write_text(
            "policy:\n  allow_implicit_invocation: false\n"
        )

    assert tree_digest(first) == tree_digest(second)

    (second / "agents" / "openai.yaml").write_text(
        "policy:\n  allow_implicit_invocation: true\n"
    )

    assert tree_digest(first) != tree_digest(second)


def test_tree_digest_rejects_symlink_that_escapes_skill(tmp_path: Path) -> None:
    source = tmp_path / "source"
    write_skill(source)
    (source / "escape").symlink_to("../outside")

    with pytest.raises(ValueError, match="escapes source root"):
        tree_digest(source)


def test_tree_digest_rejects_absolute_symlink(tmp_path: Path) -> None:
    source = tmp_path / "source"
    write_skill(source)
    (source / "absolute").symlink_to(source / "SKILL.md")

    with pytest.raises(ValueError, match="must be relative"):
        tree_digest(source)


def test_tree_digest_rejects_symlink_to_excluded_or_missing_content(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    write_skill(source)
    (source / "__pycache__").mkdir()
    (source / "__pycache__" / "data").write_text("cache")
    (source / "excluded-link").symlink_to("__pycache__/data")

    with pytest.raises(ValueError, match="excluded content"):
        tree_digest(source)

    (source / "excluded-link").unlink()
    (source / "missing-link").symlink_to("missing")
    with pytest.raises(ValueError, match="missing content"):
        tree_digest(source)


def test_plan_refuses_unmanaged_real_directory(tmp_path: Path) -> None:
    source = tmp_path / "source"
    target = tmp_path / "registry" / "demo"
    write_skill(source)
    write_skill(target, "Local")

    plan = plan_directory(target.parent, ["demo"], {"demo": source}, {})

    assert len(plan.conflicts) == 1
    assert "no managed snapshot provenance" in plan.conflicts[0].reason


def test_plan_blocks_missing_or_replaced_managed_snapshot(tmp_path: Path) -> None:
    source = tmp_path / "source"
    registry = tmp_path / "registry"
    target = registry / "demo"
    write_skill(source)
    shutil.copytree(source, target)
    digest = tree_digest(source)
    records = {
        "demo": {
            "source_alias": "demo",
            "source_digest": digest,
            "target_digest": digest,
        }
    }

    shutil.rmtree(target)
    missing = plan_directory(registry, ["demo"], {"demo": source}, records)
    assert len(missing.conflicts) == 1
    assert not missing.create

    target.symlink_to(source)
    replaced = plan_directory(registry, ["demo"], {"demo": source}, records)
    assert len(replaced.conflicts) == 1
    assert not replaced.replace_symlink

    target.unlink()
    missing_during_unvendor = plan_directory(registry, [], {"demo": source}, records)
    assert len(missing_during_unvendor.conflicts) == 1
    assert not missing_during_unvendor.remove


def test_plan_requires_complete_matching_provenance(tmp_path: Path) -> None:
    source = tmp_path / "source"
    target = tmp_path / "registry" / "demo"
    write_skill(source)
    shutil.copytree(source, target)
    digest = tree_digest(source)
    records = {
        "demo": {
            "source_alias": "other",
            "source_digest": digest,
            "target_digest": digest,
        }
    }

    plan = plan_directory(target.parent, ["demo"], {"demo": source}, records)

    assert len(plan.conflicts) == 1
    assert "provenance" in plan.conflicts[0].reason


def test_runtime_cache_is_excluded_from_managed_target_identity(tmp_path: Path) -> None:
    source = tmp_path / "source"
    target = tmp_path / "registry" / "demo"
    write_skill(source)
    shutil.copytree(source, target)
    digest = tree_digest(source)
    records = {
        "demo": {
            "source_alias": "demo",
            "source_digest": digest,
            "target_digest": digest,
        }
    }
    for cache_name in ("__pycache__", ".ruff_cache", ".mypy_cache", ".hg"):
        (target / cache_name).mkdir()
        (target / cache_name / "generated").write_bytes(b"cache")

    plan = plan_directory(target.parent, ["demo"], {"demo": source}, records)

    assert len(plan.unchanged) == 1
    assert not plan.conflicts
