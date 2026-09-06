from __future__ import annotations

import getpass
import json
import os
import socket
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest
from skills_profile_toml import render_profile

import skills_skill_manager_orchestration.fleet_audit as fleet_audit_module
from skills_skill_manager_orchestration.fleet_audit import audit_host
from skills_skill_manager_orchestration.enrollment import (
    HostIdentity,
    accept_current_fleet_revision,
    current_host_user,
    enroll_host,
    identity_path,
    read_host_identity,
)
from skills_skill_manager_orchestration.fleet_domain import (
    FleetConfigError,
    FleetManifest,
)
from skills_skill_manager_orchestration.fleet_protocol import HostAuditRequest
from skills_skill_manager_orchestration.fleet_render import render_manifest_host
from skills_skill_manager_orchestration.host_runtime import handle_host_request
from skills_skill_manager_orchestration.host_transport import (
    fleet_audit as run_fleet_audit,
)


ENROLLMENT_ID = "2a5e650f-c9d3-44de-a12a-c2dc80332851"
DEFAULT_IDENTITY = "11111111-1111-4111-8111-111111111111"


def _host(*, enrollment_id: str = ENROLLMENT_ID) -> dict[str, object]:
    return {
        "enrollment_id": enrollment_id,
        "hostname": socket.gethostname(),
        "username": getpass.getuser(),
        "transport": "local",
        "profile": "/tmp/profile.toml",
        "runtime": "/tmp/skill-manager",
        "global_registry": "/tmp/global",
        "global_add": [],
        "global_remove": [],
        "sources": {},
        "repos": {},
    }


def _raw_manifest(*hosts: tuple[str, dict[str, object]]) -> dict[str, object]:
    return {
        "schema_version": 4,
        "global": {"include": []},
        "sources": {},
        "repos": {},
        "hosts": dict(hosts),
    }


def _published_checkout(tmp_path: Path) -> tuple[Path, Path, str]:
    remote = tmp_path / "remote.git"
    subprocess.run(["git", "init", "--bare", "-q", str(remote)], check=True)
    checkout = tmp_path / "checkout"
    checkout.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=checkout, check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=checkout,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"], cwd=checkout, check=True
    )
    subprocess.run(
        ["git", "remote", "add", "origin", str(remote)],
        cwd=checkout,
        check=True,
    )
    manifest = checkout / "fleet.toml"
    manifest.write_text(_manifest_toml())
    subprocess.run(["git", "add", "fleet.toml"], cwd=checkout, check=True)
    subprocess.run(["git", "commit", "-qm", "fleet"], cwd=checkout, check=True)
    revision = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=checkout,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    subprocess.run(
        ["git", "push", "-q", "-u", "origin", "main"],
        cwd=checkout,
        check=True,
    )
    return checkout, manifest, revision


def _manifest_toml() -> str:
    return f'''schema_version = 4

[global]
include = []

[hosts.local]
enrollment_id = "{ENROLLMENT_ID}"
hostname = "{socket.gethostname()}"
username = "{getpass.getuser()}"
transport = "local"
profile = "/tmp/profile.toml"
runtime = "/tmp/skill-manager"
global_registry = "/tmp/global"
global_add = []
global_remove = []
'''


def test_manifest_rejects_duplicate_enrollment_id_and_host_user_selector() -> None:
    duplicate_id = _host()
    duplicate_id["hostname"] = "different"
    with pytest.raises(FleetConfigError, match="duplicate enrollment_id"):
        FleetManifest.from_raw(
            _raw_manifest(("first", _host()), ("second", duplicate_id))
        )

    duplicate_selector = _host(
        enrollment_id="32bd7cb8-5508-4d30-881d-02e98d7fea15"
    )
    with pytest.raises(FleetConfigError, match="ambiguous hostname and username"):
        FleetManifest.from_raw(
            _raw_manifest(("first", _host()), ("second", duplicate_selector))
        )


@pytest.mark.parametrize("field", ["enrollment_id", "hostname", "username"])
def test_manifest_rejects_missing_host_identity_field(field: str) -> None:
    host = _host()
    del host[field]

    with pytest.raises(FleetConfigError):
        FleetManifest.from_raw(_raw_manifest(("local", host)))


def test_manifest_toml_round_trip_preserves_host_identity() -> None:
    manifest = FleetManifest.from_raw(_raw_manifest(("local", _host())))

    round_tripped = FleetManifest.from_raw(tomllib.loads(manifest.to_toml()))

    assert round_tripped.as_dict() == manifest.as_dict()


def test_current_user_guard_ignores_spoofable_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    expected = current_host_user()
    monkeypatch.setenv("LOGNAME", "different")
    monkeypatch.setenv("USER", "different")

    assert current_host_user() == expected


