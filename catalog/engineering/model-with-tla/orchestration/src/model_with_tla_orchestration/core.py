from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
import time
import zipfile
from dataclasses import asdict, dataclass
from pathlib import Path


MAX_DIAGNOSTIC_CHARACTERS = 262_144
EXPECTATIONS = {
    "success",
    "semantic-error",
    "temporal",
    "deadlock",
    "assumption",
    "assertion",
}


class CheckInputError(ValueError):
    """The caller supplied an invalid model-check request."""


class ToolPrerequisiteError(RuntimeError):
    """The pinned checker cannot run with the observed toolchain."""


@dataclass(frozen=True)
class Toolchain:
    version: str
    sha256: str
    revision: str
    build_timestamp: str
    minimum_java_major: int
    prerelease: bool


@dataclass(frozen=True)
class CheckResult:
    schema_version: int
    status: str
    expected: str
    observed: str
    module: str
    config: str | None
    tool_version: str
    tool_revision: str
    tool_build_timestamp: str
    tlc_version: str | None
    tool_prerelease: bool
    tool_sha256: str
    java_version: str
    generated_states: int | None
    distinct_states: int | None
    depth: int | None
    duration_ms: int
    diagnostics: str | None
    diagnostics_truncated: bool

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def default_skill_directory() -> Path:
    return Path(__file__).resolve().parents[3]


def load_toolchain(skill_directory: Path) -> tuple[Toolchain, Path]:
    tools = skill_directory / ".tools"
    manifest_path = tools / "toolchain.json"
    jar_path = tools / "tla2tools.jar"
    try:
        raw = json.loads(manifest_path.read_text())
    except FileNotFoundError as exc:
        raise ToolPrerequisiteError("bundled toolchain manifest is missing") from exc
    except json.JSONDecodeError as exc:
        raise ToolPrerequisiteError("bundled toolchain manifest is invalid") from exc
    if not isinstance(raw, dict) or raw.get("schemaVersion") != 1:
        raise ToolPrerequisiteError("bundled toolchain manifest schema is unsupported")
    try:
        toolchain = Toolchain(
            version=str(raw["version"]),
            sha256=str(raw["sha256"]),
            revision=str(raw["revision"]),
            build_timestamp=str(raw["buildTimestamp"]),
            minimum_java_major=int(raw["minimumJavaMajor"]),
            prerelease=bool(raw["prerelease"]),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise ToolPrerequisiteError("bundled toolchain manifest is incomplete") from exc
    if not re.fullmatch(r"[0-9a-f]{64}", toolchain.sha256):
        raise ToolPrerequisiteError("bundled toolchain checksum is invalid")
    if not re.fullmatch(r"[0-9a-f]{40}", toolchain.revision):
        raise ToolPrerequisiteError("bundled toolchain revision is invalid")
    try:
        observed_digest = hashlib.sha256(jar_path.read_bytes()).hexdigest()
    except FileNotFoundError as exc:
        raise ToolPrerequisiteError("bundled tla2tools.jar is missing") from exc
    if observed_digest != toolchain.sha256:
        raise ToolPrerequisiteError("bundled tla2tools.jar checksum does not match")
    try:
        with zipfile.ZipFile(jar_path) as archive:
            manifest = archive.read("META-INF/MANIFEST.MF").decode("utf-8")
    except (KeyError, UnicodeDecodeError, zipfile.BadZipFile) as exc:
        raise ToolPrerequisiteError("bundled tla2tools.jar manifest is invalid") from exc
    revision = re.search(
        r"^X-Git-Revision: ([0-9a-f]{40})\r?$", manifest, re.MULTILINE
    )
    built_at = re.search(r"^Build-TimeStamp: (.+?)\r?$", manifest, re.MULTILINE)
    if revision is None or revision.group(1) != toolchain.revision:
        raise ToolPrerequisiteError("bundled tla2tools.jar revision does not match")
    if built_at is None or built_at.group(1) != toolchain.build_timestamp:
        raise ToolPrerequisiteError("bundled tla2tools.jar build timestamp does not match")
    return toolchain, jar_path


def resolve_java(explicit: Path | None = None) -> Path:
    candidates: list[str] = []
    if explicit is not None:
        candidates.append(str(explicit))
    elif os.environ.get("TLA_JAVA"):
        candidates.append(os.environ["TLA_JAVA"])
    elif os.environ.get("JAVA_HOME"):
        candidates.append(str(Path(os.environ["JAVA_HOME"]) / "bin" / "java"))
    else:
        located = shutil.which("java")
        if located:
            candidates.append(located)
    if not candidates:
        raise ToolPrerequisiteError("Java executable is unavailable")
    candidate = Path(candidates[0]).expanduser()
    if not candidate.is_absolute():
        located = shutil.which(str(candidate))
        if located is None:
            raise ToolPrerequisiteError("Java executable is unavailable")
        candidate = Path(located)
    try:
        resolved = candidate.resolve(strict=True)
    except FileNotFoundError as exc:
        raise ToolPrerequisiteError("Java executable is unavailable") from exc
    if not os.access(resolved, os.X_OK):
        raise ToolPrerequisiteError("Java executable is not executable")
    return resolved


def inspect_java(java: Path, minimum_major: int) -> tuple[int, str]:
    completed = subprocess.run(
        [str(java), "-version"],
        text=True,
        capture_output=True,
        check=False,
    )
    output = (completed.stderr or completed.stdout).strip()
    first_line = output.splitlines()[0] if output else ""
    match = re.search(r'version "([0-9]+)(?:\.([0-9]+))?', first_line)
    if completed.returncode != 0 or match is None:
        raise ToolPrerequisiteError("Java version could not be determined")
    first = int(match.group(1))
    major = int(match.group(2)) if first == 1 and match.group(2) else first
    if major < minimum_major:
        raise ToolPrerequisiteError(
            f"Java {minimum_major} or newer is required; observed Java {major}"
        )
    return major, first_line


def parse_expectation(raw: str) -> str:
    if raw.startswith("invariant:"):
        name = raw.removeprefix("invariant:")
        if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_!]*", name):
            return raw
        raise CheckInputError("invariant expectation requires one operator name")
    if raw in EXPECTATIONS:
        return raw
    raise CheckInputError(f"unsupported expectation: {raw}")


