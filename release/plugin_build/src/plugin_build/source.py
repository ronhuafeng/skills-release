"""Committed engineering Plugin identity and inventory, independent of ZIP config."""

from __future__ import annotations

import json
import re
import subprocess
import unicodedata
from dataclasses import dataclass
from pathlib import Path

CANONICAL_ROOT = "catalog/engineering"
CODEX_MANIFEST = ".codex-plugin/plugin.json"
CLAUDE_MANIFEST = ".claude-plugin/plugin.json"
SHARED_FIELDS = ("name", "version", "description", "author.name", "repository", "license")
NAME_RE = re.compile(r"^(?!.*--)[a-z0-9](?:[a-z0-9-]*[a-z0-9])?$")
SEMVER_RE = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")
SKILL_NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


class SourceError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class PluginSource:
    commit: str
    manifest: dict
    # name -> committed (mode, blob id, path within Skill) entries
    skills: dict[str, list[tuple[str, str, str]]]


def git(repository: Path, *args: str) -> bytes:
    try:
        return subprocess.run(
            ["git", "-C", str(repository), *args], check=True, capture_output=True
        ).stdout
    except subprocess.CalledProcessError as error:
        raise SourceError("invalid_source", "Git checkout is unavailable") from error


def committed_files(repository: Path, *paths: str) -> dict[str, tuple[str, str]]:
    entries = {}
    for entry in git(repository, "ls-tree", "-rz", "HEAD", "--", *paths).split(b"\0"):
        if not entry:
            continue
        header, path = entry.split(b"\t", 1)
        mode, kind, blob = header.decode().split()
        if kind != "blob" or mode not in {"100644", "100755"}:
            raise SourceError("path_escape", f"unsafe committed target: {path.decode()}")
        entries[path.decode()] = (mode, blob)
    return entries


def require_checkout(repository: Path, entries: dict[str, tuple[str, str]], *paths: str) -> None:
    """Require tracked resources, safe ancestors, and a worktree matching HEAD.

    Git-ignored runtime caches are not source inputs; unignored additions fail.
    Every committed resource is checked even when Git would ignore its name.
    """
    for relative in entries:
        target = repository / relative
        if any(parent.is_symlink() for parent in (target, *target.parents) if parent != repository):
            raise SourceError("path_escape", f"symlinked marketplace target: {relative}")
        if not target.is_file():
            raise SourceError("missing_file", f"missing marketplace target: {relative}")
    if git(repository, "ls-files", "--others", "--exclude-standard", "--", *paths):
        raise SourceError("dirty_source", "uncommitted marketplace target")
    if git(repository, "diff", "HEAD", "--name-only", "--", *paths):
        raise SourceError("dirty_source", "dirty marketplace target differs from HEAD")


def read_committed_json(repository: Path, relative: str) -> dict:
    entries = committed_files(repository, relative)
    if relative not in entries:
        raise SourceError("missing_file", f"uncommitted marketplace target: {relative}")
    require_checkout(repository, entries, relative)
    try:
        document = json.loads(git(repository, "cat-file", "blob", entries[relative][1]))
    except (ValueError, UnicodeDecodeError) as error:
        raise SourceError("invalid_source", f"invalid JSON: {relative}") from error
    if not isinstance(document, dict):
        raise SourceError("invalid_source", f"invalid object: {relative}")
    return document


def _shared(document: dict, field: str) -> object:
    value: object = document
    for key in field.split("."):
        if not isinstance(value, dict):
            raise SourceError("identity_mismatch", f"missing shared identity: {field}")
        value = value.get(key)
    if not isinstance(value, str) or not value.strip():
        raise SourceError("identity_mismatch", f"invalid shared identity: {field}")
    return value


def load_plugin_source(repository: Path) -> PluginSource:
    repository = repository.resolve()
    manifest = read_committed_json(repository, CODEX_MANIFEST)
    claude = read_committed_json(repository, CLAUDE_MANIFEST)
    for field in SHARED_FIELDS:
        if _shared(manifest, field) != _shared(claude, field):
            raise SourceError("identity_mismatch", f"shared field differs: {field}")
    if len(manifest["name"]) > 64 or not NAME_RE.fullmatch(manifest["name"]):
        raise SourceError("identity_mismatch", "Plugin name is invalid")
    if len(manifest["version"]) > 64 or not SEMVER_RE.fullmatch(manifest["version"]):
        raise SourceError("identity_mismatch", "Plugin version is not semantic")
    for relative, document in ((CODEX_MANIFEST, manifest), (CLAUDE_MANIFEST, claude)):
        if document.get("skills") != f"./{CANONICAL_ROOT}":
            raise SourceError("identity_mismatch", f"Plugin Skill path is not canonical: {relative}")
    entries = committed_files(repository, CANONICAL_ROOT)
    require_checkout(repository, entries, CANONICAL_ROOT)
    skills: dict[str, list[tuple[str, str, str]]] = {}
    names = sorted(path[len(CANONICAL_ROOT) + 1:].split("/")[0] for path in entries if path.endswith("/SKILL.md") and path.count("/") == 3)
    actual = sorted(path.parent.name for path in (repository / CANONICAL_ROOT).glob("*/SKILL.md"))
    if actual != names:
        raise SourceError("dirty_source", "uncommitted engineering Skill inventory")
    if not names:
        raise SourceError("missing_file", "canonical engineering Skill inventory is empty")
    seen: set[str] = set()
    for name in names:
        if not SKILL_NAME_RE.fullmatch(name):
            raise SourceError("inventory_mismatch", f"skill name is not package-safe: {name}")
        prefix = f"{CANONICAL_ROOT}/{name}/"
        skills[name] = []
        for path, (mode, blob) in entries.items():
            if not path.startswith(prefix):
                continue
            key = unicodedata.normalize("NFC", path).casefold()
            if key in seen:
                raise SourceError("duplicate_path", f"duplicate canonical resource: {path}")
            seen.add(key)
            skills[name].append((mode, blob, path[len(prefix):]))
    return PluginSource(git(repository, "rev-parse", "HEAD").decode().strip(), manifest, skills)
