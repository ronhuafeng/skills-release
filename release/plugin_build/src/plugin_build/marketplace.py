"""Contract for the committed GitHub marketplace Plugin source."""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path


MARKETPLACE = ".agents/plugins/marketplace.json"
SOURCE = "release/plugins/engineering/source.json"
MANIFESTS = (".codex-plugin/plugin.json", ".claude-plugin/plugin.json")
GIT_URL = "https://github.com/ronhuafeng/skills-release.git"


class MarketplaceError(Exception):
    pass


@dataclass(frozen=True)
class MarketplaceContract:
    commit: str
    version: str
    skills: tuple[str, ...]


def verify_marketplace_checkout(repository: Path) -> MarketplaceContract:
    """Verify a checkout without building or reading ignored package output."""
    repository = repository.resolve()
    commit = _git(repository, "rev-parse", "HEAD").strip()
    tracked = set(_git(repository, "ls-tree", "-r", "--name-only", "HEAD").splitlines())

    def read(relative: str) -> dict:
        if relative not in tracked:
            raise MarketplaceError(f"uncommitted marketplace target: {relative}")
        path = repository / relative
        if path.is_symlink() or not path.is_file():
            raise MarketplaceError(f"missing marketplace target: {relative}")
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise MarketplaceError(f"invalid JSON: {relative}") from error
        if not isinstance(value, dict):
            raise MarketplaceError(f"invalid object: {relative}")
        return value

    catalog = read(MARKETPLACE)
    metadata = read(SOURCE)
    plugins = catalog.get("plugins")
    if catalog.get("name") != "ronhuafeng-skills" or catalog.get("interface", {}).get("displayName") != "Engineering":
        raise MarketplaceError("marketplace identity is invalid")
    if not isinstance(plugins, list) or len(plugins) != 1 or not isinstance(plugins[0], dict):
        raise MarketplaceError("marketplace must declare one engineering Plugin")
    plugin = plugins[0]
    source = plugin.get("source")
    if source != {"source": "url", "url": GIT_URL, "ref": "main"}:
        raise MarketplaceError("marketplace must use the public Git repository root on main")
    if plugin.get("name") != metadata.get("name") or metadata.get("repository") != GIT_URL.removesuffix(".git"):
        raise MarketplaceError("marketplace Plugin identity does not match source metadata")
    if plugin.get("policy") != {"installation": "AVAILABLE", "authentication": "ON_INSTALL"}:
        raise MarketplaceError("marketplace install or authentication policy is invalid")
    if plugin.get("category") != "Developer Tools" or plugin["category"] != metadata.get("openai", {}).get("interface", {}).get("category"):
        raise MarketplaceError("marketplace category does not match source metadata")

    declared = metadata.get("skills")
    if not isinstance(declared, list) or not declared or not all(isinstance(name, str) for name in declared):
        raise MarketplaceError("engineering Skill inventory is invalid")
    skills = tuple(sorted(declared))
    if len(set(skills)) != len(skills):
        raise MarketplaceError("duplicate engineering Skill")
    actual = tuple(sorted(path.parent.name for path in (repository / "catalog/engineering").glob("*/SKILL.md")))
    if actual != skills:
        raise MarketplaceError("canonical engineering Skill inventory differs from source metadata")
    for name in skills:
        relative = f"catalog/engineering/{name}/SKILL.md"
        if name in (".", "..") or "/" in name or "\\" in name or relative not in tracked:
            raise MarketplaceError(f"uncommitted engineering Skill: {name}")
        if (repository / relative).is_symlink():
            raise MarketplaceError(f"symlinked engineering Skill: {name}")

    shared = ("name", "version", "description", "repository", "license")
    for relative in MANIFESTS:
        manifest = read(relative)
        if any(manifest.get(field) != metadata.get(field) for field in shared):
            raise MarketplaceError(f"Plugin identity mismatch: {relative}")
        if manifest.get("author") != metadata.get("author"):
            raise MarketplaceError(f"Plugin author mismatch: {relative}")
        if manifest.get("skills") != "./catalog/engineering":
            raise MarketplaceError(f"Plugin Skill path is not canonical: {relative}")
    return MarketplaceContract(commit=commit, version=str(metadata["version"]), skills=skills)


def _git(repository: Path, *args: str) -> str:
    result = subprocess.run(["git", "-C", str(repository), *args], capture_output=True, text=True)
    if result.returncode:
        raise MarketplaceError(f"Git checkout is unavailable: {' '.join(args)}")
    return result.stdout