def validate_inputs(
    module: Path, config: Path | None, expectation: str
) -> tuple[Path, Path | None]:
    try:
        resolved_module = module.expanduser().resolve(strict=True)
    except FileNotFoundError as exc:
        raise CheckInputError("module does not exist") from exc
    if not resolved_module.is_file() or resolved_module.suffix != ".tla":
        raise CheckInputError("module must be one .tla file")
    resolved_config: Path | None = None
    if config is not None:
        try:
            resolved_config = config.expanduser().resolve(strict=True)
        except FileNotFoundError as exc:
            raise CheckInputError("config does not exist") from exc
        if not resolved_config.is_file() or resolved_config.suffix != ".cfg":
            raise CheckInputError("config must be one .cfg file")
    if expectation != "semantic-error" and resolved_config is None:
        raise CheckInputError("config is required for TLC expectations")
    return resolved_module, resolved_config


def classify_tlc(output: str, returncode: int) -> str:
    invariant = re.search(r"Invariant\s+([^\s]+)\s+is violated", output)
    if invariant:
        return f"invariant:{invariant.group(1).rstrip('.')}"
    if "Temporal properties were violated" in output:
        return "temporal"
    if "Deadlock reached" in output:
        return "deadlock"
    if re.search(r"assumption.*(?:false|violat)", output, re.IGNORECASE):
        return "assumption"
    if re.search(r"assert(?:ion)?.*(?:failed|violat)", output, re.IGNORECASE):
        return "assertion"
    if returncode == 0 and "Model checking completed. No error has been found." in output:
        return "success"
    return "tool-error"


def classify_sany(output: str, returncode: int) -> str:
    if returncode == 0:
        return "semantic-success"
    if re.search(
        r"(?:Semantic errors:|Parse Error|Lexical error|Unknown operator)",
        output,
        re.IGNORECASE,
    ):
        return "semantic-error"
    return "tool-error"


def parse_statistics(output: str) -> tuple[str, int | None, int | None, int | None]:
    version_match = re.search(r"^(TLC2 Version .+)$", output, re.MULTILINE)
    version = version_match.group(1) if version_match else "unknown"
    stats = list(
        re.finditer(
            r"([0-9][0-9,]*) states generated, "
            r"([0-9][0-9,]*) distinct states found",
            output,
        )
    )
    generated = int(stats[-1].group(1).replace(",", "")) if stats else None
    distinct = int(stats[-1].group(2).replace(",", "")) if stats else None
    depth_match = re.search(
        r"The depth of the complete state graph search is ([0-9]+)", output
    )
    depth = int(depth_match.group(1)) if depth_match else None
    return version, generated, distinct, depth


def bounded_diagnostics(output: str, observed: str) -> tuple[str | None, bool]:
    if observed == "success":
        return None, False
    if len(output) <= MAX_DIAGNOSTIC_CHARACTERS:
        return output, False
    return output[:MAX_DIAGNOSTIC_CHARACTERS], True


