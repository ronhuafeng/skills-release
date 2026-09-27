from __future__ import annotations

import posixpath
import tomllib
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from skills_profile_toml import normalize_profile, validate_skill_name

from .fleet_domain import (
    HOST_AUDIT_SCHEMA_VERSION,
    GIT_OBJECT_ID_PATTERN,
    SHA256_DIGEST_PATTERN,
    FleetConfigError,
    canonical_enrollment_id,
    reject_unknown_keys,
)

if TYPE_CHECKING:
    from .fleet_protocol import HostAuditRequest


@dataclass(frozen=True)
class _ResponseValidationContext:
    request: HostAuditRequest
    expected_profile: dict[str, Any]

    @classmethod
    def from_request(
        cls,
        request: HostAuditRequest,
    ) -> _ResponseValidationContext:
        return cls(
            request=request,
            expected_profile=normalize_profile(tomllib.loads(request.profile_toml)),
        )


def validate_host_audit_response(
    raw: object,
    *,
    expected_request: HostAuditRequest,
) -> tuple[dict[str, Any], str]:
    payload, status = _validate_envelope(raw, expected_request)
    context = _ResponseValidationContext.from_request(expected_request)
    _validate_runtime(payload["runtime"], context)
    identity = _validate_identity(payload["identity"], context)
    profile = _validate_profile(payload["profile"], context)
    global_registry, global_links = _validate_global_registry(
        payload["registries"],
        context,
    )
    sources = _validate_sources(payload["sources"], context)
    repos = _validate_repos(payload["repos"], context)
    drift_codes = _response_string_list(payload["drift_codes"], "drift_codes")
    blockers = _response_string_list(payload["blockers"], "blockers")
    evidence_gaps = _response_string_list(
        payload["evidence_gaps"],
        "evidence_gaps",
    )
    observation = _validate_observation(payload["observation"])
    _validate_status_consistency(
        status=status,
        drift_codes=drift_codes,
        blockers=blockers,
        evidence_gaps=evidence_gaps,
        observation=observation,
    )
    if status == "converged":
        _validate_converged_response(
            profile=profile,
            identity=identity,
            global_registry=global_registry,
            global_links=global_links,
            sources=sources,
            repos=repos,
            context=context,
        )
    return payload, status


def _validate_envelope(
    raw: object,
    expected_request: HostAuditRequest,
) -> tuple[dict[str, Any], str]:
    if not isinstance(raw, dict):
        raise FleetConfigError("host audit response must be an object")
    required = {
        "schema_version",
        "host_id",
        "transport",
        "endpoint",
        "status",
        "runtime",
        "identity",
        "profile",
        "sources",
        "repos",
        "registries",
        "drift_codes",
        "blockers",
        "evidence_gaps",
        "observation",
    }
    reject_unknown_keys(raw, required, "host audit response")
    missing = sorted(required - set(raw))
    if missing:
        raise FleetConfigError(f"host audit response missing field: {missing[0]}")
    if (
        type(raw["schema_version"]) is not int
        or raw["schema_version"] != HOST_AUDIT_SCHEMA_VERSION
    ):
        raise FleetConfigError(
            "host audit response schema_version must be "
            f"{HOST_AUDIT_SCHEMA_VERSION}"
        )
    if _response_string(raw["host_id"], "host_id") != expected_request.host_id:
        raise FleetConfigError("host audit response host_id does not match request")
    if _response_string(raw["transport"], "transport") != expected_request.transport:
        raise FleetConfigError("host audit response transport is invalid")
    endpoint = raw["endpoint"]
    if endpoint is not None:
        _response_string(endpoint, "endpoint")
    if endpoint != expected_request.endpoint:
        raise FleetConfigError("host audit response endpoint does not match request")
    status = _response_string(raw["status"], "status")
    if status not in {"converged", "drifted", "incomplete"}:
        raise FleetConfigError("host audit response status is invalid")
    return raw, status