def test_enroll_writes_minimal_private_identity_from_published_revision(
    tmp_path: Path,
) -> None:
    checkout, manifest, revision = _published_checkout(tmp_path)
    identity_path().unlink()

    result = enroll_host(manifest, revision)

    assert result == {
        "status": "enrolled",
        "host_id": "local",
        "enrollment_id": ENROLLMENT_ID,
        "hostname": socket.gethostname(),
        "username": getpass.getuser(),
        "config_revision": revision,
    }
    path = identity_path()
    assert path.read_text() == (
        'schema_version = 1\n'
        f'enrollment_id = "{ENROLLMENT_ID}"\n'
    )
    assert path.parent.stat().st_mode & 0o777 == 0o700
    assert path.stat().st_mode & 0o777 == 0o600
    assert read_host_identity() == HostIdentity(ENROLLMENT_ID)
    assert subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=checkout,
        check=True,
        capture_output=True,
        text=True,
    ).stdout == ""

    accepted = accept_current_fleet_revision(manifest, revision)
    assert accepted.revision == revision
    assert accepted.host_id == "local"
    assert accepted.enrollment_id == ENROLLMENT_ID
    assert accepted.profile_toml == render_profile({})


def test_enroll_cli_returns_only_after_identity_readback(tmp_path: Path) -> None:
    _, manifest, revision = _published_checkout(tmp_path)
    identity_path().unlink()

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "skills_skill_manager_orchestration",
            "enroll",
            "--manifest",
            str(manifest),
            "--revision",
            revision,
        ],
        text=True,
        capture_output=True,
        check=False,
        env=os.environ.copy(),
    )

    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["status"] == "enrolled"
    assert read_host_identity() == HostIdentity(ENROLLMENT_ID)


def test_enroll_parses_the_bytes_bound_to_the_published_revision(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, manifest, revision = _published_checkout(tmp_path)
    identity_path().unlink()

    def reject_secondary_path_read(_path: Path) -> FleetManifest:
        raise AssertionError("enrollment re-read manifest through FleetManifest.load")

    monkeypatch.setattr(FleetManifest, "load", reject_secondary_path_read)

    result = enroll_host(manifest, revision)

    assert result["enrollment_id"] == ENROLLMENT_ID


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ("short", "full lowercase commit"),
        ("dirty", "worktree must be clean"),
        ("head", "must equal HEAD"),
        ("unpublished", "published on origin/main"),
    ],
)
def test_enroll_rejects_unpublished_or_unreproducible_revision(
    tmp_path: Path,
    mutation: str,
    message: str,
) -> None:
    checkout, manifest, revision = _published_checkout(tmp_path)
    requested = revision
    if mutation == "short":
        requested = revision[:12]
    elif mutation == "dirty":
        (checkout / "untracked.txt").write_text("dirty\n")
    else:
        (checkout / "fleet.toml").write_text(_manifest_toml() + "\n# next\n")
        subprocess.run(["git", "add", "fleet.toml"], cwd=checkout, check=True)
        subprocess.run(["git", "commit", "-qm", "next"], cwd=checkout, check=True)
        next_revision = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=checkout,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        if mutation == "head":
            requested = revision
        else:
            requested = next_revision

    with pytest.raises(FleetConfigError, match=message):
        enroll_host(manifest, requested)


def test_enroll_rejects_ignored_manifest_absent_from_revision(
    tmp_path: Path,
) -> None:
    checkout, _, revision = _published_checkout(tmp_path)
    ignored = checkout / "ignored-fleet.toml"
    ignored.write_text(_manifest_toml())
    (checkout / ".git" / "info" / "exclude").write_text("ignored-fleet.toml\n")
    assert subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=all"],
        cwd=checkout,
        check=True,
        capture_output=True,
        text=True,
    ).stdout == ""

    with pytest.raises(FleetConfigError, match="worktree must be clean"):
        enroll_host(ignored, revision)


def test_enroll_never_overwrites_a_different_identity(tmp_path: Path) -> None:
    _, manifest, revision = _published_checkout(tmp_path)
    path = identity_path()
    path.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
    path.write_text(
        'schema_version = 1\n'
        'enrollment_id = "32bd7cb8-5508-4d30-881d-02e98d7fea15"\n'
    )
    path.chmod(0o600)

    with pytest.raises(FleetConfigError, match="different enrollment_id"):
        enroll_host(manifest, revision)


