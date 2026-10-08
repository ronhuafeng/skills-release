from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from plugin_build.release_status import (
    ReleaseError,
    ReleaseRecord,
    current_publication,
    publication_status,
    read_openai_marketplace,
)


def subprocess_commit(repo: Path) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
    )
    return result.stdout.decode().strip()


def record(version: str = "0.1.0", commit: str = "a" * 40, digest: str = "zip-a", surface: str = "public") -> ReleaseRecord:
    return ReleaseRecord(version=version, source_commit=commit, zip_sha256=digest, surface=surface)


def status(**overrides: object):
    evidence = {
        "source_merged": True,
        "source_commit": "a" * 40,
        "repository_release": "0.2.0",
        "built_version": "0.1.0",
        "built_commit": "a" * 40,
        "built_zip_sha256": "zip-a",
        "distribution_passed": False,
        "activation_status": "unavailable",
        "bounded_surface": None,
        "release_notes": None,
        "approval": None,
        "publication": None,
        "prior_publication": None,
    }
    evidence.update(overrides)
    return publication_status(**evidence)


def test_source_merge_without_a_package_is_not_a_plugin_release() -> None:
    report = status(built_version=None, built_commit=None, built_zip_sha256=None)

    assert report.state == "source_merged"
    assert report.plugin_release is False
    assert report.package_version is None
    assert report.zip_sha256 is None
    assert report.surface is None
    assert report.package_version != report.repository_release


def test_built_package_is_not_public_when_activation_is_unavailable() -> None:
    report = status(distribution_passed=True, activation_status="unavailable")

    assert report.state == "package_built"
    assert report.plugin_release is False
    assert report.surface is None
    assert report.package_version == "0.1.0"
    assert report.zip_sha256 == "zip-a"
    assert report.source_commit == "a" * 40


def test_workspace_distribution_is_not_public() -> None:
    report = status(
        distribution_passed=True,
        activation_status="passed",
        bounded_surface="workspace",
    )

    assert report.state == "bounded_distribution"
    assert report.surface == "workspace"
    assert report.plugin_release is False


def test_public_publication_needs_its_own_matching_artifact() -> None:
    notes = "ronhuafeng-engineering 0.1.0\n\nPositive: reduce context.\nNegative: do not answer weather.\n"
    approval = record(surface="directory-review")
    publication = record(surface="public")
    report = status(
        distribution_passed=True,
        activation_status="passed",
        bounded_surface="workspace",
        release_notes=notes,
        approval=approval,
        publication=publication,
    )

    assert report.state == "public_published"
    assert report.plugin_release is True
    assert report.surface == "public"
    assert report.zip_sha256 == "zip-a"


def test_same_version_cannot_replace_a_published_zip() -> None:
    with pytest.raises(ReleaseError) as caught:
        status(
            built_zip_sha256="zip-b",
            prior_publication=record(),
        )

    assert caught.value.code == "immutable_artifact"


def test_repository_marketplace_points_at_the_built_package_without_skill_copies() -> None:
    repo = Path(__file__).resolve().parents[3]
    marketplace = read_openai_marketplace(repo)
    claude = json.loads((repo / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8"))

    assert marketplace["plugins"][0]["source"]["path"] == "./dist/plugins/ronhuafeng-engineering"
    assert marketplace["plugins"][0]["source"]["source"] == "local"
    assert not (repo / ".agents" / "plugins" / "skills").exists()
    assert claude["plugins"][0]["source"] == "./"
    assert claude["plugins"][0]["source"] != marketplace["plugins"][0]["source"]["path"]


def test_repository_publication_answers_identity_and_surface() -> None:
    repo = Path(__file__).resolve().parents[3]
    report = current_publication(repo)
    commit = subprocess_commit(repo)

    assert report.source_commit == commit
    assert report.package_version == "0.1.0"
    assert report.repository_release == "0.2.0"
    assert report.package_version != report.repository_release
    assert report.surface == "./dist/plugins/ronhuafeng-engineering"
    assert report.plugin_release is False
    assert report.state != "public_published"
    assert report.state != "public_approved"