def _validate_identity(
    value: object,
    context: _ResponseValidationContext,
) -> dict[str, Any]:
    identity = _response_exact_table(
        value,
        "identity",
        {"expected", "observed", "matches", "errors"},
    )
    expected = _response_exact_table(
        identity["expected"],
        "identity.expected",
        {"enrollment_id", "hostname", "username"},
    )
    if expected != {
        "enrollment_id": context.request.enrollment_id,
        "hostname": context.request.hostname,
        "username": context.request.username,
    }:
        raise FleetConfigError("host audit response identity does not match request")
    observed = _response_exact_table(
        identity["observed"],
        "identity.observed",
        {"enrollment_id", "hostname", "username"},
    )
    enrollment_id = observed["enrollment_id"]
    if enrollment_id is not None:
        canonical_enrollment_id(enrollment_id, "identity.observed.enrollment_id")
    _response_optional_string(observed["hostname"], "identity.observed.hostname")
    _response_optional_string(observed["username"], "identity.observed.username")
    _response_bool(identity["matches"], "identity.matches")
    _response_string_list(identity["errors"], "identity.errors")
    return identity


def _validate_runtime(
    value: object,
    context: _ResponseValidationContext,
) -> dict[str, Any]:
    runtime = _response_exact_table(
        value,
        "runtime",
        {"path", "protocol_version", "available"},
    )
    if (
        _response_string(runtime["path"], "runtime.path") != context.request.runtime
        or _response_int(
            runtime["protocol_version"],
            "runtime.protocol_version",
        )
        != HOST_AUDIT_SCHEMA_VERSION
        or _response_bool(runtime["available"], "runtime.available") is not True
    ):
        raise FleetConfigError("host audit response runtime is incompatible")
    return runtime


def _validate_profile(
    value: object,
    context: _ResponseValidationContext,
) -> dict[str, Any]:
    profile = _response_exact_table(
        value,
        "profile",
        {
            "path",
            "desired_digest",
            "observed_digest",
            "matches",
        },
    )
    if _response_string(profile["path"], "profile.path") != context.request.profile:
        raise FleetConfigError(
            "host audit response profile path does not match request"
        )
    if (
        _response_digest(
            profile["desired_digest"],
            "profile.desired_digest",
        )
        != context.request.profile_digest
    ):
        raise FleetConfigError(
            "host audit response profile digest does not match request"
        )
    _response_optional_digest(
        profile["observed_digest"],
        "profile.observed_digest",
    )
    _response_bool(profile["matches"], "profile.matches")
    return profile


def _validate_global_registry(
    value: object,
    context: _ResponseValidationContext,
) -> tuple[dict[str, Any], dict[str, Any]]:
    registries = _response_exact_table(value, "registries", {"global"})
    global_registry = _response_exact_table(
        registries["global"],
        "registries.global",
        {"path", "desired", "observed", "links", "errors"},
    )
    if (
        _response_string(
            global_registry["path"],
            "registries.global.path",
        )
        != context.request.global_registry
    ):
        raise FleetConfigError(
            "host audit response global registry path does not match request"
        )
    for field in ("desired", "observed"):
        _response_string_list(
            global_registry[field],
            f"registries.global.{field}",
        )
    _response_error_map(
        global_registry["errors"],
        "registries.global.errors",
    )
    expected_global = context.expected_profile.get("global", {}).get("include", [])
    if global_registry["desired"] != expected_global:
        raise FleetConfigError(
            "host audit response global desired state does not match request"
        )
    global_links = _response_link_map(
        global_registry["links"],
        "registries.global.links",
    )
    if set(global_links) != set(expected_global):
        raise FleetConfigError(
            "host audit response global link scope does not match request"
        )
    for alias, link in global_links.items():
        validate_skill_name(alias, "global alias")
        if link["desired_target"] != context.expected_profile.get("sources", {}).get(
            alias
        ):
            raise FleetConfigError(
                f"host audit response global link {alias} does not match request"
            )
    return global_registry, global_links


def _validate_sources(
    value: object,
    context: _ResponseValidationContext,
) -> dict[str, Any]:
    sources = _response_table(value, "sources")
    if set(sources) != set(context.request.sources):
        raise FleetConfigError(
            "host audit response source scope does not match request"
        )
    for source_id, source in sources.items():
        _validate_source(source_id, source, context)
    return sources