def test_enroll_atomic_publish_never_replaces_a_racing_different_id(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, manifest, revision = _published_checkout(tmp_path)
    identity_path().unlink()
    different = "32bd7cb8-5508-4d30-881d-02e98d7fea15"

    def publish_different_then_fail(_source: Path, target: Path) -> None:
        Path(target).write_text(
            'schema_version = 1\n' f'enrollment_id = "{different}"\n'
        )
        Path(target).chmod(0o600)
        raise FileExistsError

    monkeypatch.setattr(os, "link", publish_different_then_fail)

    with pytest.raises(FleetConfigError, match="different enrollment_id"):
        enroll_host(manifest, revision)
    assert read_host_identity() == HostIdentity(different)


@pytest.mark.parametrize(
    ("transport", "endpoint"),
    [("local", None), ("ssh", "loopback-host")],
)
def test_host_audit_binds_identity_for_local_and_ssh_protocols(
    tmp_path: Path,
    transport: str,
    endpoint: str | None,
) -> None:
    manifest = _audit_manifest(tmp_path, transport=transport, endpoint=endpoint)

    fleet_result = run_fleet_audit(
        tmp_path / "not-read.toml",
        ["target"],
        transport_factory=lambda _host: _LoopbackTransport(),
        resolved_manifest=manifest,
    )
    result = fleet_result["hosts"][0]

    assert result["status"] == "converged"
    assert result["transport"] == transport
    assert result["endpoint"] == endpoint
    assert result["identity"] == {
        "expected": {
            "enrollment_id": DEFAULT_IDENTITY,
            "hostname": socket.gethostname(),
            "username": getpass.getuser(),
        },
        "observed": {
            "enrollment_id": DEFAULT_IDENTITY,
            "hostname": socket.gethostname(),
            "username": getpass.getuser(),
        },
        "matches": True,
        "errors": [],
    }


def test_host_audit_reports_missing_identity_before_reconciliation(
    tmp_path: Path,
) -> None:
    manifest = _audit_manifest(tmp_path, transport="local", endpoint=None)
    rendered = render_manifest_host(manifest, "target")
    request = HostAuditRequest.from_manifest(manifest, "target", rendered)
    identity_path().unlink()

    result = audit_host(request)

    assert result["status"] == "incomplete"
    assert result["identity"]["matches"] is False
    assert result["identity"]["observed"]["enrollment_id"] is None
    assert "identity_drift" in result["drift_codes"]
    assert result["evidence_gaps"] == ["host enrollment identity"]


@pytest.mark.parametrize("field", ["enrollment_id", "hostname", "username"])
def test_host_audit_rejects_unknown_id_and_host_user_mismatch(
    tmp_path: Path,
    field: str,
) -> None:
    overrides: dict[str, str] = {}
    if field == "enrollment_id":
        identity_path().write_text(
            'schema_version = 1\n'
            'enrollment_id = "32bd7cb8-5508-4d30-881d-02e98d7fea15"\n'
        )
        identity_path().chmod(0o600)
    else:
        overrides[field] = "different"
    manifest = _audit_manifest(
        tmp_path,
        transport="local",
        endpoint=None,
        host_overrides=overrides,
    )
    rendered = render_manifest_host(manifest, "target")
    request = HostAuditRequest.from_manifest(manifest, "target", rendered)

    result = audit_host(request)

    assert result["status"] == "incomplete"
    assert result["identity"]["matches"] is False
    assert result["drift_codes"] == ["identity_drift"]


def test_host_audit_detects_identity_change_during_observation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest = _audit_manifest(tmp_path, transport="local", endpoint=None)
    rendered = render_manifest_host(manifest, "target")
    request = HostAuditRequest.from_manifest(manifest, "target", rendered)
    original = fleet_audit_module._observe_host_identity
    first = original(request)
    second = {
        **first,
        "observed": {**first["observed"], "enrollment_id": None},
        "matches": False,
        "errors": ["identity changed"],
    }
    observations = iter((first, second))
    monkeypatch.setattr(
        fleet_audit_module,
        "_observe_host_identity",
        lambda _request: next(observations),
    )

    result = audit_host(request)

    assert result["status"] == "incomplete"
    assert "concurrent_change" in result["drift_codes"]
    assert result["observation"]["before_fingerprint"] != result["observation"][
        "after_fingerprint"
    ]


class _LoopbackTransport:
    def request(
        self,
        _runtime: str,
        payload: dict[str, object],
    ) -> dict[str, object]:
        return handle_host_request(payload)


def _audit_manifest(
    tmp_path: Path,
    *,
    transport: str,
    endpoint: str | None,
    host_overrides: dict[str, str] | None = None,
) -> FleetManifest:
    profile = tmp_path / "profile.toml"
    profile.write_text(render_profile({"global": {"include": []}}))
    registry = tmp_path / "global"
    registry.mkdir()
    host = _host(enrollment_id=DEFAULT_IDENTITY)
    host.update(
        transport=transport,
        endpoint=endpoint,
        profile=str(profile),
        runtime="/tmp/skill-manager",
        global_registry=str(registry),
    )
    host.update(host_overrides or {})
    if endpoint is None:
        host.pop("endpoint")
    return FleetManifest.from_raw(_raw_manifest(("target", host))).with_catalogs({})
