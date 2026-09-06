from __future__ import annotations

import importlib
import platform
from typing import Any

from .fleet_audit import audit_host
from .fleet_domain import FLEET_SCHEMA_VERSION, FleetConfigError
from .fleet_protocol import HostAuditRequest
from .source_remote import inspect_source_revision


HOST_PROTOCOL_VERSION = 6
RUNTIME_VERSION = "0.12.0"


def runtime_identity() -> dict[str, Any]:
    build_identity = importlib.import_module("_skill_manager_build_identity")
    source_revision = getattr(build_identity, "SOURCE_REVISION", None)
    if not isinstance(source_revision, str) or len(source_revision) != 40:
        raise RuntimeError("runtime source revision is invalid")
    return {
        "artifact_name": "skill-manager-runtime",
        "artifact_version": RUNTIME_VERSION,
        "fleet_protocol_version": FLEET_SCHEMA_VERSION,
        "host_protocol_version": HOST_PROTOCOL_VERSION,
        "identity_version": 1,
        "source_revision": source_revision,
        "target": {
            "architecture": platform.machine(),
            "platform": _runtime_platform(),
        },
    }


def _runtime_platform() -> str:
    system = platform.system().lower()
    return "macos" if system == "darwin" else system


def handle_host_request(raw: object) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise FleetConfigError("host request must be an object")
    if raw.get("schema_version") != HOST_PROTOCOL_VERSION:
        raise FleetConfigError("host protocol version is incompatible")
    operation = raw.get("operation")
    if operation == "audit":
        _require_exact_keys(raw, {"schema_version", "operation", "request"})
        request = HostAuditRequest.from_raw(raw["request"])
        return _response(operation, "audited", audit=audit_host(request))
    if operation == "inspect_source_catalog":
        _require_exact_keys(
            raw,
            {
                "schema_version",
                "operation",
                "source_root",
                "expected_origin",
                "revision",
            },
        )
        catalog = inspect_source_revision(
            raw["source_root"],
            raw["expected_origin"],
            raw["revision"],
        )
        return _response(
            operation,
            "inspected",
            catalog={alias: skill.as_dict() for alias, skill in catalog.items()},
        )
    raise FleetConfigError("host operation is unsupported")


def _response(operation: str, result: str, **values: Any) -> dict[str, Any]:
    return {
        "schema_version": HOST_PROTOCOL_VERSION,
        "operation": operation,
        "result": result,
        **values,
    }


def _require_exact_keys(value: dict[str, Any], expected: set[str]) -> None:
    actual = set(value)
    if actual != expected:
        missing = sorted(expected - actual)
        extra = sorted(actual - expected)
        raise FleetConfigError(
            f"host request fields are invalid; missing={missing}, extra={extra}"
        )


__all__ = ["HOST_PROTOCOL_VERSION", "handle_host_request", "runtime_identity"]