def _validate_source(
    source_id: str,
    value: object,
    context: _ResponseValidationContext,
) -> dict[str, Any]:
    source_table = _response_exact_table(
        value,
        f"source {source_id}",
        {
            "path",
            "expected_origin",
            "observed_origin",
            "expected_revision",
            "observed_revision",
            "clean_worktree",
            "aliases",
        },
    )
    expected_source = context.request.sources[source_id]
    if (
        _response_string(
            source_table["path"],
            f"source {source_id}.path",
        )
        != context.request.source_bindings[source_id]
        or _response_string(
            source_table["expected_origin"],
            f"source {source_id}.expected_origin",
        )
        != expected_source.origin
        or _response_string(
            source_table["expected_revision"],
            f"source {source_id}.expected_revision",
        )
        != expected_source.revision
    ):
        raise FleetConfigError(
            f"host audit response source {source_id} identity does not match request"
        )
    _response_optional_string(
        source_table["observed_origin"],
        f"source {source_id}.observed_origin",
    )
    _response_optional_string(
        source_table["observed_revision"],
        f"source {source_id}.observed_revision",
    )
    _response_optional_bool(
        source_table["clean_worktree"],
        f"source {source_id}.clean_worktree",
    )
    _validate_source_aliases(
        source_table["aliases"],
        source_id,
        context,
    )
    return source_table


def _validate_source_aliases(
    value: object,
    source_id: str,
    context: _ResponseValidationContext,
) -> dict[str, Any]:
    aliases = _response_table(value, f"source {source_id} aliases")
    expected_aliases = context.request.sources[source_id].skills
    if set(aliases) != set(expected_aliases):
        raise FleetConfigError(
            f"host audit response source {source_id} alias scope does not match request"
        )
    for alias, alias_result in aliases.items():
        if type(alias) is not str:
            raise FleetConfigError(
                "host audit response source alias name must be a string"
            )
        validate_skill_name(alias, "source alias")
        alias_table = _response_exact_table(
            alias_result,
            f"source alias {alias}",
            {
                "path",
                "expected_tree_oid",
                "observed_tree_oid",
                "metadata_valid",
                "errors",
            },
        )
        expected_alias = expected_aliases[alias]
        expected_alias_path = posixpath.join(
            context.request.source_bindings[source_id],
            expected_alias.relative_path,
        )
        if (
            _response_string(
                alias_table["path"],
                f"source alias {alias}.path",
            )
            != expected_alias_path
            or _response_git_oid(
                alias_table["expected_tree_oid"],
                f"source alias {alias}.expected_tree_oid",
            )
            != expected_alias.tree_oid
        ):
            raise FleetConfigError(
                f"host audit response source alias {alias} does not match request"
            )
        _response_optional_git_oid(
            alias_table["observed_tree_oid"],
            f"source alias {alias}.observed_tree_oid",
        )
        _response_bool(
            alias_table["metadata_valid"],
            f"source alias {alias}.metadata_valid",
        )
        _response_string_list(
            alias_table["errors"],
            f"source alias {alias} errors",
        )
    return aliases


def _validate_repos(
    value: object,
    context: _ResponseValidationContext,
) -> dict[str, Any]:
    repos = _response_table(value, "repos")
    if set(repos) != set(context.request.repos):
        raise FleetConfigError("host audit response repo scope does not match request")
    for repo_id, repo in repos.items():
        _validate_repo(repo_id, repo, context)
    return repos


