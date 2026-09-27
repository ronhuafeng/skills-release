from __future__ import annotations

import hashlib
import tomllib
from dataclasses import dataclass
from typing import Any

from skills_profile_toml import normalize_profile, render_profile

from .fleet_domain import (
    HOST_AUDIT_SCHEMA_VERSION,
    SHA256_DIGEST_PATTERN,
    FleetConfigError,
    FleetManifest,
    HostTarget,
    RepoBinding,
    RepoSpec,
    SourceSpec,
    absolute_path,
    logical_id,
    reject_unknown_keys,
)
from .fleet_response import validate_host_audit_response


@dataclass(frozen=True)
class HostAuditRequest:
    host_id: str
    enrollment_id: str
    hostname: str
    username: str
    transport: str
    endpoint: str | None
    profile: str
    runtime: str
    global_registry: str
    source_bindings: dict[str, str]
    repo_bindings: dict[str, RepoBinding]
    manifest_digest: str
    profile_digest: str
    profile_toml: str
    sources: dict[str, SourceSpec]
    repos: dict[str, RepoSpec]

    @classmethod
    def from_manifest(
        cls,
        manifest: FleetManifest,
        host_id: str,
        rendered: dict[str, Any],
    ) -> HostAuditRequest:
        host = manifest.host(host_id)
        return cls(
            host_id=host.host_id,
            enrollment_id=host.enrollment_id,
            hostname=host.hostname,
            username=host.username,
            transport=host.transport,
            endpoint=host.endpoint,
            profile=host.profile,
            runtime=host.runtime,
            global_registry=host.global_registry,
            source_bindings={
                source_id: binding.path
                for source_id, binding in host.source_bindings.items()
            },
            repo_bindings=dict(host.repo_bindings),
            manifest_digest=str(rendered["manifest_digest"]),
            profile_digest=str(rendered["profile_digest"]),
            profile_toml=str(rendered["profile_toml"]),
            sources={
                source_id: manifest.sources[source_id]
                for source_id in sorted(host.source_bindings)
            },
            repos={
                repo_id: manifest.repos[repo_id]
                for repo_id in sorted(host.repo_bindings)
            },
        )

    @classmethod
    def from_raw(cls, raw: object) -> HostAuditRequest:
        if not isinstance(raw, dict):
            raise FleetConfigError("host audit request must be an object")
        required = (
            "host_id",
            "enrollment_id",
            "hostname",
            "username",
            "transport",
            "endpoint",
            "profile",
            "runtime",
            "global_registry",
            "source_bindings",
            "repo_bindings",
            "manifest_digest",
            "profile_digest",
            "profile_toml",
            "sources",
            "repos",
        )
        if raw.get("schema_version") != HOST_AUDIT_SCHEMA_VERSION:
            raise FleetConfigError(
                "host audit request schema_version must be "
                f"{HOST_AUDIT_SCHEMA_VERSION}"
            )
        for field in required:
            if field not in raw:
                raise FleetConfigError(f"host audit request missing field: {field}")
        reject_unknown_keys(
            raw,
            {"schema_version", *required},
            "host audit request",
        )
        raw_sources = raw["sources"]
        raw_repos = raw["repos"]
        raw_source_bindings = raw["source_bindings"]
        repo_bindings = raw["repo_bindings"]
        if not isinstance(raw_sources, dict) or not isinstance(
            raw_source_bindings,
            dict,
        ):
            raise FleetConfigError("host audit sources must be objects")
        if not isinstance(raw_repos, dict) or not isinstance(repo_bindings, dict):
            raise FleetConfigError("host audit repos must be objects")
        sources = {
            logical_id(source_id, "source_id"): SourceSpec.from_wire(
                source_id,
                source,
            )
            for source_id, source in raw_sources.items()
        }
        repos = {
            logical_id(repo_id, "repo_id"): RepoSpec.from_raw(repo_id, repo)
            for repo_id, repo in raw_repos.items()
        }
        source_bindings = {
            logical_id(source_id, "source_id"): absolute_path(
                path,
                f"host source {source_id}",
            )
            for source_id, path in raw_source_bindings.items()
        }
        target_raw = dict(raw)
        target_raw["source_bindings"] = {
            source_id: {"path": path}
            for source_id, path in source_bindings.items()
        }
        target = HostTarget.parse(
            raw["host_id"],
            target_raw,
            source_ids=set(sources),
            repo_ids=set(repos),
            source_bindings_key="source_bindings",
            repo_bindings_key="repo_bindings",
        )
        if set(source_bindings) != set(sources):
            raise FleetConfigError(
                "host audit source bindings must exactly match source records"
            )
        if set(target.repo_bindings) != set(repos):
            raise FleetConfigError(
                "host audit repo bindings must exactly match repo records"
            )
        manifest_digest = str(raw["manifest_digest"])
        profile_digest = str(raw["profile_digest"])
        if not SHA256_DIGEST_PATTERN.fullmatch(manifest_digest):
            raise FleetConfigError("host audit manifest_digest must be SHA-256")
        if not SHA256_DIGEST_PATTERN.fullmatch(profile_digest):
            raise FleetConfigError("host audit profile_digest must be SHA-256")
        profile_toml = str(raw["profile_toml"])
        try:
            profile = normalize_profile(tomllib.loads(profile_toml))
        except (TypeError, ValueError, tomllib.TOMLDecodeError) as exc:
            raise FleetConfigError(
                f"host audit profile_toml is invalid: {exc}"
            ) from exc
        if render_profile(profile) != profile_toml:
            raise FleetConfigError("host audit profile_toml must be canonical")
        profile_sources = set(profile.get("sources", {}))
        for repo_id, binding in target.repo_bindings.items():
            desired = set(binding.include) | set(binding.vendor)
            unknown = sorted(desired - profile_sources)
            if unknown:
                raise FleetConfigError(
                    f"repo {repo_id} refers to undeclared profile alias(es): "
                    + ", ".join(unknown)
                )
        if hashlib.sha256(profile_toml.encode()).hexdigest() != profile_digest:
            raise FleetConfigError(
                "host audit profile_digest does not match profile_toml"
            )
        return cls(
            host_id=target.host_id,
            enrollment_id=target.enrollment_id,
            hostname=target.hostname,
            username=target.username,
            transport=target.transport,
            endpoint=target.endpoint,
            profile=target.profile,
            runtime=target.runtime,
            global_registry=target.global_registry,
            source_bindings=source_bindings,
            repo_bindings=target.repo_bindings,
            manifest_digest=manifest_digest,
            profile_digest=profile_digest,
            profile_toml=profile_toml,
            sources=sources,
            repos=repos,
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": HOST_AUDIT_SCHEMA_VERSION,
            "host_id": self.host_id,
            "enrollment_id": self.enrollment_id,
            "hostname": self.hostname,
            "username": self.username,
            "transport": self.transport,
            "endpoint": self.endpoint,
            "profile": self.profile,
            "runtime": self.runtime,
            "global_registry": self.global_registry,
            "source_bindings": dict(sorted(self.source_bindings.items())),
            "repo_bindings": {
                repo_id: binding.as_dict()
                for repo_id, binding in sorted(self.repo_bindings.items())
            },
            "manifest_digest": self.manifest_digest,
            "profile_digest": self.profile_digest,
            "profile_toml": self.profile_toml,
            "sources": {
                source_id: source.as_wire_dict()
                for source_id, source in sorted(self.sources.items())
            },
            "repos": {
                repo_id: repo.as_dict() for repo_id, repo in sorted(self.repos.items())
            },
        }


@dataclass(frozen=True)
class HostAuditResult:
    payload: dict[str, Any]
    status: str

    @classmethod
    def from_raw(
        cls,
        raw: object,
        *,
        expected_request: HostAuditRequest,
    ) -> HostAuditResult:
        payload, status = validate_host_audit_response(
            raw,
            expected_request=expected_request,
        )
        return cls(payload=payload, status=status)

    def as_dict(self) -> dict[str, Any]:
        return self.payload
