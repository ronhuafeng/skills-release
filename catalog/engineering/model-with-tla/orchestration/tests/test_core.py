from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from model_with_tla_orchestration.core import (
    CheckInputError,
    ToolPrerequisiteError,
    check_model,
    classify_sany,
    classify_tlc,
    parse_expectation,
)


SKILL_DIRECTORY = Path(__file__).resolve().parents[2]


def supported_java() -> Path | None:
    candidates = [os.environ.get("TLA_JAVA"), shutil.which("java")]
    for raw in candidates:
        if not raw:
            continue
        completed = subprocess.run(
            [raw, "-version"], text=True, capture_output=True, check=False
        )
        output = completed.stderr or completed.stdout
        match = re.search(r'version "([0-9]+)(?:\.([0-9]+))?', output)
        if match is None:
            continue
        first = int(match.group(1))
        major = int(match.group(2)) if first == 1 and match.group(2) else first
        if major >= 11:
            return Path(raw)
    return None


JAVA = supported_java()
requires_java = pytest.mark.skipif(JAVA is None, reason="Java 11+ is unavailable")


def write_model(tmp_path: Path, module: str, body: str, config: str) -> tuple[Path, Path]:
    module_path = tmp_path / f"{module}.tla"
    config_path = tmp_path / f"{module}.cfg"
    module_path.write_text(f"---- MODULE {module} ----\n{body}\n====\n")
    config_path.write_text(config)
    return module_path, config_path


def test_expectation_parser_requires_an_exact_invariant_name() -> None:
    assert parse_expectation("success") == "success"
    assert parse_expectation("invariant:NoDuplicate") == "invariant:NoDuplicate"
    with pytest.raises(CheckInputError):
        parse_expectation("invariant:")
    with pytest.raises(CheckInputError):
        parse_expectation("failure")


def test_tlc_classification_distinguishes_expected_failures() -> None:
    assert (
        classify_tlc("Error: Invariant NoDuplicate is violated.", 12)
        == "invariant:NoDuplicate"
    )
    assert classify_tlc("Error: Temporal properties were violated.", 13) == "temporal"
    assert classify_tlc("Error: Deadlock reached.", 11) == "deadlock"
    assert classify_tlc("unexpected", 150) == "tool-error"


def test_sany_classification_does_not_treat_every_failure_as_semantic() -> None:
    assert classify_sany("Semantic errors: 1", 1) == "semantic-error"
    assert classify_sany("Error: Could not find or load main class", 1) == "tool-error"
    assert classify_sany("", 0) == "semantic-success"


def test_toolchain_rejects_a_changed_bundled_jar(tmp_path: Path) -> None:
    tools = tmp_path / ".tools"
    tools.mkdir()
    jar = tools / "tla2tools.jar"
    jar.write_bytes(b"changed")
    (tools / "toolchain.json").write_text(
        json.dumps(
            {
                "schemaVersion": 1,
                "version": "test",
                "sha256": hashlib.sha256(b"expected").hexdigest(),
                "revision": "0" * 40,
                "buildTimestamp": "test",
                "minimumJavaMajor": 11,
                "prerelease": False,
            }
        )
    )
    module, config = write_model(
        tmp_path,
        "Valid",
        "VARIABLE x\nInit == x = 0\nNext == x' = x\nSpec == Init /\\ [][Next]_<<x>>",
        "SPECIFICATION Spec\nCHECK_DEADLOCK FALSE\n",
    )
    with pytest.raises(ToolPrerequisiteError, match="checksum does not match"):
        check_model(
            module=module,
            config=config,
            expectation="success",
            java=JAVA,
            skill_directory=tmp_path,
        )


@requires_java
def test_real_checker_matches_success_violation_and_semantic_error(tmp_path: Path) -> None:
    valid, valid_config = write_model(
        tmp_path,
        "Valid",
        "VARIABLE x\nInit == x = 0\nNext == x' = x\nSpec == Init /\\ [][Next]_<<x>>\nTypeOK == x = 0",
        "SPECIFICATION Spec\nCHECK_DEADLOCK FALSE\nINVARIANT TypeOK\n",
    )
    success = check_model(
        module=valid,
        config=valid_config,
        expectation="success",
        java=JAVA,
        skill_directory=SKILL_DIRECTORY,
    )
    assert success.status == "matched"
    assert success.observed == "success"
    assert success.generated_states == 2
    assert success.distinct_states == 1
    assert success.tlc_version is not None
    assert not (tmp_path / "states").exists()

    faulty, faulty_config = write_model(
        tmp_path,
        "Faulty",
        "VARIABLE x\nInit == x = 0\nNext == x' = 1\nSpec == Init /\\ [][Next]_<<x>>\nAlwaysZero == x = 0",
        "SPECIFICATION Spec\nCHECK_DEADLOCK FALSE\nINVARIANT AlwaysZero\n",
    )
    violation = check_model(
        module=faulty,
        config=faulty_config,
        expectation="invariant:AlwaysZero",
        java=JAVA,
        skill_directory=SKILL_DIRECTORY,
    )
    assert violation.status == "matched"
    assert violation.observed == "invariant:AlwaysZero"
    assert "State 2" in (violation.diagnostics or "")
    assert str(tmp_path) not in (violation.diagnostics or "")
    assert str(SKILL_DIRECTORY) not in (violation.diagnostics or "")
    assert not list(tmp_path.glob("*_TTrace_*"))

    wrong_property = check_model(
        module=faulty,
        config=faulty_config,
        expectation="invariant:OtherInvariant",
        java=JAVA,
        skill_directory=SKILL_DIRECTORY,
    )
    assert wrong_property.status == "mismatch"
    assert wrong_property.observed == "invariant:AlwaysZero"

    semantic = tmp_path / "SemanticError.tla"
    semantic.write_text(
        "---- MODULE SemanticError ----\nVARIABLE x\nInit == x = Missing\n"
        "Next == x' = x\nSpec == Init /\\ [][Next]_<<x>>\n====\n"
    )
    rejected = check_model(
        module=semantic,
        config=None,
        expectation="semantic-error",
        java=JAVA,
        skill_directory=SKILL_DIRECTORY,
    )
    assert rejected.status == "matched"
    assert rejected.observed == "semantic-error"


@requires_java
def test_fixed_toolchain_passes_upstream_fcnlambda_except_reproducer(tmp_path: Path) -> None:
    module, config = write_model(
        tmp_path,
        "Github1302c",
        """EXTENDS TLC, TLCExt
S == [{1} -> {1, 2}]
I == [s \\in S |-> 0]
r1 == [i \\in {1} |-> 1]
r2 == [i \\in {1} |-> 2]
fcn == r1 :> 10
VARIABLES x, y
Init ==
  /\\ x = [I EXCEPT ![r1] = fcn]
  /\\ y = [x EXCEPT ![r2] = 99]
Next == UNCHANGED <<x, y>>
correct == [([([s \\in S |-> 0]) EXCEPT ![r1] = fcn]) EXCEPT ![r2] = 99]
Inv == TLCFP(y) = TLCFP(correct)""",
        "INIT Init\nNEXT Next\nINVARIANT Inv\n",
    )
    result = check_model(
        module=module,
        config=config,
        expectation="success",
        java=JAVA,
        skill_directory=SKILL_DIRECTORY,
    )
    assert result.status == "matched"
    assert result.observed == "success"