def _validate_repo(
    repo_id: str,
    value: object,
    context: _ResponseValidationContext,
) -> dict[str, Any]:
    repo_table = _response_exact_table(
        value,
        f"repo {repo_id}",
        {
            "path",
            "status",
            "inspection_blocked",
            "expected_remote",
            "observed_remote",
            "desired_aliases",
            "observed_aliases",
            "managed_snapshots",
            "links",
            "ownership",
            "git_visibility",
            "worktree_status",
            "unknown_directories",
            "unexpected_links",
            "unexpected_vendor_records",
            "registry_errors",
            "drift_codes",
            "blockers",
        },
    )
    expected_repo = context.request.repos[repo_id]
    expected_binding = context.request.repo_bindings[repo_id]
    if (
        _response_string(
            repo_table["path"],
            f"repo {repo_id}.path",
        )
        != expected_binding.path
        or _response_string(
            repo_table["expected_remote"],
            f"repo {repo_id}.expected_remote",
        )
        != expected_repo.remote
    ):
        raise FleetConfigError(
            f"host audit response repo {repo_id} identity does not match request"
        )
    _response_optional_string(
        repo_table["observed_remote"],
        f"repo {repo_id}.observed_remote",
    )
    inspection_blocked = _response_bool(
        repo_table["inspection_blocked"],
        f"repo {repo_id}.inspection_blocked",
    )
    desired_aliases = _response_alias_set(
        repo_table["desired_aliases"],
        f"repo {repo_id} desired_aliases",
        allow_owned_none=inspection_blocked,
    )
    if desired_aliases["linked"] != list(expected_binding.include) or desired_aliases[
        "vendored"
    ] != list(expected_binding.vendor):
        raise FleetConfigError(
            f"host audit response repo {repo_id} desired state does not match request"
        )
    repo_status = _response_string(
        repo_table["status"],
        f"repo {repo_id}.status",
    )
    if repo_status not in {"converged", "drifted", "incomplete"}:
        raise FleetConfigError(f"host audit response repo {repo_id} status is invalid")
    _response_string_list(
        repo_table["drift_codes"],
        f"repo {repo_id} drift_codes",
    )
    _response_string_list(
        repo_table["blockers"],
        f"repo {repo_id} blockers",
    )
    if inspection_blocked:
        _validate_blocked_repo(repo_id, repo_status, repo_table)
    else:
        _validate_inspected_repo(
            repo_id,
            repo_table,
            desired_aliases,
            context,
        )
    return repo_table


def _validate_blocked_repo(
    repo_id: str,
    repo_status: str,
    repo_table: dict[str, Any],
) -> None:
    if repo_status != "incomplete":
        raise FleetConfigError(
            f"host audit response repo {repo_id} blocked status is invalid"
        )
    for field in (
        "observed_aliases",
        "managed_snapshots",
        "links",
        "ownership",
        "git_visibility",
        "worktree_status",
        "unknown_directories",
        "unexpected_links",
        "unexpected_vendor_records",
        "registry_errors",
    ):
        if repo_table[field] is not None:
            raise FleetConfigError(
                f"host audit response repo {repo_id} {field} must be null "
                "when inspection is blocked"
            )


def _validate_inspected_repo(
    repo_id: str,
    repo_table: dict[str, Any],
    desired_aliases: dict[str, Any],
    context: _ResponseValidationContext,
) -> None:
    observed_aliases = _response_alias_set(
        repo_table["observed_aliases"],
        f"repo {repo_id} observed_aliases",
    )
    if observed_aliases["owned"] is None:
        raise FleetConfigError(
            f"host audit response repo {repo_id} "
            "observed owned aliases must be an array"
        )
    unexpected_vendor_records = _response_string_list(
        repo_table["unexpected_vendor_records"],
        f"repo {repo_id}.unexpected_vendor_records",
    )
    desired_vendors = desired_aliases["vendored"]
    _validate_managed_snapshots(
        repo_table["managed_snapshots"],
        repo_id,
        sorted(set(desired_vendors) | set(unexpected_vendor_records)),
    )
    _validate_ownership(
        repo_table["ownership"],
        repo_id,
        desired_aliases,
        context,
    )
    required_visibility = _validate_git_visibility(
        repo_table["git_visibility"],
        repo_id,
        desired_aliases,
    )
    if desired_vendors and (
        ".agents/skill-manager/vendor-lock.json" not in required_visibility
    ):
        raise FleetConfigError(
            f"host audit response repo {repo_id} omits vendor-lock visibility"
        )
    repo_links = _response_link_map(
        repo_table["links"],
        f"repo {repo_id} links",
    )
    if set(repo_links) != (
        set(desired_aliases["linked"]) | set(observed_aliases["linked"])
    ):
        raise FleetConfigError(
            f"host audit response repo {repo_id} link scope does not match request"
        )
    for alias, link in repo_links.items():
        validate_skill_name(alias, "repo link alias")
        if link["desired_target"] != context.expected_profile.get("sources", {}).get(
            alias
        ):
            raise FleetConfigError(
                f"host audit response repo {repo_id} link "
                f"{alias} does not match request"
            )
    _response_optional_string(
        repo_table["worktree_status"],
        f"repo {repo_id}.worktree_status",
    )
    for field in ("unknown_directories", "unexpected_links"):
        _response_string_list(
            repo_table[field],
            f"repo {repo_id}.{field}",
        )
    _response_error_map(
        repo_table["registry_errors"],
        f"repo {repo_id}.registry_errors",
    )


