from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path

GOLDEN_RELATIVE = Path("release/plugins/engineering/activation/golden-prompts.json")
SOURCE_RELATIVE = Path("release/plugins/engineering/source.json")
KINDS = {"direct", "indirect", "negative", "follow_up", "unsupported"}
SELECTING_KINDS = {"direct", "indirect", "follow_up"}
ABSTAINING_KINDS = {"negative", "unsupported"}


class ActivationError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class GoldenCase:
    case_id: str
    kind: str
    prompt: str
    expected_skill: str | None
    follows: str | None


@dataclass(frozen=True)
class ActivationReport:
    status: str
    package_name: str
    package_version: str
    source_commit: str
    surface: str | None
    cases: tuple[GoldenCase, ...]
    mismatches: tuple[str, ...]


def evaluate_activation(
    repository: Path,
    live_results: dict[str, str | None] | None = None,
    surface: str | None = None,
) -> ActivationReport:
    repository = repository.resolve()
    metadata = _read_json(repository / SOURCE_RELATIVE)
    cases = _golden_cases(_read_json(repository / GOLDEN_RELATIVE), set(metadata["skills"]))
    report = ActivationReport(
        status="unavailable",
        package_name=str(metadata["name"]),
        package_version=str(metadata["version"]),
        source_commit=_head(repository),
        surface=None,
        cases=cases,
        mismatches=(),
    )
    if live_results is None:
        if surface is not None:
            raise ActivationError("missing_surface", "an unavailable evaluation has no surface")
        return report
    if not surface:
        raise ActivationError("missing_surface", "a live evaluation needs the tested surface")
    mismatches: list[str] = []
    case_ids = {case.case_id for case in cases}
    for case in cases:
        if case.case_id not in live_results or live_results[case.case_id] != case.expected_skill:
            mismatches.append(case.case_id)
    mismatches.extend(sorted(set(live_results) - case_ids))
    return ActivationReport(
        status="failed" if mismatches else "passed",
        package_name=report.package_name,
        package_version=report.package_version,
        source_commit=report.source_commit,
        surface=surface,
        cases=cases,
        mismatches=tuple(mismatches),
    )


def main() -> int:
    report = evaluate_activation(Path.cwd())
    print(f"activation_status={report.status}")
    print(f"package_name={report.package_name}")
    print(f"package_version={report.package_version}")
    print(f"source_commit={report.source_commit}")
    print(f"surface={report.surface or ''}")
    return 1 if report.status == "failed" else 0


def _golden_cases(document: dict, skills: set[str]) -> tuple[GoldenCase, ...]:
    raw_cases = document.get("cases")
    if not isinstance(raw_cases, list) or not raw_cases:
        raise ActivationError("invalid_golden", "golden prompts are missing")
    cases: list[GoldenCase] = []
    seen: set[str] = set()
    for raw in raw_cases:
        case = _case(raw, skills)
        if case.case_id in seen:
            raise ActivationError("invalid_golden", f"duplicate golden case: {case.case_id}")
        seen.add(case.case_id)
        cases.append(case)
    if {case.kind for case in cases} != KINDS:
        raise ActivationError("invalid_golden", "golden prompts must cover every activation kind")
    for case in cases:
        if case.kind == "follow_up" and case.follows not in seen:
            raise ActivationError("invalid_golden", f"follow-up has no prior case: {case.case_id}")
        if case.kind == "follow_up" and case.follows == case.case_id:
            raise ActivationError("invalid_golden", f"follow-up cannot follow itself: {case.case_id}")
    return tuple(cases)


def _case(raw: object, skills: set[str]) -> GoldenCase:
    if not isinstance(raw, dict):
        raise ActivationError("invalid_golden", "a golden case must be an object")
    case_id = raw.get("id")
    kind = raw.get("kind")
    prompt = raw.get("prompt")
    expected = raw.get("expected_skill")
    follows = raw.get("follows")
    if not isinstance(case_id, str) or not case_id.strip():
        raise ActivationError("invalid_golden", "a golden case needs an id")
    if kind not in KINDS or not isinstance(prompt, str) or not prompt.strip():
        raise ActivationError("invalid_golden", f"golden case is incomplete: {case_id}")
    if kind in SELECTING_KINDS and (not isinstance(expected, str) or expected not in skills):
        raise ActivationError("invalid_golden", f"golden case selects an unknown skill: {case_id}")
    if kind in ABSTAINING_KINDS and expected is not None:
        raise ActivationError("invalid_golden", f"golden case must abstain: {case_id}")
    if isinstance(expected, str) and expected.casefold() in prompt.casefold():
        raise ActivationError("invalid_golden", f"prompt contains the expected skill: {case_id}")
    if follows is not None and not isinstance(follows, str):
        raise ActivationError("invalid_golden", f"follow-up reference is invalid: {case_id}")
    if kind == "follow_up" and not follows:
        raise ActivationError("invalid_golden", f"follow-up has no prior case: {case_id}")
    return GoldenCase(case_id, kind, prompt, expected if isinstance(expected, str) else None, follows)


def _read_json(path: Path) -> dict:
    if not path.is_file():
        raise ActivationError("invalid_golden", path.name)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ActivationError("invalid_golden", path.name) from error
    if not isinstance(data, dict):
        raise ActivationError("invalid_golden", path.name)
    return data


def _head(repository: Path) -> str:
    try:
        result = subprocess.run(
            ["git", "-C", str(repository), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
        )
    except subprocess.CalledProcessError as error:
        raise ActivationError("invalid_golden", "source commit is unreadable") from error
    return result.stdout.decode().strip()


if __name__ == "__main__":
    raise SystemExit(main())
