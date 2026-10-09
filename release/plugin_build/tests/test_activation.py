from __future__ import annotations

import json
from pathlib import Path

import pytest

from plugin_build.activation import ActivationError, evaluate_activation
from test_build import make_repo, recommit, write_json


def sample_cases() -> list[dict]:
    return [
        {
            "id": "direct-alpha",
            "kind": "direct",
            "prompt": "Reduce the context for this change.",
            "expected_skill": "alpha",
        },
        {
            "id": "indirect-alpha",
            "kind": "indirect",
            "prompt": "Keep only the facts needed to edit this module safely.",
            "expected_skill": "alpha",
        },
        {
            "id": "negative-weather",
            "kind": "negative",
            "prompt": "What is the weather tomorrow?",
            "expected_skill": None,
        },
        {
            "id": "follow-alpha",
            "kind": "follow_up",
            "follows": "direct-alpha",
            "prompt": "Continue that reduction and do not add new scope.",
            "expected_skill": "alpha",
        },
        {
            "id": "unsupported-publish",
            "kind": "unsupported",
            "prompt": "Publish this package to the public directory now.",
            "expected_skill": None,
        },
    ]


def commit_golden(repo: Path, cases: list[dict] | None = None) -> str:
    path = repo / "release" / "plugins" / "engineering" / "activation" / "golden-prompts.json"
    write_json(path, {"cases": sample_cases() if cases is None else cases})
    return recommit(repo, "add golden prompts")


def test_live_activation_is_unavailable_without_a_surface(tmp_path: Path) -> None:
    repo, _commit = make_repo(tmp_path)
    commit = commit_golden(repo)

    report = evaluate_activation(repo)

    assert report.status == "unavailable"
    assert report.surface is None
    assert report.package_version == "0.1.0"
    assert report.source_commit == commit
    assert report.mismatches == ()
    assert [case.kind for case in report.cases] == [
        "direct",
        "indirect",
        "negative",
        "follow_up",
        "unsupported",
    ]
    assert all(case.expected_skill not in case.prompt for case in report.cases if case.expected_skill)


def test_behavior_mismatch_fails_even_when_the_package_exists(tmp_path: Path) -> None:
    repo, _commit = make_repo(tmp_path)
    commit_golden(repo)
    results = {
        "direct-alpha": None,
        "indirect-alpha": "alpha",
        "negative-weather": None,
        "follow-alpha": "alpha",
        "unsupported-publish": None,
    }

    report = evaluate_activation(repo, live_results=results, surface="codex-test")

    assert report.status == "failed"
    assert report.surface == "codex-test"
    assert report.mismatches == ("direct-alpha",)


def test_matching_live_results_pass_only_for_the_named_surface(tmp_path: Path) -> None:
    repo, _commit = make_repo(tmp_path)
    commit_golden(repo)
    results = {
        "direct-alpha": "alpha",
        "indirect-alpha": "alpha",
        "negative-weather": None,
        "follow-alpha": "alpha",
        "unsupported-publish": None,
    }

    report = evaluate_activation(repo, live_results=results, surface="codex-test")

    assert report.status == "passed"
    assert report.surface == "codex-test"
    assert report.mismatches == ()


def test_prompt_cannot_contain_the_expected_skill(tmp_path: Path) -> None:
    repo, _commit = make_repo(tmp_path)
    cases = sample_cases()
    cases[0]["prompt"] = "Run alpha now."
    commit_golden(repo, cases)

    with pytest.raises(ActivationError) as caught:
        evaluate_activation(repo)

    assert caught.value.code == "invalid_golden"


def test_repository_golden_set_reports_live_activation_unavailable() -> None:
    repo = Path(__file__).resolve().parents[3]

    report = evaluate_activation(repo)

    assert report.status == "unavailable"
    assert report.package_version == json.loads((repo / ".codex-plugin/plugin.json").read_text())["version"]
    kinds = {case.kind for case in report.cases}
    assert kinds == {"direct", "indirect", "negative", "follow_up", "unsupported"}
    assert any(case.kind == "negative" and case.expected_skill is None for case in report.cases)
    for case in report.cases:
        if case.expected_skill is not None:
            assert case.expected_skill.casefold() not in case.prompt.casefold()


def test_distribution_and_activation_are_separate_jobs() -> None:
    workflow = Path(__file__).resolve().parents[3] / ".github" / "workflows" / "verify.yml"
    text = workflow.read_text(encoding="utf-8")
    assert text.count("name: Plugin distribution contracts") == 1
    assert text.count("name: Plugin activation evaluation") == 1
    distribution, remainder = text.split("name: Plugin activation evaluation", 1)
    activation, release = remainder.split("plugin-release:", 1)

    assert "name: Plugin distribution contracts" in distribution
    assert "release/plugin_build/tests/test_marketplace.py" in distribution
    assert "release/plugin_build/tests/test_build.py" not in distribution
    assert "plugin_build.activation" not in distribution
    assert "python -m plugin_build.activation" in activation
    assert "test_build.py" not in activation
    assert "release/plugin_build/tests/test_build.py" in release


def test_activation_does_not_require_optional_zip_metadata(tmp_path: Path) -> None:
    repo, _commit = make_repo(tmp_path)
    commit_golden(repo)
    (repo / "release/plugins/engineering/source.json").unlink()
    assert evaluate_activation(repo).status == "unavailable"