def _validate_managed_snapshots(
    value: object,
    repo_id: str,
    desired_vendors: list[str],
) -> dict[str, Any]:
    snapshots = _response_table(value, f"repo {repo_id} managed_snapshots")
    if set(snapshots) != set(desired_vendors):
        raise FleetConfigError(
            f"host audit response repo {repo_id} snapshot scope does not match request"
        )
    digest_fields = {
        "record_source_digest",
        "record_target_digest",
        "source_digest",
        "target_digest",
    }
    for alias, snapshot in snapshots.items():
        snapshot_table = _response_exact_table(
            snapshot,
            f"repo {repo_id} snapshot {alias}",
            digest_fields,
        )
        for field in digest_fields:
            _response_optional_digest(
                snapshot_table[field],
                f"repo {repo_id} snapshot {alias}.{field}",
            )
    return snapshots


def _validate_ownership(
    value: object,
    repo_id: str,
    desired_aliases: dict[str, Any],
    context: _ResponseValidationContext,
) -> dict[str, Any]:
    ownership = _response_exact_table(
        value,
        f"repo {repo_id} ownership",
        {
            "path",
            "declared",
            "accepted",
            "matches_committed",
        },
    )
    _response_string_list(
        ownership["declared"],
        f"repo {repo_id} ownership.declared",
    )
    _response_string_list(
        ownership["accepted"],
        f"repo {repo_id} ownership.accepted",
    )
    _response_optional_bool(
        ownership["matches_committed"],
        f"repo {repo_id} ownership.matches_committed",
    )
    expected_path = posixpath.join(
        context.request.repo_bindings[repo_id].path,
        ".agents/skill-manager/ownership.toml",
    )
    if (
        _response_string(
            ownership["path"],
            f"repo {repo_id} ownership.path",
        )
        != expected_path
        or ownership["declared"] != desired_aliases["owned"]
    ):
        raise FleetConfigError(
            f"host audit response repo {repo_id} "
            "ownership does not match observed declaration"
        )
    return ownership


def _validate_git_visibility(
    value: object,
    repo_id: str,
    desired_aliases: dict[str, Any],
) -> list[str]:
    visibility = _response_exact_table(
        value,
        f"repo {repo_id} git_visibility",
        {"required", "missing"},
    )
    required = _response_string_list(
        visibility["required"],
        f"repo {repo_id} git_visibility.required",
    )
    _response_string_list(
        visibility["missing"],
        f"repo {repo_id} git_visibility.missing",
    )
    for alias in [
        *desired_aliases["vendored"],
        *desired_aliases["owned"],
    ]:
        if f".agents/skills/{alias}" not in required:
            raise FleetConfigError(
                f"host audit response repo {repo_id} omits visibility for {alias}"
            )
    if desired_aliases["owned"] and (
        ".agents/skill-manager/ownership.toml" not in required
    ):
        raise FleetConfigError(
            f"host audit response repo {repo_id} omits ownership visibility"
        )
    return required


def _validate_observation(value: object) -> dict[str, Any]:
    observation = _response_exact_table(
        value,
        "observation",
        {
            "started_at",
            "completed_at",
            "before_fingerprint",
            "after_fingerprint",
        },
    )
    for field in ("started_at", "completed_at"):
        _response_string(
            observation[field],
            f"observation.{field}",
            nonempty=True,
        )
    for field in ("before_fingerprint", "after_fingerprint"):
        _response_digest(
            observation[field],
            f"observation.{field}",
        )
    return observation


