from __future__ import annotations

import tempfile
import tomllib
from pathlib import Path
from typing import Any

from skills_profile_toml import profile_sources

from .core import (
    apply_sync_plan,
    apply_vendor_plan,
    plan_sync,
    plan_vendor,
)
from .enrollment import (
    _load_published_manifest,
    _select_current_host,
    AcceptedFleetRevision,
    accept_current_fleet_revision,
    read_host_identity,
)
from .fleet_audit import audit_host
from .fleet_domain import FleetConfigError, FleetManifest, canonical_digest
from .fleet_observe import file_digest, registry_fingerprint, run_git
from .fleet_protocol import HostAuditRequest
from .fleet_render import host_skill_policies, render_manifest_host
from .source_remote import (
    inspect_source_revision,
    materialize_source_checkout,
    validate_fetch_url,
)
from .skill_projection import materialize_host_projections


RECEIPT_VERSION = 1
PUBLICATION_DRIFT = {"git_visibility_drift", "vendor_provenance_drift"}


def apply_fleet_revision(
    manifest_path: Path,
    revision: str,
) -> dict[str, Any]:
    """Converge the current enrolled host from one published Fleet commit."""
    manifest = _load_published_manifest(manifest_path, revision)
    host, _, _ = _select_current_host(manifest)
    if read_host_identity().enrollment_id != host.enrollment_id:
        raise FleetConfigError("host enrollment identity does not match Fleet binding")

    before_fingerprint = _deployment_fingerprint(manifest, host.host_id)
    source_actions: list[dict[str, Any]] = []
    projection_actions: list[dict[str, Any]] = []
    phases: list[dict[str, Any]] = []
    error: str | None = None
    authority: AcceptedFleetRevision | None = None
    spec: HostAuditRequest | None = None
    before_audit: dict[str, Any] | None = None
    after_audit: dict[str, Any] | None = None
    placement_readback: dict[str, Any] = {
        "status": "incomplete",
        "pending_actions": None,
    }
    with tempfile.TemporaryDirectory(prefix="skill-manager-apply-") as directory:
        artifacts = Path(directory)
        current_phase: dict[str, Any] | None = None
        try:
            _materialize_host_sources(
                manifest,
                host.host_id,
                source_actions,
            )
            catalogs = {
                source_id: inspect_source_revision(
                    host.source_bindings[source_id].path,
                    source.origin,
                    source.revision,
                    host.source_bindings[source_id].discovery_path,
                )
                for source_id, source in sorted(manifest.sources.items())
            }
            resolved = manifest.with_catalogs(catalogs)
            projection_actions = materialize_host_projections(
                resolved,
                host.host_id,
            )
            authority = accept_current_fleet_revision(
                manifest_path,
                revision,
                profile_free=True,
                resolved_manifest=resolved,
            )
            rendered = render_manifest_host(resolved, host.host_id)
            spec = HostAuditRequest.from_manifest(resolved, host.host_id, rendered)
            before_audit = audit_host(spec)

            link_artifact = artifacts / "links.json"
            link_plan = plan_sync(
                _link_request(authority),
                link_artifact,
                authority=authority,
            )
            phases.append(_planned_phase("links", link_plan))
            vendor_plans: list[tuple[Path, dict[str, Any]]] = []
            for index, (repo, desired) in enumerate(_vendor_effects(authority)):
                artifact = artifacts / f"vendor-{index}.json"
                planned = plan_vendor(
                    _vendor_request(authority, Path(repo), desired),
                    artifact,
                    authority=authority,
                )
                phases.append(_planned_phase(f"vendor:{repo}", planned))
                vendor_plans.append((artifact, planned))

            if any(phase["plan_status"] != "success" for phase in phases):
                raise FleetConfigError("Fleet apply plan contains blockers")

            current_phase = phases[0]
            applied = apply_sync_plan(
                link_artifact,
                link_plan["digest"],
                False,
                authority=authority,
            )
            _mark_applied(phases[0], applied)
            for phase, (artifact, planned) in zip(
                phases[1:],
                vendor_plans,
                strict=True,
            ):
                current_phase = phase
                applied = apply_vendor_plan(
                    artifact,
                    planned["digest"],
                    False,
                    authority=authority,
                )
                _mark_applied(phase, applied)
        except (Exception, KeyboardInterrupt) as exc:
            if current_phase is not None and current_phase["status"] != "applied":
                current_phase["status"] = "failed"
            error = _error_text(exc)

        if authority is not None:
            try:
                placement_readback = _read_back_placements(authority, artifacts)
            except (Exception, KeyboardInterrupt) as exc:
                placement_readback = {
                    "status": "incomplete",
                    "pending_actions": None,
                    "error": _error_text(exc),
                }
                if error is None:
                    error = "placement readback failed"
        if spec is not None:
            try:
                after_audit = audit_host(spec)
            except (Exception, KeyboardInterrupt) as exc:
                if error is None:
                    error = f"final host audit failed: {_error_text(exc)}"

    fingerprint_gap: str | None = None
    try:
        after_fingerprint: str | None = _deployment_fingerprint(
            manifest,
            host.host_id,
        )
    except (Exception, KeyboardInterrupt) as exc:
        after_fingerprint = None
        fingerprint_gap = "deployment fingerprint"
        if error is None:
            error = f"final deployment fingerprint failed: {_error_text(exc)}"
    pending_publication = _pending_repository_publication(after_audit)
    if error is None and placement_readback["status"] != "converged":
        error = "final placement readback did not converge"
    if error is None and not _audit_accepts_placement(after_audit):
        error = "final host audit found non-publication drift"
    receipt = {
        "version": RECEIPT_VERSION,
        "status": "success" if error is None else "partial",
        "target": {
            "host_id": host.host_id,
            "enrollment_id": host.enrollment_id,
        },
        "config_revision": revision,
        "manifest_digest": manifest.digest,
        "source_actions": source_actions,
        "projection_actions": projection_actions,
        "skill_policies": (
            {}
            if authority is None
            else host_skill_policies(resolved, host.host_id)
        ),
        "actions": phases,
        "before_fingerprint": before_fingerprint,
        "after_fingerprint": after_fingerprint,
        "readback": {
            "placement": placement_readback,
            "before_status": None if before_audit is None else before_audit["status"],
            "after_status": None if after_audit is None else after_audit["status"],
            "drift_codes": [] if after_audit is None else after_audit["drift_codes"],
            "blockers": [] if after_audit is None else after_audit["blockers"],
            "evidence_gaps": _receipt_evidence_gaps(
                after_audit,
                fingerprint_gap,
            ),
            "pending_repository_publication": pending_publication,
        },
        "error": error,
    }
    receipt["receipt_digest"] = canonical_digest(receipt)
    return receipt


