from __future__ import annotations

import json
import re
import shutil
import subprocess
import unicodedata
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable
from urllib.parse import urlparse

from .source import CANONICAL_ROOT, PluginSource, SourceError, load_plugin_source, read_committed_json

SCHEMA = "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json"
SOURCE_METADATA = "release/plugins/engineering/source.json"
INPUT_PATHS = (
    CANONICAL_ROOT,
    "release/plugins/engineering",
    ".codex-plugin/plugin.json",
    ".claude-plugin/plugin.json",
)
EXCLUDED_DIRECTORIES = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
}
ALLOWED_ROOT_KEYS = {
    "$schema",
    "author",
    "description",
    "extensions",
    "homepage",
    "keywords",
    "license",
    "name",
    "repository",
    "version",
}
ALLOWED_OPENAI_KEYS = {"interface"}
ALLOWED_INTERFACE_KEYS = {
    "brandColor",
    "brandColorDark",
    "capabilities",
    "category",
    "composerIcon",
    "composerIconDark",
    "defaultPrompt",
    "developerName",
    "displayName",
    "logo",
    "logoDark",
    "longDescription",
    "privacyPolicyURL",
    "screenshots",
    "shortDescription",
    "supportURL",
    "termsOfServiceURL",
    "websiteURL",
}
INTERFACE_LIMITS = {
    "developerName": 120,
    "displayName": 80,
    "longDescription": 4000,
    "shortDescription": 240,
}
CATEGORIES = {
    "Business & Operations",
    "Communication",
    "Creativity",
    "Data & Analytics",
    "Developer Tools",
    "Education & Research",
    "Entertainment",
    "Finance",
    "Healthcare",
    "Other",
    "Productivity",
    "Security",
    "Travel",
}
MAX_DESCRIPTION_LENGTH = 1024
MAX_AUTHOR_NAME_LENGTH = 120
MAX_PATH_SEGMENTS = 20
MAX_URL_LENGTH = 2048
MAX_VERSION_LENGTH = 64
MAX_DEFAULT_PROMPTS = 3
MAX_DEFAULT_PROMPT_LENGTH = 512
LIGHT_BACKGROUND = "#FFFFFF"
DARK_BACKGROUND = "#212121"
HEX_COLOR_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")
LISTING_URLS = ("websiteURL", "privacyPolicyURL", "termsOfServiceURL", "supportURL")

MAX_COMPRESSED_BYTES = 100 * 1024 * 1024
MAX_UNCOMPRESSED_BYTES = 512 * 1024 * 1024
MAX_ENTRIES = 5000
MAX_ENTRY_BYTES = 100 * 1024 * 1024
NAME_RE = re.compile(r"^(?!.*--)[a-z0-9](?:[a-z0-9-]*[a-z0-9])?$")
SEMVER_RE = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")
COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
RELATIVE_REFERENCE_RE = re.compile(r"^\./[A-Za-z0-9._/-]+$")


class PackageError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class PackagedSkill:
    name: str
    source: str


@dataclass(frozen=True)
class PlannedFile:
    path: str
    data: bytes
    mode: int


@dataclass(frozen=True)
class PortablePackage:
    root: Path
    zip_path: Path
    name: str
    version: str
    source_commit: str
    skills: tuple[PackagedSkill, ...]


def build_from_head(repository: Path, destination: Path | None = None) -> PortablePackage:
    authority = _load_source(repository)
    return build_portable_package(
        repository,
        version=authority.manifest["version"],
        source_commit=git_head(repository),
        destination=destination or repository / "dist" / "plugins",
    )