def _validate_status_consistency(
    *,
    status: str,
    drift_codes: list[str],
    blockers: list[str],
    evidence_gaps: list[str],
    observation: dict[str, Any],
) -> None:
    unstable = observation["before_fingerprint"] != observation["after_fingerprint"]
    expected_status = (
        "incomplete"
        if blockers or evidence_gaps or unstable
        else "drifted"
        if drift_codes
        else "converged"
    )
    if status != expected_status:
        raise FleetConfigError(
            "host audit response status is inconsistent with its evidence"
        )
    if unstable and "concurrent_change" not in drift_codes:
        raise FleetConfigError(
            "host audit response omits concurrent_change for unstable evidence"
        )


def _validate_converged_response(
    *,
    profile: dict[str, Any],
    identity: dict[str, Any],
    global_registry: dict[str, Any],
    global_links: dict[str, Any],
    sources: dict[str, Any],
    repos: dict[str, Any],
    context: _ResponseValidationContext,
) -> None:
    if identity["matches"] is not True or identity["errors"]:
        raise FleetConfigError("converged host audit response has identity drift")
    if profile["matches"] is not True:
        raise FleetConfigError("converged host audit response has profile drift")
    if global_registry["desired"] != global_registry["observed"]:
        raise FleetConfigError("converged host audit response has registry drift")
    if global_registry["errors"]:
        raise FleetConfigError("converged host audit response has registry errors")
    if set(global_registry["desired"]) != set(global_links):
        raise FleetConfigError(
            "converged host audit response omits global link evidence"
        )
    for link in global_links.values():
        if (
            link["observed_target"] is None
            or link["metadata_valid"] is not True
            or link["errors"]
        ):
            raise FleetConfigError(
                "converged host audit response has global link drift"
            )
    for source in sources.values():
        if (
            source["expected_origin"] != source["observed_origin"]
            or source["expected_revision"] != source["observed_revision"]
            or source["clean_worktree"] is not True
        ):
            raise FleetConfigError(
                "converged host audit response has source identity drift"
            )
        for alias in source["aliases"].values():
            if (
                alias["expected_tree_oid"] != alias["observed_tree_oid"]
                or alias["metadata_valid"] is not True
                or alias["errors"]
            ):
                raise FleetConfigError(
                    "converged host audit response has source content drift"
                )
    for repo in repos.values():
        _validate_converged_repo(repo)


def _validate_converged_repo(
    repo: dict[str, Any],
) -> None:
    if repo["status"] != "converged" or repo["inspection_blocked"] is not False:
        raise FleetConfigError("converged host audit response has repo drift")

    repo_links = repo.get("links")
    snapshot_evidence_valid = all(
        all(snapshot.values()) and len(set(snapshot.values())) == 1
        for snapshot in repo["managed_snapshots"].values()
    )
    owned_aliases = repo["desired_aliases"].get("owned", [])
    if (
        repo["expected_remote"] != repo["observed_remote"]
        or repo["desired_aliases"] != repo["observed_aliases"]
        or repo["drift_codes"]
        or repo["blockers"]
        or repo["git_visibility"].get("missing")
        or not snapshot_evidence_valid
        or repo["ownership"]["accepted"] != owned_aliases
        or (bool(owned_aliases) and repo["ownership"]["matches_committed"] is not True)
        or repo["unknown_directories"]
        or repo["unexpected_links"]
        or repo["unexpected_vendor_records"]
        or repo["registry_errors"]
        or not isinstance(repo_links, dict)
        or set(repo["desired_aliases"].get("linked", [])) != set(repo_links)
        or any(
            link["observed_target"] is None
            or link["metadata_valid"] is not True
            or link["errors"]
            for link in repo_links.values()
        )
    ):
        raise FleetConfigError("converged host audit response has repo drift")


