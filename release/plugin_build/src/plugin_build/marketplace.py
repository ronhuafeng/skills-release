"""Contract for the committed GitHub marketplace Plugin source."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .source import SourceError, load_plugin_source, read_committed_json


MARKETPLACE = ".agents/plugins/marketplace.json"
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
    try:
        authority = load_plugin_source(repository)
        catalog = read_committed_json(repository, MARKETPLACE)
        claude_catalog = read_committed_json(repository, ".claude-plugin/marketplace.json")
    except SourceError as error:
        raise MarketplaceError(str(error)) from error
    metadata = authority.manifest
    plugins = catalog.get("plugins")
    interface = catalog.get("interface")
    if catalog.get("name") != "ronhuafeng-skills" or not isinstance(interface, dict) or interface.get("displayName") != "Engineering":
        raise MarketplaceError("marketplace identity is invalid")
    if not isinstance(plugins, list) or len(plugins) != 1 or not isinstance(plugins[0], dict):
        raise MarketplaceError("marketplace must declare one engineering Plugin")
    plugin = plugins[0]
    source = plugin.get("source")
    if source != {"source": "url", "url": GIT_URL, "ref": "main"}:
        raise MarketplaceError("marketplace must use the public Git repository root on main")
    if plugin.get("name") != metadata.get("name") or metadata.get("repository") != GIT_URL.removesuffix(".git"):
        raise MarketplaceError("marketplace Plugin identity does not match root Codex manifest")
    if plugin.get("policy") != {"installation": "AVAILABLE", "authentication": "ON_INSTALL"}:
        raise MarketplaceError("marketplace install or authentication policy is invalid")
    if plugin.get("category") != "Developer Tools":
        raise MarketplaceError("marketplace category is invalid")
    # Claude has a distinct native schema; shared identity/source semantics agree.
    claude_plugins = claude_catalog.get("plugins")
    if (
        claude_catalog.get("name") != catalog["name"]
        or not isinstance(claude_catalog.get("owner"), dict)
        or not isinstance(claude_catalog["owner"].get("name"), str)
        or not isinstance(claude_plugins, list)
        or len(claude_plugins) != 1
        or not isinstance(claude_plugins[0], dict)
        or claude_plugins[0].get("name") != metadata["name"]
        or claude_plugins[0].get("source") != "./"
        or claude_plugins[0].get("category") != plugin["category"]
    ):
        raise MarketplaceError("Claude marketplace structure or shared identity is invalid")
    return MarketplaceContract(
        commit=authority.commit, version=metadata["version"], skills=tuple(authority.skills)
    )