def _materialize_host_sources(
    manifest: FleetManifest,
    host_id: str,
    actions: list[dict[str, Any]],
) -> None:
    host = manifest.host(host_id)
    if set(host.source_bindings) != set(manifest.sources):
        raise FleetConfigError(
            "Fleet apply requires a managed binding for every declared source"
        )
    for source_id, binding in sorted(host.source_bindings.items()):
        source = manifest.sources[source_id]
        if binding.fetch_url is None:
            raise FleetConfigError(
                f"host source {source_id} requires fetch_url for Fleet apply"
            )
        validate_fetch_url(binding.fetch_url, source.origin)
        action: dict[str, Any] = {
            "source_id": source_id,
            "revision": source.revision,
            "status": "pending",
        }
        actions.append(action)
        try:
            action["status"] = materialize_source_checkout(
                source_id,
                binding.path,
                source.origin,
                source.revision,
                fetch_url=binding.fetch_url,
            )
        except (Exception, KeyboardInterrupt) as exc:
            action["status"] = "failed"
            action["error"] = _error_text(exc)
            raise


def _profile(authority: AcceptedFleetRevision) -> dict[str, Any]:
    return tomllib.loads(authority.profile_toml)


def _link_request(authority: AcceptedFleetRevision) -> dict[str, Any]:
    profile = _profile(authority)
    registries = [
        {
            "scope": "global",
            "directory": authority.global_registry,
            "desired": list(profile.get("global", {}).get("include", [])),
        }
    ]
    for repo, desired in sorted(authority.linked_scopes.items()):
        registries.append(
            {
                "scope": repo,
                "directory": str(Path(repo) / ".agents" / "skills"),
                "desired": list(desired),
            }
        )
    return {
        "profile": profile,
        "sources": {
            name: str(path) for name, path in profile_sources(profile).items()
        },
        "registries": registries,
    }


def _vendor_request(
    authority: AcceptedFleetRevision,
    repo: Path,
    desired: tuple[str, ...],
) -> dict[str, Any]:
    profile = _profile(authority)
    return {
        "profile": profile,
        "repo": str(repo),
        "registry": str(repo / ".agents" / "skills"),
        "state_path": str(repo / ".agents" / "skill-manager" / "vendor-lock.json"),
        "sources": {
            name: str(path) for name, path in profile_sources(profile).items()
        },
        "desired": list(desired),
    }