def _response_table(value: object, label: str) -> dict[str, Any]:
    if type(value) is not dict:
        raise FleetConfigError(f"host audit response {label} must be an object")
    return value


def _response_exact_table(
    value: object,
    label: str,
    fields: set[str],
) -> dict[str, Any]:
    table = _response_table(value, label)
    reject_unknown_keys(table, fields, f"host audit response {label}")
    missing = sorted(fields - set(table))
    if missing:
        raise FleetConfigError(
            f"host audit response {label} missing field: {missing[0]}"
        )
    return table


def _response_string_list(value: object, label: str) -> list[str]:
    if type(value) is not list or any(type(item) is not str for item in value):
        raise FleetConfigError(f"host audit response {label} must be a string array")
    return value


def _response_string(
    value: object,
    label: str,
    *,
    nonempty: bool = False,
) -> str:
    if type(value) is not str or (nonempty and not value):
        raise FleetConfigError(f"host audit response {label} must be a string")
    return value


def _response_optional_string(value: object, label: str) -> str | None:
    if value is None:
        return None
    return _response_string(value, label)


def _response_bool(value: object, label: str) -> bool:
    if type(value) is not bool:
        raise FleetConfigError(f"host audit response {label} must be a boolean")
    return value


def _response_optional_bool(value: object, label: str) -> bool | None:
    if value is None:
        return None
    return _response_bool(value, label)


def _response_int(value: object, label: str) -> int:
    if type(value) is not int:
        raise FleetConfigError(f"host audit response {label} must be an integer")
    return value


def _response_digest(value: object, label: str) -> str:
    digest = _response_string(value, label)
    if not SHA256_DIGEST_PATTERN.fullmatch(digest):
        raise FleetConfigError(f"host audit response {label} must be a SHA-256 digest")
    return digest


def _response_optional_digest(value: object, label: str) -> str | None:
    if value is None:
        return None
    return _response_digest(value, label)


def _response_git_oid(value: object, label: str) -> str:
    oid = _response_string(value, label)
    if not GIT_OBJECT_ID_PATTERN.fullmatch(oid):
        raise FleetConfigError(
            f"host audit response {label} must be a Git object ID"
        )
    return oid


def _response_optional_git_oid(value: object, label: str) -> str | None:
    if value is None:
        return None
    return _response_git_oid(value, label)


def _response_error_map(value: object, label: str) -> dict[str, Any]:
    errors = _response_table(value, label)
    for alias, messages in errors.items():
        if type(alias) is not str:
            raise FleetConfigError(f"host audit response {label} keys must be strings")
        validate_skill_name(alias, f"{label} alias")
        _response_string_list(messages, f"{label}.{alias}")
    return errors


def _response_link_map(value: object, label: str) -> dict[str, Any]:
    links = _response_table(value, label)
    for alias, raw_link in links.items():
        if type(alias) is not str:
            raise FleetConfigError(f"host audit response {label} keys must be strings")
        validate_skill_name(alias, f"{label} alias")
        link = _response_exact_table(
            raw_link,
            f"{label}.{alias}",
            {
                "desired_target",
                "observed_target",
                "metadata_valid",
                "errors",
            },
        )
        _response_optional_string(
            link["desired_target"],
            f"{label}.{alias}.desired_target",
        )
        _response_optional_string(
            link["observed_target"],
            f"{label}.{alias}.observed_target",
        )
        _response_bool(
            link["metadata_valid"],
            f"{label}.{alias}.metadata_valid",
        )
        _response_string_list(
            link["errors"],
            f"{label}.{alias}.errors",
        )
    return links


def _response_alias_set(
    value: object,
    label: str,
    *,
    allow_owned_none: bool = False,
) -> dict[str, Any]:
    aliases = _response_exact_table(
        value,
        label,
        {"linked", "vendored", "owned"},
    )
    _response_string_list(aliases["linked"], f"{label}.linked")
    _response_string_list(aliases["vendored"], f"{label}.vendored")
    if aliases["owned"] is None and allow_owned_none:
        return aliases
    _response_string_list(aliases["owned"], f"{label}.owned")
    return aliases


__all__ = ["validate_host_audit_response"]