def build_portable_package(
    repository: Path,
    *,
    version: str,
    source_commit: str,
    destination: Path,
) -> PortablePackage:
    repository = repository.resolve()
    destination = destination.resolve()
    _reject_destination(repository, destination)
    commit = _require_commit(source_commit)
    if commit != git_head(repository):
        raise PackageError("identity_mismatch", "source commit does not match HEAD")
    authority = _load_source(repository)
    _require_clean(repository)
    try:
        metadata = read_committed_json(repository, SOURCE_METADATA)
    except SourceError as error:
        raise PackageError(error.code, str(error)) from error
    if set(metadata) - {"keywords", "openai", "assets"}:
        raise PackageError("invalid_source", "ZIP config contains non-package fields")
    metadata = {
        **metadata,
        **{field: authority.manifest[field] for field in ("name", "version", "description", "repository", "license")},
        "author": {"name": authority.manifest["author"]["name"]},
        "skills": list(authority.skills),
    }
    _validate_metadata_shape(metadata)
    if version != metadata["version"]:
        raise PackageError("identity_mismatch", "version does not match root Codex manifest")
    _require_semver(version)
    _require_name(metadata["name"])
    skills = authority.skills
    planned = _plan_files(repository, metadata, skills, commit)
    assert_unique_package_paths(item.path for item in planned)
    package_dir = destination / metadata["name"]
    zip_path = destination / f"{metadata['name']}-{version}.zip"
    _reset_output(package_dir, zip_path)
    for item in planned:
        target = package_dir / item.path
        if not target.resolve().is_relative_to(package_dir.resolve()):
            raise PackageError("path_escape", item.path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(item.data)
        target.chmod(item.mode)
    _write_zip(planned, zip_path)
    validate_zip(zip_path)
    packaged = tuple(
        PackagedSkill(name=name, source=f"{CANONICAL_ROOT}/{name}")
        for name in metadata["skills"]
    )
    return PortablePackage(
        root=package_dir,
        zip_path=zip_path,
        name=metadata["name"],
        version=version,
        source_commit=commit,
        skills=packaged,
    )


def assert_unique_package_paths(paths: Iterable[str]) -> None:
    seen: dict[str, str] = {}
    for path in paths:
        if "\\" in path:
            raise PackageError("path_escape", path)
        parts = path.split("/")
        if (
            not path
            or path != path.strip()
            or path.startswith("/")
            or len(parts) > MAX_PATH_SEGMENTS
            or any(part in {"", ".", ".."} for part in parts)
        ):
            raise PackageError("path_escape", path)
        key = unicodedata.normalize("NFC", path).casefold()
        if key in seen:
            raise PackageError("duplicate_path", path)
        seen[key] = path


def assert_archive_limits(
    *,
    compressed_bytes: int,
    uncompressed_bytes: int,
    entry_count: int,
    largest_entry: int,
) -> None:
    if (
        compressed_bytes > MAX_COMPRESSED_BYTES
        or uncompressed_bytes > MAX_UNCOMPRESSED_BYTES
        or entry_count > MAX_ENTRIES
        or largest_entry > MAX_ENTRY_BYTES
    ):
        raise PackageError("archive_limit", "package exceeds OpenAI archive limits")


def validate_zip(zip_path: Path) -> None:
    with zipfile.ZipFile(zip_path) as archive:
        infos = archive.infolist()
        names = [info.filename for info in infos]
        assert_unique_package_paths(names)
        if names.count("plugin.json") != 1 or any(name.endswith("/plugin.json") for name in names):
            raise PackageError("invalid_archive", "ZIP must contain exactly one plugin root")
        if not any(name.startswith("skills/") and name.endswith("/SKILL.md") for name in names):
            raise PackageError("missing_file", "package contains no Skill")
        if any(name in {"mcp.json", ".mcp.json"} for name in names):
            raise PackageError("forbidden_content", "package must not add MCP configuration")
        forbidden = ("agents/", "catalog/", "docs/", "harnesses/")
        if any(name.startswith(forbidden) for name in names):
            raise PackageError("forbidden_content", "package contains repository source outside Skills")
        uncompressed = sum(info.file_size for info in infos)
        largest = max((info.file_size for info in infos), default=0)
    assert_archive_limits(
        compressed_bytes=zip_path.stat().st_size,
        uncompressed_bytes=uncompressed,
        entry_count=len(names),
        largest_entry=largest,
    )


def repository_root(start: Path) -> Path:
    result = _git(start, "rev-parse", "--show-toplevel")
    return Path(result.stdout.decode().strip())


def git_head(repository: Path) -> str:
    result = _git(repository, "rev-parse", "HEAD")
    return result.stdout.decode().strip().lower()


def _plan_files(
    repository: Path,
    metadata: dict,
    skills: dict[str, list[tuple[str, str, str]]],
    commit: str,
) -> list[PlannedFile]:
    planned = [
        PlannedFile("plugin.json", _plugin_bytes(metadata), 0o644),
        PlannedFile("assets/provenance.json", _provenance_bytes(metadata, commit), 0o644),
    ]
    for asset in metadata.get("assets", []):
        package_path = asset["package"]
        source = asset["source"]
        if not source.startswith("release/plugins/engineering/assets/"):
            raise PackageError("path_escape", source)
        if not package_path.startswith("assets/") or package_path == "assets/provenance.json":
            raise PackageError("path_escape", package_path)
        planned.append(
            PlannedFile(package_path, _blob_for_path(repository, source), 0o644)
        )
    for name in metadata["skills"]:
        for mode, blob, inner in skills[name]:
            if _secret(inner):
                raise PackageError("forbidden_content", f"{CANONICAL_ROOT}/{name}/{inner}")
            if _excluded(inner):
                continue
            if _git_mode_is_unsafe(mode):
                raise PackageError("path_escape", f"{CANONICAL_ROOT}/{name}/{inner}")
            file_mode = 0o755 if int(mode, 8) & 0o111 else 0o644
            planned.append(
                PlannedFile(
                    f"skills/{name}/{inner}",
                    _blob(repository, blob),
                    file_mode,
                )
            )
    _require_interface_files(metadata, {item.path for item in planned})
    return sorted(planned, key=lambda item: item.path)


def _load_source(repository: Path) -> PluginSource:
    try:
        return load_plugin_source(repository)
    except SourceError as error:
        raise PackageError(error.code, str(error)) from error


def _plugin_bytes(metadata: dict) -> bytes:
    interface = metadata["openai"]["interface"]
    document = {
        "$schema": SCHEMA,
        "name": metadata["name"],
        "version": metadata["version"],
        "description": metadata["description"],
        "author": {"name": metadata["author"]["name"]},
        "repository": metadata["repository"],
        "license": metadata["license"],
        "keywords": metadata["keywords"],
        "extensions": {"com.openai": {"interface": interface}},
    }
    _validate_plugin_document(document)
    return _dump(document)


def _provenance_bytes(metadata: dict, commit: str) -> bytes:
    return _dump(
        {
            "name": metadata["name"],
            "version": metadata["version"],
            "source_commit": commit,
            "skills": [
                {"name": name, "source": f"{CANONICAL_ROOT}/{name}"}
                for name in metadata["skills"]
            ],
        }
    )


def _validate_metadata_shape(metadata: dict) -> None:
    required = {
        "author",
        "description",
        "keywords",
        "license",
        "name",
        "openai",
        "repository",
        "skills",
        "version",
    }
    if not required <= set(metadata):
        raise PackageError("invalid_source", "source metadata is incomplete")
    if not isinstance(metadata["skills"], list) or not metadata["skills"]:
        raise PackageError("invalid_source", "skill inventory is empty")
    if not isinstance(metadata["keywords"], list) or not all(
        isinstance(item, str) and item.strip() for item in metadata["keywords"]
    ):
        raise PackageError("invalid_source", "keywords are invalid")
    description = metadata["description"]
    if (
        not isinstance(description, str)
        or not description.strip()
        or len(description) > MAX_DESCRIPTION_LENGTH
    ):
        raise PackageError("invalid_source", "description is missing or too long")
    author_name = metadata.get("author", {}).get("name") if isinstance(metadata.get("author"), dict) else None
    if not isinstance(author_name, str) or not author_name.strip() or len(author_name) > MAX_AUTHOR_NAME_LENGTH:
        raise PackageError("invalid_source", "author name is missing or too long")
    interface = metadata["openai"].get("interface")
    if not isinstance(interface, dict):
        raise PackageError("invalid_source", "OpenAI interface metadata is missing")
    unknown = set(metadata["openai"]) - ALLOWED_OPENAI_KEYS
    if unknown:
        raise PackageError("invalid_source", "unknown OpenAI metadata")
    if "screenshots" in interface:
        raise PackageError("forbidden_content", "skills-only package cannot include screenshots")
    if set(interface) - ALLOWED_INTERFACE_KEYS:
        raise PackageError("invalid_source", "unknown OpenAI interface field")
    category = interface.get("category")
    if category is not None and category not in CATEGORIES:
        raise PackageError("invalid_source", "category is not supported")
    capabilities = interface.get("capabilities", [])
    if not isinstance(capabilities, list) or len(capabilities) > 20:
        raise PackageError("invalid_source", "capabilities are invalid")
    if any(
        not isinstance(item, str) or not item.strip() or "\n" in item or len(item) > 120
        for item in capabilities
    ):
        raise PackageError("invalid_source", "capabilities are invalid")
    for field, limit in INTERFACE_LIMITS.items():
        value = interface.get(field, "")
        if not isinstance(value, str) or not value.strip() or len(value) > limit:
            raise PackageError("invalid_source", f"{field} is missing or too long")
        if field != "longDescription" and "\n" in value:
            raise PackageError("invalid_source", f"{field} must be one line")
    for field in LISTING_URLS:
        if field in interface:
            _require_https_url(interface[field], field)
    for field, background in (("brandColor", LIGHT_BACKGROUND), ("brandColorDark", DARK_BACKGROUND)):
        if field in interface:
            _require_brand_color(interface[field], background)
    if "defaultPrompt" in interface:
        _require_default_prompts(interface["defaultPrompt"])
    for field in ("logo", "logoDark", "composerIcon", "composerIconDark"):
        if field in interface and not RELATIVE_REFERENCE_RE.fullmatch(interface[field]):
            raise PackageError("path_escape", field)



def _require_https_url(value: object, field: str) -> None:
    parsed = urlparse(value) if isinstance(value, str) else None
    if (
        not isinstance(value, str)
        or parsed is None
        or parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or len(value) > MAX_URL_LENGTH
    ):
        raise PackageError("invalid_source", f"{field} must be an HTTPS URL")


def _require_brand_color(value: object, background: str) -> None:
    if not isinstance(value, str) or not HEX_COLOR_RE.fullmatch(value):
        raise PackageError("invalid_source", "brand color must be a six-digit hex color")
    if _contrast(value, background) < 2:
        raise PackageError("invalid_source", "brand color contrast is too low")


def _require_default_prompts(value: object) -> None:
    prompts = [value] if isinstance(value, str) else value
    if not isinstance(prompts, list) or len(prompts) > MAX_DEFAULT_PROMPTS:
        raise PackageError("invalid_source", "default prompts are invalid")
    for prompt in prompts:
        if (
            not isinstance(prompt, str)
            or not prompt.strip()
            or "\n" in prompt
            or len(prompt) > MAX_DEFAULT_PROMPT_LENGTH
        ):
            raise PackageError("invalid_source", "default prompts are invalid")


def _contrast(color: str, background: str) -> float:
    luminances = sorted((_relative_luminance(color), _relative_luminance(background)), reverse=True)
    return (luminances[0] + 0.05) / (luminances[1] + 0.05)


def _relative_luminance(color: str) -> float:
    channels = [int(color[index : index + 2], 16) / 255 for index in (1, 3, 5)]

    def linear(channel: float) -> float:
        if channel <= 0.04045:
            return channel / 12.92
        return ((channel + 0.055) / 1.055) ** 2.4

    red, green, blue = (linear(channel) for channel in channels)
    return 0.2126 * red + 0.7152 * green + 0.0722 * blue


def _validate_plugin_document(document: dict) -> None:
    if set(document) - ALLOWED_ROOT_KEYS or document["$schema"] != SCHEMA:
        raise PackageError("invalid_archive", "portable manifest does not match the Agent Plugins schema")
    if "skills" in document or "mcpServers" in document:
        raise PackageError("invalid_archive", "portable manifest must not restate discovered components")


def _require_interface_files(metadata: dict, paths: set[str]) -> None:
    interface = metadata["openai"]["interface"]
    for field in ("logo", "logoDark", "composerIcon", "composerIconDark"):
        reference = interface.get(field)
        if reference is None:
            continue
        relative = reference.removeprefix("./")
        if relative not in paths:
            raise PackageError("missing_file", reference)
    for asset in metadata.get("assets", []):
        if asset["package"] not in paths:
            raise PackageError("missing_file", asset["source"])


def _require_name(name: object) -> None:
    if not isinstance(name, str) or len(name) > 64 or not NAME_RE.fullmatch(name):
        raise PackageError("identity_mismatch", "plugin name is not portable")


def _require_semver(version: object) -> None:
    if (
        not isinstance(version, str)
        or len(version) > MAX_VERSION_LENGTH
        or not SEMVER_RE.fullmatch(version)
    ):
        raise PackageError("identity_mismatch", "version must be semantic")


def _require_commit(commit: str) -> str:
    normalized = commit.lower()
    if not COMMIT_RE.fullmatch(normalized):
        raise PackageError("identity_mismatch", "source commit must identify one Git commit")
    return normalized


def _require_clean(repository: Path) -> None:
    result = _git(repository, "status", "--porcelain", "--", *INPUT_PATHS)
    if result.stdout.strip():
        raise PackageError("dirty_source", "canonical source does not match HEAD")


def _reject_destination(repository: Path, destination: Path) -> None:
    forbidden = [repository / "catalog", repository / "release", repository / ".git"]
    if any(destination == path or path in destination.parents for path in forbidden):
        raise PackageError("path_escape", "package destination must stay outside canonical source")


def _secret(inner: str) -> bool:
    secret_names = {".env", ".npmrc", "credentials.json", "id_rsa"}
    parts = inner.split("/")
    return any(part in secret_names or part.endswith(".pem") for part in parts)


def _excluded(inner: str) -> bool:
    parts = inner.split("/")
    return any(part in EXCLUDED_DIRECTORIES or part.endswith(".egg-info") for part in parts) or parts[-1] in {
        ".DS_Store"
    } or parts[-1].endswith((".pyc", ".pyo"))


def _git_mode_is_unsafe(mode: str) -> bool:
    return mode not in {"100644", "100755"}


def _blob_for_path(repository: Path, relative: str) -> bytes:
    if relative.startswith("/") or ".." in Path(relative).parts:
        raise PackageError("path_escape", relative)
    result = _git(repository, "ls-tree", "HEAD", relative)
    if not result.stdout.strip():
        raise PackageError("missing_file", relative)
    mode, kind, blob, path = _parse_ls_tree(result.stdout.decode().splitlines()[0])
    if kind != "blob" or path != relative or _git_mode_is_unsafe(mode):
        raise PackageError("missing_file", relative)
    return _blob(repository, blob)


def _blob(repository: Path, blob: str) -> bytes:
    return _git(repository, "cat-file", "blob", blob).stdout


def _parse_ls_tree(line: str) -> tuple[str, str, str, str]:
    meta, path = line.split("\t", 1)
    mode, kind, blob = meta.split(" ", 2)
    return mode, kind, blob, path


def _read_json(path: Path) -> dict:
    if not path.is_file():
        raise PackageError("missing_file", path.name)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise PackageError("invalid_source", path.name) from error
    if not isinstance(data, dict):
        raise PackageError("invalid_source", path.name)
    return data


def _dump(document: dict) -> bytes:
    return (json.dumps(document, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _reset_output(package_dir: Path, zip_path: Path) -> None:
    if package_dir.exists():
        shutil.rmtree(package_dir)
    zip_path.unlink(missing_ok=True)
    package_dir.mkdir(parents=True)


def _write_zip(planned: list[PlannedFile], zip_path: Path) -> None:
    with zipfile.ZipFile(zip_path, "w") as archive:
        for item in planned:
            info = zipfile.ZipInfo(item.path, (1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = (0o100000 | item.mode) << 16
            archive.writestr(info, item.data, compresslevel=9)


def _git(repository: Path, *args: str) -> subprocess.CompletedProcess[bytes]:
    try:
        return subprocess.run(
            ["git", "-C", str(repository), *args],
            check=True,
            capture_output=True,
        )
    except subprocess.CalledProcessError as error:
        raise PackageError("invalid_source", "git metadata is unreadable") from error
