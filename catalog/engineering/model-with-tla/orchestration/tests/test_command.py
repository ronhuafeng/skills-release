from __future__ import annotations

import json

import pytest

from model_with_tla_orchestration.__main__ import main
from model_with_tla_orchestration.core import CheckResult


def test_command_rejects_an_unknown_expectation(capsys) -> None:
    exit_code = main(
        [
            "check",
            "--module",
            "/missing/Model.tla",
            "--expect",
            "anything",
        ]
    )
    assert exit_code == 2
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "invalid"
    assert result["error"] == "unsupported expectation: anything"


@pytest.mark.parametrize(
    ("status", "expected_exit"),
    [("matched", 0), ("mismatch", 4), ("tool-error", 3)],
)
def test_command_exit_status_follows_the_structured_result(
    monkeypatch, capsys, status: str, expected_exit: int
) -> None:
    result = CheckResult(
        schema_version=1,
        status=status,
        expected="success",
        observed="success" if status == "matched" else "tool-error",
        module="Model.tla",
        config="Model.cfg",
        tool_version="test",
        tool_revision="0" * 40,
        tool_build_timestamp="test",
        tlc_version=None,
        tool_prerelease=True,
        tool_sha256="0" * 64,
        java_version='openjdk version "26"',
        generated_states=None,
        distinct_states=None,
        depth=None,
        duration_ms=1,
        diagnostics=None,
        diagnostics_truncated=False,
    )
    monkeypatch.setattr(
        "model_with_tla_orchestration.__main__.check_model", lambda **_: result
    )
    exit_code = main(
        [
            "check",
            "--module",
            "/does/not/matter.tla",
            "--config",
            "/does/not/matter.cfg",
            "--expect",
            "success",
        ]
    )
    assert exit_code == expected_exit
    assert json.loads(capsys.readouterr().out)["status"] == status
