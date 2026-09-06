from __future__ import annotations

import subprocess
import threading
import uuid
from pathlib import Path

import pytest

import skills_skill_manager_orchestration.fleet_audit as fleet_audit_module
import skills_skill_manager_orchestration.fleet_observe as fleet_observe_module
import skills_skill_manager_orchestration.host_transport as host_transport_module
from skills_profile_toml import render_profile
from skills_skill_manager_orchestration.fleet_audit import audit_host
from skills_skill_manager_orchestration.fleet_domain import FleetManifest
from skills_skill_manager_orchestration.fleet_observe import observe_worktree
from skills_skill_manager_orchestration.fleet_protocol import HostAuditRequest
from skills_skill_manager_orchestration.fleet_render import render_manifest_host


def _initialize_repo(root: Path) -> None:
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    subprocess.run(
        ["git", "-C", str(root), "config", "user.email", "test@example.com"],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(root), "config", "user.name", "Test"],
        check=True,
    )
    subprocess.run(
        [
            "git",
            "-C",
            str(root),
            "remote",
            "add",
            "origin",
            "https://example.com/owner/repo.git",
        ],
        check=True,
    )
    subprocess.run(["git", "-C", str(root), "add", "."], check=True)
    subprocess.run(
        ["git", "-C", str(root), "commit", "-qm", "fixture"],
        check=True,
    )


def test_worktree_observation_batches_exact_path_evidence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "repo"
    skill = root / "skills" / "demo"
    skill.mkdir(parents=True)
    skill_file = skill / "SKILL.md"
    skill_file.write_text("---\nname: demo\ndescription: Demo.\n---\n")
    _initialize_repo(root)
    commands: list[tuple[list[str], str | None]] = []
    original_run = fleet_observe_module.subprocess.run

    def recording_run(command, *args, **kwargs):
        commands.append((command, kwargs.get("input")))
        return original_run(command, *args, **kwargs)

    monkeypatch.setattr(fleet_observe_module.subprocess, "run", recording_run)

    observed = observe_worktree(
        root,
        ["skills/demo"],
        ["skills/demo", "skills/demo/SKILL.md", "skills/demo/missing.md"],
    )

    assert observed.errors == ()
    assert observed.alias_tree_oids["skills/demo"] is not None
    assert observed.visibility["skills/demo"].matches_worktree is True
    assert observed.visibility["skills/demo/SKILL.md"].matches_worktree is True
    assert observed.visibility["skills/demo/missing.md"].tracked_at_head is False
    assert observed.visibility["skills/demo/missing.md"].matches_worktree is False
    batch_calls = [call for call in commands if "cat-file" in call[0]]
    status_calls = [call for call in commands if "status" in call[0]]
    assert len(batch_calls) == 1
    assert batch_calls[0][1].splitlines() == [
        "HEAD:skills/demo",
        "HEAD:skills/demo/SKILL.md",
        "HEAD:skills/demo/missing.md",
    ]
    assert len(status_calls) == 1

    skill_file.write_text("changed\n")
    changed = observe_worktree(root, [], ["skills/demo", "skills/demo/SKILL.md"])
    assert changed.visibility["skills/demo"].matches_worktree is False
    assert changed.visibility["skills/demo/SKILL.md"].matches_worktree is False


def test_fleet_audit_retains_failed_host_and_stable_order(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    profile = tmp_path / "profiles.toml"
    profile.write_text(render_profile({"global": {"include": []}}))
    registry = tmp_path / "global"
    registry.mkdir()
    manifest = tmp_path / "fleet.toml"
    host_ids = ["zeta", "echo", "delta", "charlie", "bravo", "alpha"]
    host_tables = "\n".join(
        f"""
[hosts.{host_id}]
enrollment_id = "{uuid.uuid5(uuid.NAMESPACE_DNS, host_id)}"
hostname = "{host_id}"
username = "test-user"
transport = "local"
profile = "{profile}"
runtime = "/tmp/skill-manager"
global_registry = "{registry}"
global_add = []
global_remove = []
"""
        for host_id in host_ids
    )
    manifest.write_text(
        f"""
schema_version = 4

[global]
include = []

{host_tables}
"""
    )
    barrier = threading.Barrier(4)
    lock = threading.Lock()
    active = 0
    maximum_active = 0
    started = 0

    def audit(request, _transport):
        nonlocal active, maximum_active, started
        if request.host_id == "zeta":
            raise RuntimeError("fixture host failed")
        with lock:
            active += 1
            started += 1
            ordinal = started
            maximum_active = max(maximum_active, active)
        try:
            if ordinal <= 4:
                barrier.wait(timeout=5)
        finally:
            with lock:
                active -= 1
        return {"host_id": request.host_id, "status": "converged"}

    monkeypatch.setattr(host_transport_module, "_audit_runtime", audit)
    result = host_transport_module.fleet_audit(
        manifest,
        transport_factory=lambda _host: None,
    )

    assert [host["host_id"] for host in result["hosts"]] == sorted(host_ids)
    assert maximum_active == 4
    failed = next(host for host in result["hosts"] if host["host_id"] == "zeta")
    assert failed["status"] == "incomplete"
    assert failed["drift_codes"] == ["runtime_incompatible"]


def test_host_audit_retains_concurrent_change_gate(
    remote_fleet_protocol,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest = FleetManifest.load(remote_fleet_protocol.manifest).with_catalogs(
        remote_fleet_protocol.catalogs
    )
    rendered = render_manifest_host(manifest, "remote")
    request = HostAuditRequest.from_manifest(manifest, "remote", rendered)
    monkeypatch.setattr(
        fleet_audit_module,
        "_observation_fingerprint",
        lambda _request: "0" * 64,
    )

    result = audit_host(request)

    assert result["status"] == "incomplete"
    assert "concurrent_change" in result["drift_codes"]
    assert "host state changed during audit" in result["blockers"]
