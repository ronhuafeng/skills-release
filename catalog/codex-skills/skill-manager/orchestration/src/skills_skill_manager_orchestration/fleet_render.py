from __future__ import annotations

import hashlib
import posixpath
from pathlib import Path
from typing import Any

from skills_profile_toml import render_profile

from .fleet_domain import FLEET_SCHEMA_VERSION, FleetManifest
from .skill_projection import projection_path


def host_skill_policies(
    manifest: FleetManifest,
    host_id: str,
) -> dict[str, dict[str, Any]]:
    host = manifest.host(host_id)
    desired = set(host.desired_global(manifest.global_include))
    for binding in host.repo_bindings.values():
        desired.update(binding.include)
        desired.update(binding.vendor)
    result: dict[str, dict[str, Any]] = {}
    for alias in sorted(desired):
        resolved = manifest.resolved_skill(alias)
        configured = manifest.skills.get(alias)
        result[alias] = {
            "source": resolved.source_id,
            "source_name": resolved.source_name,
            "source_default": manifest.sources[
                resolved.source_id
            ].default_implicit_invocation,
            "skill_override": (
                "default" if configured is None else configured.implicit_invocation
            ),
            "effective": resolved.implicit_invocation,
            "projected": resolved.requires_projection,
        }
    return result


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

    rendered_sources: dict[str, str] = {}
    required_source_ids: set[str] = set()
    for alias in sorted(desired_aliases):
        skill = manifest.resolved_skill(alias)
        source_id = skill.source_id
        checkout_root = host.source_bindings[source_id].path
        required_source_ids.add(source_id)
        rendered_sources[alias] = (
            projection_path(manifest, host, skill)
            if skill.requires_projection
            else posixpath.join(checkout_root, skill.relative_path)
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
        "skill_policies": host_skill_policies(manifest, host_id),
        "validation_blockers": [],
    }


def render_host_profile(
    manifest_path: Path | str,
    host_id: str,
) -> dict[str, Any]:
    from .host_transport import resolve_manifest_catalogs

    manifest = resolve_manifest_catalogs(FleetManifest.load(manifest_path))
    return render_manifest_host(manifest, host_id)


__all__ = ["host_skill_policies", "render_host_profile", "render_manifest_host"]