def _planned_phase(name: str, plan: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": name,
        "plan_digest": plan["digest"],
        "plan_status": plan["status"],
        "planned": plan["actions"],
        "applied_actions": None,
        "status": "planned",
    }


def _mark_applied(phase: dict[str, Any], result: dict[str, Any]) -> None:
    phase["applied_actions"] = result["applied_actions"]
    phase["status"] = "applied"


def _read_back_placements(
    authority: AcceptedFleetRevision,
    artifacts: Path,
) -> dict[str, Any]:
    plans: list[dict[str, Any]] = []
    link = plan_sync(
        _link_request(authority),
        artifacts / "readback-links.json",
        authority=authority,
    )
    plans.append({"name": "links", "status": link["status"], "actions": link["actions"]})
    for index, (repo, desired) in enumerate(_vendor_effects(authority)):
        vendor = plan_vendor(
            _vendor_request(authority, Path(repo), desired),
            artifacts / f"readback-vendor-{index}.json",
            authority=authority,
        )
        plans.append(
            {
                "name": f"vendor:{repo}",
                "status": vendor["status"],
                "actions": vendor["actions"],
            }
        )
    pending = sum(_pending_count(plan["actions"]) for plan in plans)
    return {
        "status": (
            "converged"
            if pending == 0 and all(plan["status"] == "success" for plan in plans)
            else "drifted"
        ),
        "pending_actions": pending,
        "plans": plans,
    }


def _vendor_effects(
    authority: AcceptedFleetRevision,
) -> list[tuple[str, tuple[str, ...]]]:
    return [
        (repo, desired)
        for repo, desired in sorted(authority.vendored_scopes.items())
        if desired
        or (
            Path(repo) / ".agents" / "skill-manager" / "vendor-lock.json"
        ).exists()
    ]


def _pending_count(actions: dict[str, Any]) -> int:
    return sum(
        int(value)
        for name, value in actions.items()
        if name not in {"unchanged", "preserved"}
    )


def _pending_repository_publication(
    audit: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    if audit is None:
        return []
    pending = []
    for repo_id, repo in sorted(audit["repos"].items()):
        drift = sorted(set(repo["drift_codes"]) & PUBLICATION_DRIFT)
        if drift:
            pending.append(
                {
                    "repo_id": repo_id,
                    "path": repo["path"],
                    "drift_codes": drift,
                }
            )
    return pending


def _audit_accepts_placement(audit: dict[str, Any] | None) -> bool:
    if audit is None or audit["blockers"] or audit["evidence_gaps"]:
        return False
    return set(audit["drift_codes"]) <= PUBLICATION_DRIFT


def _receipt_evidence_gaps(
    audit: dict[str, Any] | None,
    fingerprint_gap: str | None,
) -> list[str]:
    gaps = [] if audit is None else list(audit["evidence_gaps"])
    if fingerprint_gap is not None and fingerprint_gap not in gaps:
        gaps.append(fingerprint_gap)
    return gaps


def _deployment_fingerprint(manifest: FleetManifest, host_id: str) -> str:
    host = manifest.host(host_id)
    facts: dict[str, Any] = {
        "sources": {
            source_id: _git_path_facts(Path(binding.path))
            for source_id, binding in sorted(host.source_bindings.items())
        },
        "global_registry": registry_fingerprint(Path(host.global_registry)),
        "repos": {},
    }
    for repo_id, binding in sorted(host.repo_bindings.items()):
        repo = Path(binding.path)
        facts["repos"][repo_id] = {
            "git": _git_path_facts(repo),
            "registry": registry_fingerprint(repo / ".agents" / "skills"),
            "vendor_lock": file_digest(
                repo / ".agents" / "skill-manager" / "vendor-lock.json"
            ),
        }
    return canonical_digest(facts)


def _git_path_facts(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"exists": False}
    try:
        return {
            "exists": True,
            "root": run_git(path, "rev-parse", "--show-toplevel"),
            "head": run_git(path, "rev-parse", "HEAD"),
            "origin": run_git(path, "config", "--get", "remote.origin.url"),
            "status": run_git(
                path,
                "status",
                "--ignored",
                "--porcelain",
                "--untracked-files=all",
            ),
        }
    except (OSError, RuntimeError) as exc:
        return {"exists": True, "error": str(exc)}


def _error_text(error: BaseException) -> str:
    if isinstance(error, KeyboardInterrupt):
        return "interrupted"
    return str(error) or error.__class__.__name__


__all__ = ["RECEIPT_VERSION", "apply_fleet_revision"]