def sanitize_output(output: str, paths: dict[Path, str]) -> str:
    sanitized = output
    for path, replacement in paths.items():
        sanitized = sanitized.replace(str(path), replacement)
    return sanitized


def check_model(
    *,
    module: Path,
    config: Path | None,
    expectation: str,
    java: Path | None = None,
    skill_directory: Path | None = None,
) -> CheckResult:
    expected = parse_expectation(expectation)
    resolved_module, resolved_config = validate_inputs(module, config, expected)
    root = (skill_directory or default_skill_directory()).resolve()
    toolchain, jar = load_toolchain(root)
    java_executable = resolve_java(java)
    _, java_version = inspect_java(java_executable, toolchain.minimum_java_major)
    started = time.monotonic()
    sany = subprocess.run(
        [
            str(java_executable),
            "-cp",
            str(jar),
            "tla2sany.SANY",
            "-error-codes",
            resolved_module.name,
        ],
        cwd=resolved_module.parent,
        text=True,
        capture_output=True,
        check=False,
    )
    sensitive_paths = {
        resolved_module.parent: "<model-directory>",
        root: "<skill-directory>",
    }
    if resolved_config is not None and resolved_config.parent != resolved_module.parent:
        sensitive_paths[resolved_config.parent] = "<config-directory>"
    sany_output = sanitize_output(sany.stdout + sany.stderr, sensitive_paths)
    sany_observed = classify_sany(sany_output, sany.returncode)
    if sany_observed != "semantic-success":
        observed = sany_observed
        diagnostics, truncated = bounded_diagnostics(sany_output, observed)
        status = "matched" if observed == expected else "mismatch"
        if observed == "tool-error":
            status = "tool-error"
        return CheckResult(
            schema_version=1,
            status=status,
            expected=expected,
            observed=observed,
            module=resolved_module.name,
            config=resolved_config.name if resolved_config else None,
            tool_version=toolchain.version,
            tool_revision=toolchain.revision,
            tool_build_timestamp=toolchain.build_timestamp,
            tlc_version=None,
            tool_prerelease=toolchain.prerelease,
            tool_sha256=toolchain.sha256,
            java_version=java_version,
            generated_states=None,
            distinct_states=None,
            depth=None,
            duration_ms=round((time.monotonic() - started) * 1000),
            diagnostics=diagnostics,
            diagnostics_truncated=truncated,
        )
    if expected == "semantic-error":
        return CheckResult(
            schema_version=1,
            status="mismatch",
            expected=expected,
            observed="semantic-success",
            module=resolved_module.name,
            config=resolved_config.name if resolved_config else None,
            tool_version=toolchain.version,
            tool_revision=toolchain.revision,
            tool_build_timestamp=toolchain.build_timestamp,
            tlc_version=None,
            tool_prerelease=toolchain.prerelease,
            tool_sha256=toolchain.sha256,
            java_version=java_version,
            generated_states=None,
            distinct_states=None,
            depth=None,
            duration_ms=round((time.monotonic() - started) * 1000),
            diagnostics=None,
            diagnostics_truncated=False,
        )
    assert resolved_config is not None
    with tempfile.TemporaryDirectory(prefix="model-with-tla-") as metadata:
        tlc = subprocess.run(
            [
                str(java_executable),
                "-XX:+UseParallelGC",
                "-jar",
                str(jar),
                "-metadir",
                metadata,
                "-noGenerateSpecTE",
                "-config",
                str(resolved_config),
                resolved_module.name,
            ],
            cwd=resolved_module.parent,
            text=True,
            capture_output=True,
            check=False,
        )
    output = sanitize_output(tlc.stdout + tlc.stderr, sensitive_paths)
    observed = classify_tlc(output, tlc.returncode)
    version, generated, distinct, depth = parse_statistics(output)
    diagnostics, truncated = bounded_diagnostics(output, observed)
    status = "matched" if observed == expected else "mismatch"
    if observed == "tool-error":
        status = "tool-error"
    return CheckResult(
        schema_version=1,
        status=status,
        expected=expected,
        observed=observed,
        module=resolved_module.name,
        config=resolved_config.name,
        tool_version=toolchain.version,
        tool_revision=toolchain.revision,
        tool_build_timestamp=toolchain.build_timestamp,
        tlc_version=version if version != "unknown" else None,
        tool_prerelease=toolchain.prerelease,
        tool_sha256=toolchain.sha256,
        java_version=java_version,
        generated_states=generated,
        distinct_states=distinct,
        depth=depth,
        duration_ms=round((time.monotonic() - started) * 1000),
        diagnostics=diagnostics,
        diagnostics_truncated=truncated,
    )
