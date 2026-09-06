from __future__ import annotations

import hashlib
import posixpath
from pathlib import Path
from typing import Any

from skills_profile_toml import render_profile

from .fleet_domain import FLEET_SCHEMA_VERSION, FleetManifest


def render_manifest_host(
    manifest: FleetManifest,
    host_id: str,
) -> dict[str, Any]:
    host = manifest.host(host_id)
    desired_global = host.desired_global(manifest.global_include)
    desired_aliases = set(desired_global)
    rendered_repos: dict[str, dict[str, list[str]]] = {}
    for _, binding in sorted(host.repo_bindings.items()):
        rendered_repos[binding.path] = {
            "include": list(binding.include),
            "vendor": list(binding.vendor),
        }
        desired_aliases.update(binding.include)
        desired_aliases.update(binding.vendor)

    alias_owners = manifest.alias_owners
    rendered_sources: dict[str, str] = {}
    required_source_ids: set[str] = set()
    for alias in sorted(desired_aliases):
        source_id = alias_owners[alias]
        source = manifest.sources[source_id]
        checkout_root = host.source_bindings[source_id].path
        required_source_ids.add(source_id)
        rendered_sources[alias] = posixpath.join(
            checkout_root,
            source.skills[alias].relative_path,
        )

    profile = {
        "source_roots": {
            source_id: posixpath.normpath(
                posixpath.join(
                    host.source_bindings[source_id].path,
                    host.source_bindings[source_id].discovery_path,
                )
            )
            for source_id in sorted(required_source_ids)
            if host.source_bindings[source_id].discovery_path is not None
        },
        "sources": rendered_sources,
        "global": {"include": list(desired_global)},
        "repos": rendered_repos,
    }
    profile_toml = render_profile(profile)
    return {
        "schema_version": FLEET_SCHEMA_VERSION,
        "status": "success",
        "host_id": host.host_id,
        "manifest_digest": manifest.digest,
        "profile_digest": hashlib.sha256(profile_toml.encode()).hexdigest(),
        "profile_toml": profile_toml,
        "validation_blockers": [],
    }


def render_host_profile(
    manifest_path: Path | str,
    host_id: str,
) -> dict[str, Any]:
    from .host_transport import resolve_manifest_catalogs

    manifest = resolve_manifest_catalogs(FleetManifest.load(manifest_path))
    return render_manifest_host(manifest, host_id)


__all__ = ["render_host_profile", "render_manifest_host"]
