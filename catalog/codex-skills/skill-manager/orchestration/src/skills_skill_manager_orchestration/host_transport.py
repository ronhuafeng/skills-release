from __future__ import annotations

import json
import posixpath
import shlex
import subprocess
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from typing import Any, Protocol

import tomllib

from .fleet_domain import (
    FLEET_SCHEMA_VERSION,
    FleetConfigError,
    FleetManifest,
    HostTarget,
    SourceSkill,
    logical_id,
)
from .fleet_protocol import HostAuditRequest, HostAuditResult
from .fleet_render import render_manifest_host
from .host_runtime import HOST_PROTOCOL_VERSION
from .source_remote import inspect_source_revision


class HostUnavailable(RuntimeError):
    pass


class HostRuntimeRejected(RuntimeError):
    pass


class HostTransport(Protocol):
    def request(
        self,
        runtime: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]: ...


class LocalHostTransport:
    def request(
        self,
        runtime: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        return _run_host_request([runtime, "_host"], payload)


class SSHHostTransport:
    def __init__(self, endpoint: str) -> None:
        self.endpoint = endpoint

    def request(
        self,
        runtime: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        remote_command = shlex.join([runtime, "_host"])
        return _run_host_request(
            [
                "/usr/bin/ssh",
                "-o",
                "BatchMode=yes",
                "--",
                self.endpoint,
                remote_command,
            ],
            payload,
        )

TransportFactory = Callable[[HostTarget], HostTransport]


def default_transport(host: HostTarget) -> HostTransport:
    if host.transport == "local":
        return LocalHostTransport()
    if host.endpoint is None:
        raise FleetConfigError(f"host {host.host_id} ssh endpoint is missing")
    return SSHHostTransport(host.endpoint)


def incomplete_host_result(
    spec: HostAuditRequest,
    *,
    drift_code: str,
    blocker: str,
    runtime_available: bool,
) -> dict[str, Any]:
    started_at = datetime.now(UTC).isoformat()
    rendered_profile = tomllib.loads(spec.profile_toml)
    source_results: dict[str, Any] = {}
    for source_id, source in spec.sources.items():
        source_root = spec.source_bindings[source_id]
        source_results[source_id] = {
            "path": source_root,
            "expected_origin": source.origin,
            "observed_origin": None,
            "expected_revision": source.revision,
            "observed_revision": None,
            "clean_worktree": None,
            "aliases": {
                alias: {
                    "path": posixpath.join(source_root, alias_spec.relative_path),
                    "expected_tree_oid": alias_spec.tree_oid,
                    "observed_tree_oid": None,
                    "metadata_valid": False,
                    "errors": ["target host state was not observed"],
                }
                for alias, alias_spec in source.skills.items()
            },
        }
    repo_results = {
        repo_id: {
            "path": spec.repo_bindings[repo_id].path,
            "status": "incomplete",
            "inspection_blocked": True,
            "expected_remote": repo.remote,
            "observed_remote": None,
            "desired_aliases": {
                "linked": list(spec.repo_bindings[repo_id].include),
                "vendored": list(spec.repo_bindings[repo_id].vendor),
                "owned": None,
            },
            "observed_aliases": None,
            "managed_snapshots": None,
            "links": None,
            "ownership": None,
            "git_visibility": None,
            "worktree_status": None,
            "unknown_directories": None,
            "unexpected_links": None,
            "unexpected_vendor_records": None,
            "registry_errors": None,
            "drift_codes": [],
            "blockers": ["target repo was not inspected"],
        }
        for repo_id, repo in spec.repos.items()
    }
    return {
        "schema_version": FLEET_SCHEMA_VERSION,
        "host_id": spec.host_id,
        "transport": spec.transport,
        "endpoint": spec.endpoint,
        "status": "incomplete",
        "runtime": {
            "path": spec.runtime,
            "protocol_version": None,
            "available": runtime_available,
        },
        "identity": {
            "expected": {
                "enrollment_id": spec.enrollment_id,
                "hostname": spec.hostname,
                "username": spec.username,
            },
            "observed": {
                "enrollment_id": None,
                "hostname": None,
                "username": None,
            },
            "matches": False,
            "errors": ["target host identity was not observed"],
        },
        "profile": {
            "path": spec.profile,
            "desired_digest": spec.profile_digest,
            "observed_digest": None,
            "matches": False,
        },
        "sources": source_results,
        "repos": repo_results,
        "registries": {
            "global": {
                "path": spec.global_registry,
                "desired": rendered_profile.get("global", {}).get("include", []),
                "observed": [],
                "links": {},
                "errors": {},
                "available": False,
            }
        },
        "drift_codes": [drift_code],
        "blockers": [blocker],
        "evidence_gaps": ["target host state"],
        "observation": {
            "started_at": started_at,
            "completed_at": datetime.now(UTC).isoformat(),
            "before_fingerprint": None,
            "after_fingerprint": None,
        },
    }


def _audit_runtime(
    spec: HostAuditRequest,
    transport: HostTransport,
) -> dict[str, Any]:
    request = {
        "schema_version": HOST_PROTOCOL_VERSION,
        "operation": "audit",
        "request": spec.as_dict(),
    }
    try:
        response = transport.request(spec.runtime, request)
        runtime_result = response["audit"]
        validated = HostAuditResult.from_raw(runtime_result, expected_request=spec)
    except HostUnavailable as exc:
        return incomplete_host_result(
            spec,
            drift_code=(
                "runtime_unavailable"
                if spec.transport == "local"
                else "transport_unavailable"
            ),
            blocker=str(exc),
            runtime_available=False,
        )
    except (HostRuntimeRejected, KeyError, TypeError, ValueError) as exc:
        return incomplete_host_result(
            spec,
            drift_code="runtime_incompatible",
            blocker=f"{spec.transport} runtime protocol is incompatible: {exc}",
            runtime_available=True,
        )
    return validated.as_dict()


def _audit_host(
    spec: HostAuditRequest,
    host: HostTarget,
    transport_factory: TransportFactory,
) -> dict[str, Any]:
    try:
        return _audit_runtime(spec, transport_factory(host))
    except Exception as exc:
        return incomplete_host_result(
            spec,
            drift_code="runtime_incompatible",
            blocker=f"{spec.transport} host audit failed: {exc}",
            runtime_available=True,
        )


def fleet_audit(
    manifest_path: Path | str,
    host_ids: list[str] | None = None,
    *,
    transport_factory: TransportFactory = default_transport,
    resolved_manifest: FleetManifest | None = None,
) -> dict[str, Any]:
    manifest = resolved_manifest or resolve_manifest_catalogs(
        FleetManifest.load(manifest_path), transport_factory=transport_factory
    )
    selected = (
        sorted({logical_id(host_id, "host_id") for host_id in host_ids})
        if host_ids
        else sorted(manifest.hosts)
    )
    if not selected:
        raise FleetConfigError("fleet audit requires at least one host")
    requests: list[tuple[HostAuditRequest, HostTarget]] = []
    for host_id in selected:
        rendered = render_manifest_host(manifest, host_id)
        request = HostAuditRequest.from_manifest(manifest, host_id, rendered)
        requests.append((request, manifest.host(host_id)))
    results_by_host: dict[str, dict[str, Any]] = {}
    with ThreadPoolExecutor(max_workers=min(len(requests), 4)) as executor:
        futures = {
            executor.submit(
                _audit_host,
                request,
                host,
                transport_factory,
            ): request
            for request, host in requests
        }
        for future in as_completed(futures):
            request = futures[future]
            results_by_host[request.host_id] = future.result()
    results = [results_by_host[host_id] for host_id in sorted(results_by_host)]
    statuses = {result["status"] for result in results}
    if "incomplete" in statuses:
        status = "incomplete"
    elif "drifted" in statuses:
        status = "drifted"
    else:
        status = "converged"
    return {
        "schema_version": FLEET_SCHEMA_VERSION,
        "status": status,
        "manifest_digest": manifest.digest,
        "hosts": results,
    }


def resolve_manifest_catalogs(
    manifest: FleetManifest,
    *,
    transport_factory: TransportFactory = default_transport,
) -> FleetManifest:
    catalogs: dict[str, dict[str, SourceSkill]] = {}
    for source_id, source in sorted(manifest.sources.items()):
        candidates = sorted(
            (
                host.transport != "local",
                host.host_id,
                host,
            )
            for host in manifest.hosts.values()
            if source_id in host.source_bindings
        )
        if not candidates:
            raise FleetConfigError(f"source {source_id} has no enrolled host binding")
        host = candidates[0][2]
        binding = host.source_bindings[source_id]
        if host.transport == "local":
            catalogs[source_id] = inspect_source_revision(
                binding.path,
                source.origin,
                source.revision,
            )
            continue
        response = transport_factory(host).request(
            host.runtime,
            {
                "schema_version": HOST_PROTOCOL_VERSION,
                "operation": "inspect_source_catalog",
                "source_root": binding.path,
                "expected_origin": source.origin,
                "revision": source.revision,
            },
        )
        raw_catalog = response.get("catalog")
        if not isinstance(raw_catalog, dict):
            raise HostRuntimeRejected(f"source {source_id} catalog evidence is incomplete")
        catalogs[source_id] = {
            str(alias): SourceSkill.from_raw(str(alias), skill)
            for alias, skill in raw_catalog.items()
        }
    return manifest.with_catalogs(catalogs)


def _run_host_request(
    command: list[str],
    payload: dict[str, Any],
) -> dict[str, Any]:
    try:
        completed = subprocess.run(
            command,
            input=json.dumps(payload, sort_keys=True),
            check=False,
            capture_output=True,
            text=True,
            timeout=120,
        )
    except OSError as exc:
        raise HostUnavailable(str(exc)) from exc
    except subprocess.TimeoutExpired as exc:
        raise HostUnavailable(str(exc)) from exc
    if completed.returncode != 0:
        detail = completed.stderr.strip() or "host runtime rejected the request"
        if completed.returncode == 255:
            raise HostUnavailable(detail)
        raise HostRuntimeRejected(detail)
    try:
        response = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise HostRuntimeRejected("host runtime returned invalid JSON") from exc
    if (
        not isinstance(response, dict)
        or response.get("schema_version") != HOST_PROTOCOL_VERSION
        or response.get("operation") != payload.get("operation")
    ):
        raise HostRuntimeRejected("host runtime response is incompatible")
    return response


__all__ = [
    "HostRuntimeRejected",
    "HostTransport",
    "HostUnavailable",
    "LocalHostTransport",
    "SSHHostTransport",
    "TransportFactory",
    "default_transport",
    "fleet_audit",
]
