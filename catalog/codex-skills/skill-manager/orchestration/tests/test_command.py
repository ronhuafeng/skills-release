from __future__ import annotations

import getpass
import hashlib
import json
import os
import shutil
import socket
import subprocess
import sys
from pathlib import Path

from skills_profile_toml import render_profile
from skills_snapshot_plan import tree_digest

from skills_skill_manager_orchestration.fleet import (
    FleetConfigError,
    FleetManifest,
    normalize_git_remote,
)
from skills_skill_manager_orchestration.fleet_domain import SourceSkill
from skills_skill_manager_orchestration.fleet_protocol import HostAuditRequest
from skills_skill_manager_orchestration.fleet_render import render_manifest_host
from skills_skill_manager_orchestration.host_runtime import HOST_PROTOCOL_VERSION


TEST_RUNTIME = shutil.which("skill-manager")
assert TEST_RUNTIME is not None
TEST_ENROLLMENT_ID = "11111111-1111-4111-8111-111111111111"
OTHER_ENROLLMENT_ID = "22222222-2222-4222-8222-222222222222"
TEST_HOSTNAME = socket.gethostname()
TEST_USERNAME = getpass.getuser()


def run_command(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    private_commands = {
        "plan": "_link-plan",
        "apply": "_link-apply",
        "vendor-plan": "_snapshot-plan",
        "vendor-apply": "_snapshot-apply",
    }
    command_args = (
        (private_commands[args[0]], *args[1:])
        if args and args[0] in private_commands
        else args
    )
    return subprocess.run(
        [sys.executable, "-m", "skills_skill_manager_orchestration", *command_args],
        cwd=cwd,
        text=True,
        capture_output=True,
        check=False,
        env=os.environ.copy(),
    )


def global_registry_path(tmp_path: Path) -> Path:
    return tmp_path / ".agents" / "skills"


def git_tree_oid(root: Path, relative_path: str) -> str:
    return subprocess.run(
        ["git", "-C", str(root), "rev-parse", f"HEAD:{relative_path}"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def test_host_audit_request_rejects_duplicate_aliases_across_sources() -> None:
    profile_toml = render_profile(
        {
            "source_roots": {
                "first": "/tmp/first",
                "second": "/tmp/second",
            },
            "sources": {"demo": "/tmp/first/skills/demo"},
            "global": {"include": ["demo"]},
            "repos": {},
        }
    )
    alias = {
        "relative_path": "skills/demo",
        "tree_oid": "0" * 40,
    }
    request = {
        "schema_version": 4,
        "host_id": "local",
        "enrollment_id": TEST_ENROLLMENT_ID,
        "hostname": TEST_HOSTNAME,
        "username": TEST_USERNAME,
        "transport": "local",
        "endpoint": None,
        "profile": "/tmp/profile.toml",
        "runtime": "/tmp/skill-manager",
        "global_registry": "/tmp/global",
        "source_bindings": {
            "first": "/tmp/first",
            "second": "/tmp/second",
        },
        "repo_bindings": {},
        "manifest_digest": "0" * 64,
        "profile_digest": hashlib.sha256(profile_toml.encode()).hexdigest(),
        "profile_toml": profile_toml,
        "sources": {
            source_id: {
                "kind": "git",
                "origin": f"example.com/owner/{source_id}",
                "revision": "0" * 40,
                    "skills": {"demo": alias},
            }
            for source_id in ("first", "second")
        },
        "repos": {},
    }

    try:
        HostAuditRequest.from_raw(request)
    except FleetConfigError as exc:
        assert str(exc) == "source alias is declared more than once: demo"
    else:
        raise AssertionError("duplicate cross-source alias was accepted")


def test_plan_and_apply_run_outside_skills_repo_with_digest_binding(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source" / "demo"
    source.mkdir(parents=True)
    (source / "SKILL.md").write_text("---\nname: demo\ndescription: Demo.\n---\n")
    registry = global_registry_path(tmp_path)
    profile_path = tmp_path / "profiles.toml"
    request_path = tmp_path / "request.json"
    artifact_path = tmp_path / "plan.json"
    request_path.write_text(
        json.dumps(
            {
                "profile_path": str(profile_path),
                "profile": {
                    "sources": {"demo": str(source)},
                    "global": {"include": ["demo"]},
                },
                "registries": [
                    {"scope": "global", "directory": str(registry), "desired": ["demo"]}
                ],
                "sources": {"demo": str(source)},
            }
        )
    )
    outside = tmp_path / "outside"
    outside.mkdir()

    planned = run_command(
        outside,
        "plan",
        "--request",
        str(request_path),
        "--artifact",
        str(artifact_path),
    )
    assert planned.returncode == 0, planned.stderr
    summary = json.loads(planned.stdout)
    assert str(tmp_path) not in planned.stdout
    assert summary["actions"]["create"] == 1

    rejected = run_command(
        outside, "apply", "--artifact", str(artifact_path), "--digest", "wrong"
    )
    assert rejected.returncode == 3
    assert not registry.exists()

    applied = run_command(
        outside,
        "apply",
        "--artifact",
        str(artifact_path),
        "--digest",
        summary["digest"],
    )
    assert applied.returncode == 0, applied.stderr
    assert (registry / "demo").resolve() == source.resolve()
    assert "demo" in profile_path.read_text()


def test_inspect_missing_profile_is_incomplete(tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    result = run_command(
        outside, "inspect", "--profile", str(tmp_path / "missing.toml")
    )
    assert result.returncode == 4
    assert result.stdout == ""
    assert result.stderr


def test_inspect_snapshot_reports_profile_coverage_and_link_anomalies(
    tmp_path: Path,
) -> None:
    source = tmp_path / "sources" / "demo"
    source.mkdir(parents=True)
    (source / "SKILL.md").write_text(
        "---\n"
        "name: demo\n"
        "description: Demo.\n"
        "disable-model-invocation: true\n"
        "---\n"
    )
    (source / "agents").mkdir()
    (source / "agents" / "openai.yaml").write_text(
        "policy:\n  allow_implicit_invocation: false\n"
    )
    profile = tmp_path / "profiles.toml"
    profile.write_text(
        f'[sources]\ndemo = "{source}"\n\n[global]\ninclude = ["demo", "missing"]\n'
    )
    registry = global_registry_path(tmp_path)
    registry.mkdir(parents=True)
    (registry / "demo").symlink_to(source)
    (registry / "broken").symlink_to(tmp_path / "absent")
    outside = tmp_path / "outside"
    outside.mkdir()

    result = run_command(
        outside,
        "inspect",
        "--profile",
        str(profile),
        "--registry",
        "global",
        str(registry),
        "--source-root",
        str(source.parent),
    )

    assert result.returncode == 0, result.stderr
    snapshot = json.loads(result.stdout)
    assert snapshot["registries"][0]["coverage"]["missing_desired"] == ["missing"]
    assert snapshot["registries"][0]["anomalies"] == ["broken"]
    demo = next(
        entry
        for entry in snapshot["registries"][0]["entries"]
        if entry["name"] == "demo"
    )
    assert demo["openai_yaml_present"] is True
    assert demo["allow_implicit_invocation"] is False
    assert demo["metadata_errors"] == []
    assert snapshot["profile_sources"][0]["alias"] == "demo"
    assert snapshot["profile_sources"][0]["openai_yaml_present"] is True
    assert snapshot["profile_sources"][0]["allow_implicit_invocation"] is False
    assert str(tmp_path) not in json.dumps(snapshot["registries"])


def test_inspect_reports_invalid_skill_metadata(tmp_path: Path) -> None:
    source = tmp_path / "sources" / "invalid"
    source.mkdir(parents=True)
    (source / "SKILL.md").write_text(
        "---\nname: invalid\ndescription: Invalid metadata.\n---\n"
    )
    metadata = source / "agents" / "openai.yaml"
    metadata.parent.mkdir()
    metadata.write_text("policy:\n  allow_implicit_invocation: null\n")
    profile = tmp_path / "profiles.toml"
    profile.write_text(
        f'[sources]\ninvalid = "{source}"\n\n[global]\ninclude = ["invalid"]\n'
    )
    registry = global_registry_path(tmp_path)
    registry.mkdir(parents=True)
    (registry / "invalid").symlink_to(source)

    result = run_command(
        tmp_path,
        "inspect",
        "--profile",
        str(profile),
        "--registry",
        "global",
        str(registry),
    )

    assert result.returncode == 0, result.stderr
    snapshot = json.loads(result.stdout)
    entry = snapshot["registries"][0]["entries"][0]
    assert snapshot["registries"][0]["anomalies"] == ["invalid"]
    assert entry["metadata_errors"] == [
        "agents/openai.yaml policy.allow_implicit_invocation must be a boolean"
    ]
    assert snapshot["profile_sources"][0]["metadata_errors"] == [
        "agents/openai.yaml policy.allow_implicit_invocation must be a boolean"
    ]


def test_inspect_reports_invalid_vendor_lock_without_aborting(tmp_path: Path) -> None:
    source = tmp_path / "sources" / "demo"
    source.mkdir(parents=True)
    (source / "SKILL.md").write_text("---\nname: demo\ndescription: Demo.\n---\n")
    repo = tmp_path / "repo"
    registry = repo / ".agents" / "skills"
    registry.mkdir(parents=True)
    shutil.copytree(source, registry / "demo")
    state_dir = repo / ".agents" / "skill-manager"
    state_dir.mkdir()
    digest = tree_digest(source)
    (state_dir / "vendor-lock.json").write_text(
        json.dumps(
            {
                "snapshots": {
                    "demo": {
                        "source_alias": "demo",
                        "source_digest": digest,
                        "target_digest": digest,
                    }
                }
            }
        )
    )
    profile = tmp_path / "profiles.toml"
    profile.write_text(
        f'[sources]\ndemo = "{source}"\n\n'
        f'[repos."{repo}"]\ninclude = []\nvendor = ["demo"]\n'
    )

    result = run_command(
        tmp_path,
        "inspect",
        "--profile",
        str(profile),
        "--registry",
        str(repo),
        str(registry),
    )

    assert result.returncode == 0, result.stderr
    registry_state = json.loads(result.stdout)["registries"][0]
    assert registry_state["vendor_lock"] == {
        "present": True,
        "valid": False,
        "errors": ["vendor lock must contain version 1 and a snapshots object"],
    }
    assert registry_state["anomalies"] == ["demo"]
    assert registry_state["managed_snapshot_anomalies"] == ["demo"]
    assert registry_state["entries"][0]["managed_snapshot"] is False
    assert (
        registry_state["entries"][0]["managed_snapshot_status"]
        == "invalid-vendor-lock"
    )


def test_inspect_reports_invalid_vendor_lock_json_without_aborting(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    registry = repo / ".agents" / "skills"
    registry.mkdir(parents=True)
    state_dir = repo / ".agents" / "skill-manager"
    state_dir.mkdir()
    (state_dir / "vendor-lock.json").write_text("{")
    profile = tmp_path / "profiles.toml"
    profile.write_text(f'[repos."{repo}"]\ninclude = []\nvendor = []\n')

    result = run_command(
        tmp_path,
        "inspect",
        "--profile",
        str(profile),
        "--registry",
        str(repo),
        str(registry),
    )

    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["registries"][0]["vendor_lock"] == {
        "present": True,
        "valid": False,
        "errors": ["vendor lock is not valid JSON"],
    }


def test_apply_rejects_unapproved_remove_action(tmp_path: Path) -> None:
    source = tmp_path / "source" / "demo"
    source.mkdir(parents=True)
    (source / "SKILL.md").write_text("---\nname: demo\ndescription: Demo.\n---\n")
    registry = global_registry_path(tmp_path)
    registry.mkdir(parents=True)
    (registry / "demo").symlink_to(source)
    request = tmp_path / "request.json"
    artifact = tmp_path / "plan.json"
    request.write_text(
        json.dumps(
            {
                "profile_path": str(tmp_path / "profiles.toml"),
                "profile": {},
                "registries": [
                    {"scope": "global", "directory": str(registry), "desired": []}
                ],
                "sources": {},
            }
        )
    )
    outside = tmp_path / "outside"
    outside.mkdir()
    planned = run_command(
        outside, "plan", "--request", str(request), "--artifact", str(artifact)
    )
    summary = json.loads(planned.stdout)
    assert summary["destructive_approval_required"] is True

    rejected = run_command(
        outside, "apply", "--artifact", str(artifact), "--digest", summary["digest"]
    )
    assert rejected.returncode == 3
    assert (registry / "demo").is_symlink()

    applied = run_command(
        outside,
        "apply",
        "--artifact",
        str(artifact),
        "--digest",
        summary["digest"],
        "--approve-destructive",
    )
    assert applied.returncode == 0, applied.stderr
    assert not (registry / "demo").exists()
    assert not (registry / "demo").is_symlink()


def test_plan_reports_unresolved_source_as_blocked(tmp_path: Path) -> None:
    request = tmp_path / "request.json"
    artifact = tmp_path / "plan.json"
    request.write_text(
        json.dumps(
            {
                "profile_path": str(tmp_path / "profiles.toml"),
                "profile": {"global": {"include": ["missing"]}},
                "registries": [
                    {
                        "scope": "global",
                        "directory": str(global_registry_path(tmp_path)),
                        "desired": ["missing"],
                    }
                ],
                "sources": {},
            }
        )
    )
    outside = tmp_path / "outside"
    outside.mkdir()

    result = run_command(
        outside, "plan", "--request", str(request), "--artifact", str(artifact)
    )

    assert result.returncode == 3
    assert json.loads(result.stdout)["status"] == "blocked"


def test_plan_accepts_non_identity_frontmatter_fields(tmp_path: Path) -> None:
    source = tmp_path / "source" / "demo"
    source.mkdir(parents=True)
    (source / "SKILL.md").write_text(
        "---\n"
        "name: demo\n"
        "description: Demo.\n"
        "disable-model-invocation: true\n"
        "---\n"
    )
    request = tmp_path / "request.json"
    request.write_text(
        json.dumps(
            {
                "profile_path": str(tmp_path / "profiles.toml"),
                "profile": {
                    "sources": {"demo": str(source)},
                    "global": {"include": ["demo"]},
                },
                "registries": [
                    {
                        "scope": "global",
                        "directory": str(global_registry_path(tmp_path)),
                        "desired": ["demo"],
                    }
                ],
                "sources": {"demo": str(source)},
            }
        )
    )

    result = run_command(
        tmp_path,
        "plan",
        "--request",
        str(request),
        "--artifact",
        str(tmp_path / "artifact.json"),
    )

    assert result.returncode == 0, result.stderr
    summary = json.loads(result.stdout)
    assert summary["status"] == "success"
    assert summary["actions"]["create"] == 1


def test_plan_rejects_unreadable_skill_identity(tmp_path: Path) -> None:
    source = tmp_path / "source" / "demo"
    source.mkdir(parents=True)
    (source / "SKILL.md").write_text(
        "---\nname: Demo\ndescription: Demo.\nlegacy-field: true\n---\n"
    )
    request = tmp_path / "request.json"
    request.write_text(
        json.dumps(
            {
                "profile_path": str(tmp_path / "profiles.toml"),
                "profile": {
                    "sources": {"demo": str(source)},
                    "global": {"include": ["demo"]},
                },
                "registries": [
                    {
                        "scope": "global",
                        "directory": str(global_registry_path(tmp_path)),
                        "desired": ["demo"],
                    }
                ],
                "sources": {"demo": str(source)},
            }
        )
    )

    result = run_command(
        tmp_path,
        "plan",
        "--request",
        str(request),
        "--artifact",
        str(tmp_path / "artifact.json"),
    )

    assert result.returncode == 2
    assert result.stdout == ""
    assert "SKILL.md frontmatter name must use hyphen-case" in result.stderr


def test_invalid_plan_request_has_stable_diagnostic(tmp_path: Path) -> None:
    request = tmp_path / "request.json"
    request.write_text("{}")
    outside = tmp_path / "outside"
    outside.mkdir()

    result = run_command(
        outside,
        "plan",
        "--request",
        str(request),
        "--artifact",
        str(tmp_path / "plan.json"),
    )

    assert result.returncode == 2
    assert result.stdout == ""
    assert (
        result.stderr.strip() == "invalid request: missing required field profile_path"
    )


def test_plan_rejects_noncanonical_global_registry(tmp_path: Path) -> None:
    request = tmp_path / "request.json"
    request.write_text(
        json.dumps(
            {
                "profile_path": str(tmp_path / "profiles.toml"),
                "profile": {},
                "registries": [
                    {
                        "scope": "global",
                        "directory": str(tmp_path / ".codex" / "skills"),
                        "desired": [],
                    }
                ],
                "sources": {},
            }
        )
    )

    result = run_command(
        tmp_path,
        "plan",
        "--request",
        str(request),
        "--artifact",
        str(tmp_path / "plan.json"),
    )

    assert result.returncode == 2
    assert f"global registry must be {global_registry_path(tmp_path)}" in result.stderr


def test_apply_blocks_link_state_changed_after_plan(tmp_path: Path) -> None:
    source = tmp_path / "source" / "demo"
    source.mkdir(parents=True)
    (source / "SKILL.md").write_text("---\nname: demo\ndescription: Demo.\n---\n")
    registry = global_registry_path(tmp_path)
    request = tmp_path / "request.json"
    artifact = tmp_path / "plan.json"
    request.write_text(
        json.dumps(
            {
                "profile_path": str(tmp_path / "profiles.toml"),
                "profile": {
                    "sources": {"demo": str(source)},
                    "global": {"include": ["demo"]},
                },
                "registries": [
                    {"scope": "global", "directory": str(registry), "desired": ["demo"]}
                ],
                "sources": {"demo": str(source)},
            }
        )
    )
    outside = tmp_path / "outside"
    outside.mkdir()
    planned = run_command(
        outside, "plan", "--request", str(request), "--artifact", str(artifact)
    )
    digest = json.loads(planned.stdout)["digest"]
    registry.mkdir(parents=True)
    (registry / "unrelated").write_text("changed")

    applied = run_command(
        outside, "apply", "--artifact", str(artifact), "--digest", digest
    )

    assert applied.returncode == 3
    assert "link state changed after plan" in applied.stderr
    assert not (registry / "demo").exists()


def test_apply_blocks_source_metadata_changed_after_plan(tmp_path: Path) -> None:
    source = tmp_path / "source" / "demo"
    source.mkdir(parents=True)
    (source / "SKILL.md").write_text("---\nname: demo\ndescription: Demo.\n---\n")
    metadata = source / "agents" / "openai.yaml"
    metadata.parent.mkdir()
    metadata.write_text("policy:\n  allow_implicit_invocation: false\n")
    registry = global_registry_path(tmp_path)
    request = tmp_path / "request.json"
    artifact = tmp_path / "plan.json"
    request.write_text(
        json.dumps(
            {
                "profile_path": str(tmp_path / "profiles.toml"),
                "profile": {
                    "sources": {"demo": str(source)},
                    "global": {"include": ["demo"]},
                },
                "registries": [
                    {
                        "scope": "global",
                        "directory": str(registry),
                        "desired": ["demo"],
                    }
                ],
                "sources": {"demo": str(source)},
            }
        )
    )
    planned = run_command(
        tmp_path, "plan", "--request", str(request), "--artifact", str(artifact)
    )
    digest = json.loads(planned.stdout)["digest"]
    metadata.write_text("policy:\n  allow_implicit_invocation: true\n")

    applied = run_command(
        tmp_path, "apply", "--artifact", str(artifact), "--digest", digest
    )

    assert applied.returncode == 3
    assert "source demo metadata changed after plan" in applied.stderr
    assert not registry.exists()


def test_apply_blocks_profile_changed_after_plan(tmp_path: Path) -> None:
    profile = tmp_path / "profiles.toml"
    request = tmp_path / "request.json"
    artifact = tmp_path / "plan.json"
    request.write_text(
        json.dumps(
            {
                "profile_path": str(profile),
                "profile": {},
                "registries": [
                    {
                        "scope": "global",
                        "directory": str(global_registry_path(tmp_path)),
                        "desired": [],
                    }
                ],
                "sources": {},
            }
        )
    )
    outside = tmp_path / "outside"
    outside.mkdir()
    planned = run_command(
        outside, "plan", "--request", str(request), "--artifact", str(artifact)
    )
    digest = json.loads(planned.stdout)["digest"]
    profile.write_text("[global]\ninclude = []\n")

    applied = run_command(
        outside, "apply", "--artifact", str(artifact), "--digest", digest
    )

    assert applied.returncode == 3
    assert "profile changed after plan" in applied.stderr


def test_vendor_plan_and_apply_create_managed_repo_snapshot(tmp_path: Path) -> None:
    source = tmp_path / "sources" / "demo"
    source.mkdir(parents=True)
    (source / "SKILL.md").write_text("---\nname: demo\ndescription: Demo.\n---\n")
    (source / "agents").mkdir()
    (source / "agents" / "openai.yaml").write_text(
        "policy:\n  allow_implicit_invocation: false\n"
    )
    (source / "scripts").mkdir()
    (source / "scripts" / "run.sh").write_text("#!/bin/sh\necho demo\n")
    (source / "scripts" / "run.sh").chmod(0o755)
    repo = tmp_path / "repo"
    repo.mkdir()
    registry = repo / ".agents" / "skills"
    state_path = repo / ".agents" / "skill-manager" / "vendor-lock.json"
    profile_path = tmp_path / "profiles.toml"
    profile = {
        "sources": {"demo": str(source)},
        "repos": {str(repo): {"include": [], "vendor": ["demo"]}},
    }
    request = tmp_path / "vendor-request.json"
    request.write_text(
        json.dumps(
            {
                "profile_path": str(profile_path),
                "profile": profile,
                "repo": str(repo),
                "registry": str(registry),
                "state_path": str(state_path),
                "sources": {"demo": str(source)},
                "desired": ["demo"],
            }
        )
    )
    artifact = tmp_path / "vendor-plan.json"

    planned = run_command(
        tmp_path, "vendor-plan", "--request", str(request), "--artifact", str(artifact)
    )

    assert planned.returncode == 0, planned.stderr
    summary = json.loads(planned.stdout)
    assert summary["actions"] == {
        "create": 1,
        "update": 0,
        "remove": 0,
        "replace_symlink": 0,
        "conflicts": 0,
        "unchanged": 0,
    }
    applied = run_command(
        tmp_path,
        "vendor-apply",
        "--artifact",
        str(artifact),
        "--digest",
        summary["digest"],
    )
    assert applied.returncode == 0, applied.stderr
    snapshot = registry / "demo"
    assert not snapshot.is_symlink()
    assert (snapshot / "SKILL.md").read_text() == (source / "SKILL.md").read_text()
    assert (snapshot / "agents" / "openai.yaml").read_text() == (
        source / "agents" / "openai.yaml"
    ).read_text()
    assert (snapshot / "scripts" / "run.sh").stat().st_mode & 0o111
    state = json.loads(state_path.read_text())
    assert state["version"] == 1
    assert state["snapshots"]["demo"]["source_alias"] == "demo"
    assert (
        state["snapshots"]["demo"]["source_digest"]
        == state["snapshots"]["demo"]["target_digest"]
    )
    assert 'vendor = ["demo"]' in profile_path.read_text()
    inspected = run_command(
        tmp_path,
        "inspect",
        "--profile",
        str(profile_path),
        "--registry",
        str(repo),
        str(registry),
        "--source-root",
        str(source.parent),
    )
    assert inspected.returncode == 0, inspected.stderr
    snapshot = json.loads(inspected.stdout)
    assert snapshot["registries"][0]["coverage"]["desired"] == ["demo"]
    assert snapshot["registries"][0]["entries"][0]["managed_snapshot"] is True
    assert snapshot["repo_profiles"][0]["vendor"] == ["demo"]


def test_vendor_updates_clean_snapshot_when_source_changes(tmp_path: Path) -> None:
    source = tmp_path / "sources" / "demo"
    source.mkdir(parents=True)
    (source / "SKILL.md").write_text("---\nname: demo\ndescription: Before.\n---\n")
    (source / "agents").mkdir()
    source_metadata = source / "agents" / "openai.yaml"
    source_metadata.write_text("policy:\n  allow_implicit_invocation: false\n")
    repo = tmp_path / "repo"
    repo.mkdir()
    registry = repo / ".agents" / "skills"
    state_path = repo / ".agents" / "skill-manager" / "vendor-lock.json"
    profile_path = tmp_path / "profiles.toml"
    profile = {
        "sources": {"demo": str(source)},
        "repos": {str(repo): {"include": [], "vendor": ["demo"]}},
    }

    def plan_and_apply(stem: str) -> dict:
        request = tmp_path / f"{stem}-request.json"
        request.write_text(
            json.dumps(
                {
                    "profile_path": str(profile_path),
                    "profile": profile,
                    "repo": str(repo),
                    "registry": str(registry),
                    "state_path": str(state_path),
                    "sources": {"demo": str(source)},
                    "desired": ["demo"],
                }
            )
        )
        artifact = tmp_path / f"{stem}-plan.json"
        planned = run_command(
            tmp_path,
            "vendor-plan",
            "--request",
            str(request),
            "--artifact",
            str(artifact),
        )
        assert planned.returncode == 0, planned.stderr
        summary = json.loads(planned.stdout)
        applied = run_command(
            tmp_path,
            "vendor-apply",
            "--artifact",
            str(artifact),
            "--digest",
            summary["digest"],
        )
        assert applied.returncode == 0, applied.stderr
        return summary

    assert plan_and_apply("create")["actions"]["create"] == 1
    unchanged = plan_and_apply("unchanged")
    assert unchanged["actions"]["unchanged"] == 1
    assert unchanged["actions"]["update"] == 0

    source_metadata.write_text("policy:\n  allow_implicit_invocation: true\n")
    updated = plan_and_apply("update")
    assert updated["actions"]["update"] == 1
    assert (registry / "demo" / "agents" / "openai.yaml").read_text() == (
        source_metadata.read_text()
    )

    source_metadata.unlink()
    removed = plan_and_apply("remove-metadata")
    assert removed["actions"]["update"] == 1
    assert not (registry / "demo" / "agents" / "openai.yaml").exists()


def test_vendor_blocks_when_managed_snapshot_was_edited(tmp_path: Path) -> None:
    source = tmp_path / "sources" / "demo"
    source.mkdir(parents=True)
    (source / "SKILL.md").write_text("---\nname: demo\ndescription: Source.\n---\n")
    repo = tmp_path / "repo"
    repo.mkdir()
    registry = repo / ".agents" / "skills"
    state_path = repo / ".agents" / "skill-manager" / "vendor-lock.json"
    profile_path = tmp_path / "profiles.toml"
    profile = {
        "sources": {"demo": str(source)},
        "repos": {str(repo): {"include": [], "vendor": ["demo"]}},
    }
    request_body = {
        "profile_path": str(profile_path),
        "profile": profile,
        "repo": str(repo),
        "registry": str(registry),
        "state_path": str(state_path),
        "sources": {"demo": str(source)},
        "desired": ["demo"],
    }
    request = tmp_path / "request.json"
    request.write_text(json.dumps(request_body))
    artifact = tmp_path / "create.json"
    planned = run_command(
        tmp_path, "vendor-plan", "--request", str(request), "--artifact", str(artifact)
    )
    digest = json.loads(planned.stdout)["digest"]
    assert (
        run_command(
            tmp_path, "vendor-apply", "--artifact", str(artifact), "--digest", digest
        ).returncode
        == 0
    )

    (registry / "demo" / "SKILL.md").write_text(
        "---\nname: demo\ndescription: Local edit.\n---\n"
    )
    drift_artifact = tmp_path / "drift.json"
    drift = run_command(
        tmp_path,
        "vendor-plan",
        "--request",
        str(request),
        "--artifact",
        str(drift_artifact),
    )

    assert drift.returncode == 3
    summary = json.loads(drift.stdout)
    assert summary["status"] == "blocked"
    assert summary["actions"]["conflicts"] == 1
    assert "Local edit" in (registry / "demo" / "SKILL.md").read_text()
    inspected = run_command(
        tmp_path,
        "inspect",
        "--profile",
        str(profile_path),
        "--registry",
        str(repo),
        str(registry),
    )
    entry = json.loads(inspected.stdout)["registries"][0]["entries"][0]
    assert entry["managed_snapshot"] is False
    assert entry["managed_snapshot_status"] == "drifted"


def test_vendor_replaces_matching_symlink_only_with_destructive_approval(
    tmp_path: Path,
) -> None:
    source = tmp_path / "sources" / "demo"
    source.mkdir(parents=True)
    (source / "SKILL.md").write_text("---\nname: demo\ndescription: Demo.\n---\n")
    repo = tmp_path / "repo"
    registry = repo / ".agents" / "skills"
    registry.mkdir(parents=True)
    (registry / "demo").symlink_to(source)
    state_path = repo / ".agents" / "skill-manager" / "vendor-lock.json"
    profile_path = tmp_path / "profiles.toml"
    profile = {
        "sources": {"demo": str(source)},
        "repos": {str(repo): {"include": [], "vendor": ["demo"]}},
    }
    request = tmp_path / "request.json"
    request.write_text(
        json.dumps(
            {
                "profile_path": str(profile_path),
                "profile": profile,
                "repo": str(repo),
                "registry": str(registry),
                "state_path": str(state_path),
                "sources": {"demo": str(source)},
                "desired": ["demo"],
            }
        )
    )
    artifact = tmp_path / "vendor.json"

    planned = run_command(
        tmp_path, "vendor-plan", "--request", str(request), "--artifact", str(artifact)
    )
    assert planned.returncode == 0, planned.stderr
    summary = json.loads(planned.stdout)
    assert summary["actions"]["replace_symlink"] == 1
    assert summary["destructive_approval_required"] is True
    rejected = run_command(
        tmp_path,
        "vendor-apply",
        "--artifact",
        str(artifact),
        "--digest",
        summary["digest"],
    )
    assert rejected.returncode == 3
    assert (registry / "demo").is_symlink()

    applied = run_command(
        tmp_path,
        "vendor-apply",
        "--artifact",
        str(artifact),
        "--digest",
        summary["digest"],
        "--approve-destructive",
    )
    assert applied.returncode == 0, applied.stderr
    assert (registry / "demo").is_dir()
    assert not (registry / "demo").is_symlink()


def test_unvendor_removes_only_clean_managed_snapshot_with_approval(
    tmp_path: Path,
) -> None:
    source = tmp_path / "sources" / "demo"
    source.mkdir(parents=True)
    (source / "SKILL.md").write_text("---\nname: demo\ndescription: Demo.\n---\n")
    repo = tmp_path / "repo"
    repo.mkdir()
    registry = repo / ".agents" / "skills"
    state_path = repo / ".agents" / "skill-manager" / "vendor-lock.json"
    profile_path = tmp_path / "profiles.toml"
    create_profile = {
        "sources": {"demo": str(source)},
        "repos": {str(repo): {"include": [], "vendor": ["demo"]}},
    }

    def write_request(
        profile: dict, desired: list[str], name: str
    ) -> tuple[Path, Path]:
        request = tmp_path / f"{name}-request.json"
        request.write_text(
            json.dumps(
                {
                    "profile_path": str(profile_path),
                    "profile": profile,
                    "repo": str(repo),
                    "registry": str(registry),
                    "state_path": str(state_path),
                    "sources": {"demo": str(source)},
                    "desired": desired,
                }
            )
        )
        return request, tmp_path / f"{name}-artifact.json"

    create_request, create_artifact = write_request(create_profile, ["demo"], "create")
    create_plan = run_command(
        tmp_path,
        "vendor-plan",
        "--request",
        str(create_request),
        "--artifact",
        str(create_artifact),
    )
    create_digest = json.loads(create_plan.stdout)["digest"]
    assert (
        run_command(
            tmp_path,
            "vendor-apply",
            "--artifact",
            str(create_artifact),
            "--digest",
            create_digest,
        ).returncode
        == 0
    )

    remove_profile = {
        "sources": {"demo": str(source)},
        "repos": {str(repo): {"include": [], "vendor": []}},
    }
    remove_request, remove_artifact = write_request(remove_profile, [], "remove")
    remove_plan = run_command(
        tmp_path,
        "vendor-plan",
        "--request",
        str(remove_request),
        "--artifact",
        str(remove_artifact),
    )
    assert remove_plan.returncode == 0, remove_plan.stderr
    summary = json.loads(remove_plan.stdout)
    assert summary["actions"]["remove"] == 1
    assert summary["destructive_approval_required"] is True
    rejected = run_command(
        tmp_path,
        "vendor-apply",
        "--artifact",
        str(remove_artifact),
        "--digest",
        summary["digest"],
    )
    assert rejected.returncode == 3
    assert (registry / "demo").is_dir()

    applied = run_command(
        tmp_path,
        "vendor-apply",
        "--artifact",
        str(remove_artifact),
        "--digest",
        summary["digest"],
        "--approve-destructive",
    )
    assert applied.returncode == 0, applied.stderr
    assert not (registry / "demo").exists()
    assert json.loads(state_path.read_text())["snapshots"] == {}


def test_vendor_rejects_request_source_that_differs_from_profile(
    tmp_path: Path,
) -> None:
    profile_source = tmp_path / "profile-source"
    request_source = tmp_path / "request-source"
    for source in (profile_source, request_source):
        source.mkdir()
        (source / "SKILL.md").write_text("---\nname: demo\ndescription: Demo.\n---\n")
    repo = tmp_path / "repo"
    repo.mkdir()
    request = tmp_path / "request.json"
    request.write_text(
        json.dumps(
            {
                "profile_path": str(tmp_path / "profiles.toml"),
                "profile": {
                    "sources": {"demo": str(profile_source)},
                    "repos": {str(repo): {"include": [], "vendor": ["demo"]}},
                },
                "repo": str(repo),
                "registry": str(repo / ".agents" / "skills"),
                "state_path": str(
                    repo / ".agents" / "skill-manager" / "vendor-lock.json"
                ),
                "sources": {"demo": str(request_source)},
                "desired": ["demo"],
            }
        )
    )

    result = run_command(
        tmp_path,
        "vendor-plan",
        "--request",
        str(request),
        "--artifact",
        str(tmp_path / "artifact.json"),
    )

    assert result.returncode == 2
    assert "must exactly match profile sources" in result.stderr


def test_vendor_ignores_strict_qualification_of_unrelated_profile_source(
    tmp_path: Path,
) -> None:
    vendored_source = tmp_path / "vendored-source"
    vendored_source.mkdir()
    (vendored_source / "SKILL.md").write_text(
        "---\nname: vendored\ndescription: Vendored.\n---\n"
    )
    link_only_source = tmp_path / "link-only-source"
    link_only_source.mkdir()
    (link_only_source / "SKILL.md").write_text(
        "---\n"
        "name: link-only\n"
        "description: Link only.\n"
        "disable-model-invocation: true\n"
        "---\n"
    )
    repo = tmp_path / "repo"
    repo.mkdir()
    request = tmp_path / "request.json"
    sources = {
        "link-only": str(link_only_source),
        "vendored": str(vendored_source),
    }
    request.write_text(
        json.dumps(
            {
                "profile_path": str(tmp_path / "profiles.toml"),
                "profile": {
                    "sources": sources,
                    "global": {"include": ["link-only"]},
                    "repos": {
                        str(repo): {"include": [], "vendor": ["vendored"]}
                    },
                },
                "repo": str(repo),
                "registry": str(repo / ".agents" / "skills"),
                "state_path": str(
                    repo / ".agents" / "skill-manager" / "vendor-lock.json"
                ),
                "sources": sources,
                "desired": ["vendored"],
            }
        )
    )

    result = run_command(
        tmp_path,
        "vendor-plan",
        "--request",
        str(request),
        "--artifact",
        str(tmp_path / "artifact.json"),
    )

    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["actions"]["create"] == 1


def test_sync_rejects_vendor_alias_as_repo_symlink(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "SKILL.md").write_text("---\nname: demo\ndescription: Demo.\n---\n")
    repo = tmp_path / "repo"
    repo.mkdir()
    request = tmp_path / "request.json"
    request.write_text(
        json.dumps(
            {
                "profile_path": str(tmp_path / "profiles.toml"),
                "profile": {
                    "sources": {"demo": str(source)},
                    "repos": {str(repo): {"include": [], "vendor": ["demo"]}},
                },
                "sources": {"demo": str(source)},
                "registries": [
                    {
                        "scope": str(repo),
                        "directory": str(repo / ".agents" / "skills"),
                        "desired": ["demo"],
                    }
                ],
            }
        )
    )

    result = run_command(
        tmp_path,
        "plan",
        "--request",
        str(request),
        "--artifact",
        str(tmp_path / "artifact.json"),
    )

    assert result.returncode == 2
    assert "desired links must exactly match" in result.stderr


def test_vendor_apply_blocks_target_change_after_plan(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "SKILL.md").write_text("---\nname: demo\ndescription: Before.\n---\n")
    repo = tmp_path / "repo"
    repo.mkdir()
    registry = repo / ".agents" / "skills"
    state_path = repo / ".agents" / "skill-manager" / "vendor-lock.json"
    profile_path = tmp_path / "profiles.toml"
    profile = {
        "sources": {"demo": str(source)},
        "repos": {str(repo): {"include": [], "vendor": ["demo"]}},
    }
    request = tmp_path / "request.json"
    request.write_text(
        json.dumps(
            {
                "profile_path": str(profile_path),
                "profile": profile,
                "repo": str(repo),
                "registry": str(registry),
                "state_path": str(state_path),
                "sources": {"demo": str(source)},
                "desired": ["demo"],
            }
        )
    )
    create_artifact = tmp_path / "create.json"
    created = run_command(
        tmp_path,
        "vendor-plan",
        "--request",
        str(request),
        "--artifact",
        str(create_artifact),
    )
    create_digest = json.loads(created.stdout)["digest"]
    assert (
        run_command(
            tmp_path,
            "vendor-apply",
            "--artifact",
            str(create_artifact),
            "--digest",
            create_digest,
        ).returncode
        == 0
    )

    (source / "SKILL.md").write_text("---\nname: demo\ndescription: After.\n---\n")
    update_artifact = tmp_path / "update.json"
    updated = run_command(
        tmp_path,
        "vendor-plan",
        "--request",
        str(request),
        "--artifact",
        str(update_artifact),
    )
    update_digest = json.loads(updated.stdout)["digest"]
    (registry / "demo" / "unplanned.txt").write_text("local")

    applied = run_command(
        tmp_path,
        "vendor-apply",
        "--artifact",
        str(update_artifact),
        "--digest",
        update_digest,
    )

    assert applied.returncode == 3
    assert "snapshot or source state changed after plan" in applied.stderr
    assert (registry / "demo" / "unplanned.txt").read_text() == "local"


def test_one_artifact_applies_global_and_repo_registries(tmp_path: Path) -> None:
    sources: dict[str, str] = {}
    for name in ("global-skill", "repo-skill"):
        source = tmp_path / "sources" / name
        source.mkdir(parents=True)
        (source / "SKILL.md").write_text(
            f"---\nname: {name}\ndescription: Demo.\n---\n"
        )
        sources[name] = str(source)
    repo = tmp_path / "repo"
    repo.mkdir()
    global_registry = global_registry_path(tmp_path)
    repo_registry = repo / ".agents" / "skills"
    profile = {
        "sources": sources,
        "global": {"include": ["global-skill"]},
        "repos": {str(repo): {"include": ["repo-skill"]}},
    }
    request = tmp_path / "request.json"
    artifact = tmp_path / "plan.json"
    request.write_text(
        json.dumps(
            {
                "profile_path": str(tmp_path / "profiles.toml"),
                "profile": profile,
                "sources": sources,
                "registries": [
                    {
                        "scope": "global",
                        "directory": str(global_registry),
                        "desired": ["global-skill"],
                    },
                    {
                        "scope": str(repo),
                        "directory": str(repo_registry),
                        "desired": ["repo-skill"],
                    },
                ],
            }
        )
    )
    outside = tmp_path / "outside"
    outside.mkdir()

    planned = run_command(
        outside, "plan", "--request", str(request), "--artifact", str(artifact)
    )
    summary = json.loads(planned.stdout)
    assert planned.returncode == 0
    assert len(summary["registries"]) == 2
    applied = run_command(
        outside, "apply", "--artifact", str(artifact), "--digest", summary["digest"]
    )

    assert applied.returncode == 0, applied.stderr
    assert (global_registry / "global-skill").is_symlink()
    assert (repo_registry / "repo-skill").is_symlink()


def test_inspect_keeps_global_and_repo_coverage_separate(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    profile = tmp_path / "profiles.toml"
    profile.write_text(
        f'[global]\ninclude = ["global-skill"]\n\n[repos."{repo}"]\ninclude = ["repo-skill"]\n'
    )
    global_registry = global_registry_path(tmp_path)
    repo_registry = repo / ".agents" / "skills"
    for registry, name in (
        (global_registry, "global-skill"),
        (repo_registry, "repo-skill"),
    ):
        target = tmp_path / "sources" / name
        target.mkdir(parents=True)
        (target / "SKILL.md").write_text(
            f"---\nname: {name}\ndescription: Demo.\n---\n"
        )
        registry.mkdir(parents=True)
        (registry / name).symlink_to(target)
    outside = tmp_path / "outside"
    outside.mkdir()

    result = run_command(
        outside,
        "inspect",
        "--profile",
        str(profile),
        "--registry",
        "global",
        str(global_registry),
        "--registry",
        str(repo),
        str(repo_registry),
    )

    assert result.returncode == 0, result.stderr
    registries = json.loads(result.stdout)["registries"]
    assert registries[0]["coverage"]["missing_desired"] == []
    assert registries[0]["coverage"]["exposed_outside_profile"] == []
    assert registries[1]["coverage"]["missing_desired"] == []
    assert registries[1]["coverage"]["exposed_outside_profile"] == []


def test_render_profile_uses_host_specific_repo_desired_state(
    tmp_path: Path,
) -> None:
    manifest = tmp_path / "fleet.toml"
    manifest.write_text(
        f"""
schema_version = 4

[global]
include = ["global-skill"]

[sources.shared]
kind = "git"
origin = "example.com/owner/shared"
revision = "0000000000000000000000000000000000000000"


[repos.demo]
remote = "example.com/owner/demo"

[hosts.local]
enrollment_id = "{TEST_ENROLLMENT_ID}"
hostname = "{TEST_HOSTNAME}"
username = "{TEST_USERNAME}"
transport = "local"
profile = "{tmp_path}/profiles.toml"
runtime = "/opt/skill-manager/bin/skill-manager"
global_registry = "{tmp_path}/global"
global_add = []
global_remove = []

[hosts.local.repos.demo]
path = "{tmp_path}/local-repo"
include = []
vendor = ["repo-skill"]

[hosts.local.sources.shared]
path = "{tmp_path}/shared"

[hosts.remote]
enrollment_id = "{OTHER_ENROLLMENT_ID}"
hostname = "remote-host"
username = "remote-user"
transport = "ssh"
endpoint = "remote"
profile = "/remote/profiles.toml"
runtime = "/remote/bin/skill-manager"
global_registry = "/remote/global"
global_add = []
global_remove = []

[hosts.remote.repos.demo]
path = "/remote/repo"
include = ["repo-skill"]
vendor = []

[hosts.remote.sources.shared]
path = "/remote/shared"
"""
    )

    catalog = {
        "shared": {
            "global-skill": SourceSkill("skills/global-skill", "1" * 40),
            "repo-skill": SourceSkill("skills/repo-skill", "2" * 40),
        }
    }
    resolved = FleetManifest.load(manifest).with_catalogs(catalog)
    local_result = render_manifest_host(resolved, "local")
    remote_result = render_manifest_host(resolved, "remote")
    assert local_result["schema_version"] == 4
    assert local_result["profile_toml"] == (
        "[sources]\n"
        f'"global-skill" = "{tmp_path}/shared/skills/global-skill"\n'
        f'"repo-skill" = "{tmp_path}/shared/skills/repo-skill"\n'
        "\n"
        "[global]\n"
        'include = ["global-skill"]\n'
        "\n"
        f'[repos."{tmp_path}/local-repo"]\n'
        "include = []\n"
        'vendor = ["repo-skill"]\n'
    )
    assert remote_result["schema_version"] == 4
    assert remote_result["profile_toml"] == (
        "[sources]\n"
        '"global-skill" = "/remote/shared/skills/global-skill"\n'
        '"repo-skill" = "/remote/shared/skills/repo-skill"\n'
        "\n"
        "[global]\n"
        'include = ["global-skill"]\n'
        "\n"
        '[repos."/remote/repo"]\n'
        'include = ["repo-skill"]\n'
        "vendor = []\n"
    )


def test_render_profile_rejects_superseded_common_repo_desired_state(
    tmp_path: Path,
) -> None:
    manifest = tmp_path / "fleet.toml"
    manifest.write_text(
        f"""
schema_version = 4

[global]
include = []

[repos.demo]
remote = "example.com/owner/demo"
include = ["demo"]
vendor = []

[hosts.local]
enrollment_id = "{TEST_ENROLLMENT_ID}"
hostname = "{TEST_HOSTNAME}"
username = "{TEST_USERNAME}"
transport = "local"
profile = "{tmp_path}/profiles.toml"
runtime = "/opt/skill-manager/bin/skill-manager"
global_registry = "{tmp_path}/global"
global_add = []
global_remove = []
"""
    )

    result = run_command(
        tmp_path,
        "render-profile",
        "--manifest",
        str(manifest),
        "--host-id",
        "local",
    )

    assert result.returncode == 2
    assert json.loads(result.stdout)["validation_blockers"] == [
        "repo demo contains unknown field(s): include, vendor"
    ]


def test_render_profile_rejects_noncanonical_source_origin(tmp_path: Path) -> None:
    manifest = tmp_path / "fleet.toml"
    manifest.write_text(
        f"""
schema_version = 4

[global]
include = []

[sources.shared]
kind = "git"
origin = "https://example.com/owner/shared.git"
revision = "0000000000000000000000000000000000000000"

[hosts.local]
enrollment_id = "{TEST_ENROLLMENT_ID}"
hostname = "{TEST_HOSTNAME}"
username = "{TEST_USERNAME}"
transport = "local"
profile = "{tmp_path}/profiles.toml"
runtime = "/opt/skill-manager/bin/skill-manager"
global_registry = "{tmp_path}/global"
global_add = []
global_remove = []
"""
    )

    result = run_command(
        tmp_path,
        "render-profile",
        "--manifest",
        str(manifest),
        "--host-id",
        "local",
    )

    assert result.returncode == 2
    assert result.stderr == ""
    payload = json.loads(result.stdout)
    assert payload["status"] == "invalid"
    assert payload["validation_blockers"] == [
        "source shared origin must use canonical Git identity"
    ]


def test_render_profile_rejects_relative_runtime_binding(tmp_path: Path) -> None:
    manifest = tmp_path / "fleet.toml"
    manifest.write_text(
        f"""
schema_version = 4

[global]
include = []

[hosts.local]
enrollment_id = "{TEST_ENROLLMENT_ID}"
hostname = "{TEST_HOSTNAME}"
username = "{TEST_USERNAME}"
transport = "local"
profile = "{tmp_path}/profiles.toml"
runtime = "bin/skill-manager"
global_registry = "{tmp_path}/global"
global_add = []
global_remove = []
"""
    )

    result = run_command(
        tmp_path,
        "render-profile",
        "--manifest",
        str(manifest),
        "--host-id",
        "local",
    )

    assert result.returncode == 2
    assert json.loads(result.stdout)["validation_blockers"] == [
        "host local runtime must be an absolute POSIX path"
    ]


def test_render_profile_manifest_digest_ignores_set_order(tmp_path: Path) -> None:
    manifest = tmp_path / "fleet.toml"

    def write_manifest(global_names: list[str]) -> None:
        manifest.write_text(
            f"""
schema_version = 4

[global]
include = {json.dumps(global_names)}

[sources.shared]
kind = "git"
origin = "example.com/owner/shared"
revision = "0000000000000000000000000000000000000000"


[hosts.local]
enrollment_id = "{TEST_ENROLLMENT_ID}"
hostname = "{TEST_HOSTNAME}"
username = "{TEST_USERNAME}"
transport = "local"
profile = "{tmp_path}/profiles.toml"
runtime = "/opt/skill-manager/bin/skill-manager"
global_registry = "{tmp_path}/global"
global_add = []
global_remove = []

[hosts.local.sources.shared]
path = "{tmp_path}/shared"
discovery_path = "."
"""
        )

    write_manifest(["beta", "alpha"])
    catalog = {
        "shared": {
            "alpha": SourceSkill("skills/alpha", "1" * 40),
            "beta": SourceSkill("skills/beta", "2" * 40),
        }
    }
    first = render_manifest_host(
        FleetManifest.load(manifest).with_catalogs(catalog), "local"
    )
    write_manifest(["alpha", "beta"])
    second = render_manifest_host(
        FleetManifest.load(manifest).with_catalogs(catalog), "local"
    )

    assert first["manifest_digest"] == second["manifest_digest"]
    assert first["profile_toml"] == second["profile_toml"]


def test_render_profile_rejects_invalid_host_source_binding(
    tmp_path: Path,
) -> None:
    manifest = tmp_path / "fleet.toml"
    manifest.write_text(
        f"""
schema_version = 4

[global]
include = []

[sources.shared]
kind = "git"
origin = "example.com/owner/shared"
revision = "0000000000000000000000000000000000000000"

[hosts.local]
enrollment_id = "{TEST_ENROLLMENT_ID}"
hostname = "{TEST_HOSTNAME}"
username = "{TEST_USERNAME}"
transport = "local"
profile = "{tmp_path}/profiles.toml"
runtime = "/opt/skill-manager/bin/skill-manager"
global_registry = "{tmp_path}/global"
global_add = []
global_remove = []

[hosts.local.sources]
shared = "/tmp/shared"
"""
    )

    result = run_command(
        tmp_path,
        "render-profile",
        "--manifest",
        str(manifest),
        "--host-id",
        "local",
    )

    assert result.returncode == 2
    assert json.loads(result.stdout)["validation_blockers"] == [
        "host source shared must be a TOML table"
    ]

    manifest.write_text(
        manifest.read_text().replace(
            '[hosts.local.sources]\nshared = "/tmp/shared"',
            '[hosts.local.sources.shared]\n'
            'path = "/tmp/shared"\n'
            'discovery_path = "../skills"',
        )
    )
    traversal = run_command(
        tmp_path,
        "render-profile",
        "--manifest",
        str(manifest),
        "--host-id",
        "local",
    )

    assert traversal.returncode == 2
    assert json.loads(traversal.stdout)["validation_blockers"] == [
        "host source shared discovery_path must be a non-traversing relative "
        "POSIX path"
    ]


def test_render_profile_rejects_unknown_host_source_binding(tmp_path: Path) -> None:
    manifest = tmp_path / "fleet.toml"
    manifest.write_text(
        f"""
schema_version = 4

[global]
include = []

[hosts.local]
enrollment_id = "{TEST_ENROLLMENT_ID}"
hostname = "{TEST_HOSTNAME}"
username = "{TEST_USERNAME}"
transport = "local"
profile = "{tmp_path}/profiles.toml"
runtime = "/opt/skill-manager/bin/skill-manager"
global_registry = "{tmp_path}/global"
global_add = []
global_remove = []

[hosts.local.sources.unknown]
path = "/tmp/unknown"
"""
    )

    result = run_command(
        tmp_path,
        "render-profile",
        "--manifest",
        str(manifest),
        "--host-id",
        "local",
    )

    assert result.returncode == 2
    assert json.loads(result.stdout)["validation_blockers"] == [
        "host binds unknown source_id: unknown"
    ]


def test_render_profile_validates_unselected_hosts_and_unique_repo_paths(
    tmp_path: Path,
) -> None:
    manifest = tmp_path / "fleet.toml"
    manifest.write_text(
        f"""
schema_version = 4

[global]
include = []

[repos.alpha]
remote = "example.com/owner/alpha"

[repos.beta]
remote = "example.com/owner/beta"

[hosts.local]
enrollment_id = "{TEST_ENROLLMENT_ID}"
hostname = "{TEST_HOSTNAME}"
username = "{TEST_USERNAME}"
transport = "local"
profile = "{tmp_path}/profiles.toml"
runtime = "/opt/skill-manager/bin/skill-manager"
global_registry = "{tmp_path}/global"
global_add = []
global_remove = []

[hosts.other]
enrollment_id = "{OTHER_ENROLLMENT_ID}"
hostname = "other-host"
username = "other-user"
transport = "local"
profile = "{tmp_path}/other.toml"
runtime = "/opt/skill-manager/bin/skill-manager"
global_registry = "{tmp_path}/other-global"
global_add = []
global_remove = []
typo = true

[hosts.local.repos.alpha]
path = "{tmp_path}/repo"
include = []
vendor = []

[hosts.local.repos.beta]
path = "{tmp_path}/repo-beta"
include = []
vendor = []
"""
    )

    unselected_invalid = run_command(
        tmp_path,
        "render-profile",
        "--manifest",
        str(manifest),
        "--host-id",
        "local",
    )

    assert unselected_invalid.returncode == 2
    assert json.loads(unselected_invalid.stdout)["validation_blockers"] == [
        "host other contains unknown field(s): typo"
    ]

    manifest.write_text(
        manifest.read_text()
        .replace("typo = true\n", "")
        .replace(
            f'path = "{tmp_path}/repo-beta"',
            f'path = "{tmp_path}/repo/../repo"',
        )
    )
    duplicate_path = run_command(
        tmp_path,
        "render-profile",
        "--manifest",
        str(manifest),
        "--host-id",
        "local",
    )

    assert duplicate_path.returncode == 2
    assert (
        "host repo bindings must use unique paths"
        in json.loads(duplicate_path.stdout)["validation_blockers"][0]
    )


def test_render_profile_manifest_digest_normalizes_host_paths(tmp_path: Path) -> None:
    manifest = tmp_path / "fleet.toml"

    def write_manifest() -> None:
        manifest.write_text(
            f"""
schema_version = 4

[global]
include = []

[hosts.local]
enrollment_id = "{TEST_ENROLLMENT_ID}"
hostname = "{TEST_HOSTNAME}"
username = "{TEST_USERNAME}"
transport = "local"
profile = "{tmp_path}/state/../profiles.toml"
runtime = "/opt/skill-manager/bin/../bin/skill-manager"
global_registry = "{tmp_path}/global/../global"
global_add = []
global_remove = []

[hosts.local.sources]
"""
        )

    write_manifest()
    first = run_command(
        tmp_path,
        "render-profile",
        "--manifest",
        str(manifest),
        "--host-id",
        "local",
    )
    write_manifest()
    manifest.write_text(manifest.read_text().replace("/state/../", "/"))
    second = run_command(
        tmp_path,
        "render-profile",
        "--manifest",
        str(manifest),
        "--host-id",
        "local",
    )

    assert first.returncode == second.returncode == 0
    assert (
        json.loads(first.stdout)["manifest_digest"]
        == json.loads(second.stdout)["manifest_digest"]
    )


def test_git_remote_normalization_rejects_plain_http() -> None:
    try:
        normalize_git_remote("http://example.com/owner/repo.git")
    except ValueError as exc:
        assert str(exc) == "Git remote is not a supported network URL"
    else:
        raise AssertionError("plain HTTP remote must be rejected")


def test_fleet_audit_reports_converged_local_host_without_mutation(
    tmp_path: Path,
) -> None:
    source_root = tmp_path / "shared"
    skill = source_root / "skills" / "demo"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text("---\nname: demo\ndescription: Demo skill.\n---\n")
    subprocess.run(
        ["git", "init", "-q", str(source_root)],
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run(
        ["git", "-C", str(source_root), "config", "user.email", "test@example.com"],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(source_root), "config", "user.name", "Test"],
        check=True,
    )
    subprocess.run(
        [
            "git",
            "-C",
            str(source_root),
            "remote",
            "add",
            "origin",
            "https://example.com/owner/shared.git",
        ],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(source_root), "add", "."],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(source_root), "commit", "-qm", "fixture"],
        check=True,
    )
    revision = subprocess.run(
        ["git", "-C", str(source_root), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    expected_tree_oid = git_tree_oid(source_root, "skills/demo")

    profile = tmp_path / "profiles.toml"
    profile.write_text(
        "[source_roots]\n"
        f'"shared" = "{source_root}/skills"\n'
        "\n"
        "[sources]\n"
        f'"demo" = "{skill}"\n'
        "\n"
        "[global]\n"
        'include = ["demo"]\n'
    )
    global_registry = tmp_path / "global"
    global_registry.mkdir()
    (global_registry / "demo").symlink_to(skill)
    manifest = tmp_path / "fleet.toml"
    manifest.write_text(
        f"""
schema_version = 4

[global]
include = ["demo"]

[sources.shared]
kind = "git"
origin = "example.com/owner/shared"
revision = "{revision}"

[hosts.local]
enrollment_id = "{TEST_ENROLLMENT_ID}"
hostname = "{TEST_HOSTNAME}"
username = "{TEST_USERNAME}"
transport = "local"
profile = "{profile}"
runtime = "{TEST_RUNTIME}"
global_registry = "{global_registry}"
global_add = []
global_remove = []

[hosts.local.sources.shared]
path = "{source_root}"
discovery_path = "skills"
"""
    )
    profile.unlink()
    before_target = os.readlink(global_registry / "demo")

    result = run_command(
        tmp_path,
        "fleet-audit",
        "--manifest",
        str(manifest),
        "--host-id",
        "local",
        "--host-id",
        "local",
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["schema_version"] == 4
    assert payload["status"] == "converged"
    assert len(payload["hosts"]) == 1
    host = payload["hosts"][0]
    assert host["host_id"] == "local"
    assert host["status"] == "converged"
    assert host["drift_codes"] == []
    assert host["blockers"] == []
    assert host["profile"]["matches"] is True
    assert host["sources"]["shared"]["observed_revision"] == revision
    assert host["sources"]["shared"]["aliases"]["demo"][
        "observed_tree_oid"
    ] == expected_tree_oid
    assert host["registries"]["global"]["observed"] == ["demo"]
    assert host["registries"]["global"]["links"]["demo"] == {
        "desired_target": str(skill),
        "observed_target": str(skill),
        "metadata_valid": True,
        "errors": [],
    }
    assert not profile.exists()
    assert os.readlink(global_registry / "demo") == before_target

    manifest.write_text(
        manifest.read_text().replace(TEST_RUNTIME, str(tmp_path / "missing-runtime"))
    )
    unavailable = run_command(
        tmp_path,
        "fleet-audit",
        "--manifest",
        str(manifest),
        "--host-id",
        "local",
    )

    assert unavailable.returncode == 4
    unavailable_host = json.loads(unavailable.stdout)["hosts"][0]
    assert unavailable_host["status"] == "incomplete"
    assert unavailable_host["drift_codes"] == ["runtime_unavailable"]
    assert unavailable_host["runtime"]["available"] is False

    manifest.write_text(
        manifest.read_text().replace(str(tmp_path / "missing-runtime"), "/usr/bin/true")
    )
    incompatible = run_command(
        tmp_path,
        "fleet-audit",
        "--manifest",
        str(manifest),
        "--host-id",
        "local",
    )

    assert incompatible.returncode == 4
    incompatible_host = json.loads(incompatible.stdout)["hosts"][0]
    assert incompatible_host["drift_codes"] == ["runtime_incompatible"]
    assert incompatible_host["runtime"]["available"] is True


def test_fleet_audit_verifies_repo_links_snapshots_ownership_and_git_visibility(
    tmp_path: Path,
) -> None:
    source_root = tmp_path / "shared"
    for name in ("link-skill", "vendor-skill"):
        skill = source_root / "skills" / name
        skill.mkdir(parents=True)
        (skill / "SKILL.md").write_text(
            f"---\nname: {name}\ndescription: {name}.\n---\n"
        )
    (source_root / "skills" / "vendor-skill" / "notes.md").write_text("tracked\n")
    subprocess.run(["git", "init", "-q", str(source_root)], check=True)
    subprocess.run(
        ["git", "-C", str(source_root), "config", "user.email", "test@example.com"],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(source_root), "config", "user.name", "Test"],
        check=True,
    )
    subprocess.run(
        [
            "git",
            "-C",
            str(source_root),
            "remote",
            "add",
            "origin",
            "git@example.com:owner/shared.git",
        ],
        check=True,
    )
    subprocess.run(["git", "-C", str(source_root), "add", "."], check=True)
    subprocess.run(
        ["git", "-C", str(source_root), "commit", "-qm", "fixture"],
        check=True,
    )
    source_revision = subprocess.run(
        ["git", "-C", str(source_root), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    link_tree_oid = git_tree_oid(source_root, "skills/link-skill")
    vendor_tree_oid = git_tree_oid(source_root, "skills/vendor-skill")

    repo = tmp_path / "repo"
    registry = repo / ".agents" / "skills"
    registry.mkdir(parents=True)
    (registry / "link-skill").symlink_to(source_root / "skills" / "link-skill")
    shutil.copytree(
        source_root / "skills" / "vendor-skill",
        registry / "vendor-skill",
    )
    owned = registry / "owned-skill"
    owned.mkdir()
    (owned / "SKILL.md").write_text(
        "---\nname: owned-skill\ndescription: Owned.\n---\n"
    )
    state_dir = repo / ".agents" / "skill-manager"
    state_dir.mkdir()
    vendor_digest = tree_digest(source_root / "skills" / "vendor-skill")
    (state_dir / "vendor-lock.json").write_text(
        json.dumps(
            {
                "version": 1,
                "snapshots": {
                    "vendor-skill": {
                        "source_alias": "vendor-skill",
                        "source_digest": vendor_digest,
                        "target_digest": vendor_digest,
                    }
                },
            },
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )
    (state_dir / "ownership.toml").write_text(
        'schema_version = 1\nowned = ["owned-skill"]\n'
    )
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    subprocess.run(
        ["git", "-C", str(repo), "config", "user.email", "test@example.com"],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(repo), "config", "user.name", "Test"],
        check=True,
    )
    subprocess.run(
        [
            "git",
            "-C",
            str(repo),
            "remote",
            "add",
            "origin",
            "ssh://git@example.com/owner/demo.git",
        ],
        check=True,
    )
    subprocess.run(["git", "-C", str(repo), "add", "."], check=True)
    subprocess.run(
        ["git", "-C", str(repo), "commit", "-qm", "fixture"],
        check=True,
    )

    profile = tmp_path / "profiles.toml"
    profile.write_text(
        "[source_roots]\n"
        f'"shared" = "{source_root}"\n'
        "\n"
        "[sources]\n"
        f'"link-skill" = "{source_root}/skills/link-skill"\n'
        f'"vendor-skill" = "{source_root}/skills/vendor-skill"\n'
        "\n"
        "[global]\n"
        "include = []\n"
        "\n"
        f'[repos."{repo}"]\n'
        'include = ["link-skill"]\n'
        'vendor = ["vendor-skill"]\n'
    )
    global_registry = tmp_path / "global"
    global_registry.mkdir()
    manifest = tmp_path / "fleet.toml"
    manifest.write_text(
        f"""
schema_version = 4

[global]
include = []

[sources.shared]
kind = "git"
origin = "example.com/owner/shared"
revision = "{source_revision}"


[repos.demo]
remote = "example.com/owner/demo"

[hosts.local]
enrollment_id = "{TEST_ENROLLMENT_ID}"
hostname = "{TEST_HOSTNAME}"
username = "{TEST_USERNAME}"
transport = "local"
profile = "{profile}"
runtime = "{TEST_RUNTIME}"
global_registry = "{global_registry}"
global_add = []
global_remove = []

[hosts.local.sources.shared]
path = "{source_root}"
discovery_path = "."

[hosts.local.repos.demo]
path = "{repo}"
include = ["link-skill"]
vendor = ["vendor-skill"]

[hosts.other]
enrollment_id = "{OTHER_ENROLLMENT_ID}"
hostname = "other-host"
username = "other-user"
transport = "local"
profile = "{profile}"
runtime = "{TEST_RUNTIME}"
global_registry = "{global_registry}"
global_add = []
global_remove = []

[hosts.other.sources.shared]
path = "{source_root}"
discovery_path = "."

[hosts.other.repos.demo]
path = "{repo}"
include = ["vendor-skill"]
vendor = ["link-skill"]
"""
    )

    result = run_command(
        tmp_path,
        "fleet-audit",
        "--manifest",
        str(manifest),
        "--host-id",
        "local",
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["status"] == "converged"
    repo_result = payload["hosts"][0]["repos"]["demo"]
    assert repo_result["status"] == "converged"
    assert repo_result["observed_remote"] == "example.com/owner/demo"
    assert repo_result["desired_aliases"] == {
        "linked": ["link-skill"],
        "owned": ["owned-skill"],
        "vendored": ["vendor-skill"],
    }
    assert repo_result["observed_aliases"] == {
        "linked": ["link-skill"],
        "owned": ["owned-skill"],
        "vendored": ["vendor-skill"],
    }
    assert repo_result["managed_snapshots"]["vendor-skill"] == {
        "record_source_digest": vendor_digest,
        "record_target_digest": vendor_digest,
        "source_digest": vendor_digest,
        "target_digest": vendor_digest,
    }
    assert repo_result["links"]["link-skill"] == {
        "desired_target": str(source_root / "skills" / "link-skill"),
        "observed_target": str(source_root / "skills" / "link-skill"),
        "metadata_valid": True,
        "errors": [],
    }
    assert repo_result["git_visibility"]["missing"] == []

    two_hosts = run_command(
        tmp_path,
        "fleet-audit",
        "--manifest",
        str(manifest),
        "--host-id",
        "local",
        "--host-id",
        "other",
    )
    assert two_hosts.returncode == 4
    host_results = {
        host["host_id"]: host for host in json.loads(two_hosts.stdout)["hosts"]
    }
    assert host_results["local"]["repos"]["demo"]["desired_aliases"] == {
        "linked": ["link-skill"],
        "owned": ["owned-skill"],
        "vendored": ["vendor-skill"],
    }
    assert host_results["other"]["repos"]["demo"]["desired_aliases"] == {
        "linked": ["vendor-skill"],
        "owned": ["owned-skill"],
        "vendored": ["link-skill"],
    }
    assert host_results["other"]["identity"]["matches"] is False
    assert "identity_drift" in host_results["other"]["drift_codes"]

    original_vendor_lock = (state_dir / "vendor-lock.json").read_text()
    (state_dir / "vendor-lock.json").write_text(original_vendor_lock + "\n")
    dirty_vendor_lock = run_command(
        tmp_path,
        "fleet-audit",
        "--manifest",
        str(manifest),
        "--host-id",
        "local",
    )
    assert dirty_vendor_lock.returncode == 3
    assert json.loads(dirty_vendor_lock.stdout)["hosts"][0]["repos"]["demo"][
        "git_visibility"
    ]["missing"] == [".agents/skill-manager/vendor-lock.json"]
    (state_dir / "vendor-lock.json").write_text(original_vendor_lock)

    original_ownership = (state_dir / "ownership.toml").read_text()
    (state_dir / "ownership.toml").write_text(original_ownership + "# local edit\n")
    dirty_ownership = run_command(
        tmp_path,
        "fleet-audit",
        "--manifest",
        str(manifest),
        "--host-id",
        "local",
    )
    assert dirty_ownership.returncode == 3
    assert json.loads(dirty_ownership.stdout)["hosts"][0]["repos"]["demo"][
        "git_visibility"
    ]["missing"] == [".agents/skill-manager/ownership.toml"]
    (state_dir / "ownership.toml").write_text(original_ownership)

    (state_dir / "ownership.toml").write_text(
        'schema_version = 1\nowned = ["owned-skill", "vendor-skill"]\n'
    )
    subprocess.run(
        ["git", "-C", str(repo), "add", ".agents/skill-manager/ownership.toml"],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(repo), "commit", "-qm", "overlap ownership"],
        check=True,
    )
    overlapping_ownership = run_command(
        tmp_path,
        "fleet-audit",
        "--manifest",
        str(manifest),
        "--host-id",
        "local",
    )
    assert overlapping_ownership.returncode == 4
    overlap_repo = json.loads(overlapping_ownership.stdout)["hosts"][0]["repos"]["demo"]
    assert (
        "overlaps linked or vendored aliases: vendor-skill"
        in overlap_repo["blockers"][0]
    )
    (state_dir / "ownership.toml").write_text(original_ownership)
    subprocess.run(
        ["git", "-C", str(repo), "add", ".agents/skill-manager/ownership.toml"],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(repo), "commit", "-qm", "restore ownership"],
        check=True,
    )

    subprocess.run(
        [
            "git",
            "-C",
            str(repo),
            "remote",
            "set-url",
            "origin",
            "ssh://git@example.com/owner/not-demo.git",
        ],
        check=True,
    )
    wrong_identity = run_command(
        tmp_path,
        "fleet-audit",
        "--manifest",
        str(manifest),
        "--host-id",
        "local",
    )
    assert wrong_identity.returncode == 4
    blocked_repo = json.loads(wrong_identity.stdout)["hosts"][0]["repos"]["demo"]
    assert blocked_repo["inspection_blocked"] is True
    assert blocked_repo["observed_aliases"] is None
    assert blocked_repo["managed_snapshots"] is None
    assert blocked_repo["drift_codes"] == ["repo_identity_mismatch"]
    subprocess.run(
        [
            "git",
            "-C",
            str(repo),
            "remote",
            "set-url",
            "origin",
            "ssh://git@example.com/owner/demo.git",
        ],
        check=True,
    )

    subprocess.run(
        [
            "git",
            "-C",
            str(repo),
            "rm",
            "--cached",
            "-q",
            ".agents/skills/vendor-skill/notes.md",
        ],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(repo), "commit", "-qm", "remove snapshot file"],
        check=True,
    )
    partially_visible = run_command(
        tmp_path,
        "fleet-audit",
        "--manifest",
        str(manifest),
        "--host-id",
        "local",
    )
    assert partially_visible.returncode == 3
    visibility = json.loads(partially_visible.stdout)["hosts"][0]["repos"]["demo"][
        "git_visibility"
    ]
    assert visibility["missing"] == [".agents/skills/vendor-skill/notes.md"]
    subprocess.run(
        [
            "git",
            "-C",
            str(repo),
            "add",
            ".agents/skills/vendor-skill/notes.md",
        ],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(repo), "commit", "-qm", "restore snapshot file"],
        check=True,
    )

    vendor_state = json.loads((state_dir / "vendor-lock.json").read_text())
    vendor_state["snapshots"]["orphan"] = {
        "source_alias": "orphan",
        "source_digest": "0" * 64,
        "target_digest": "0" * 64,
    }
    (state_dir / "vendor-lock.json").write_text(json.dumps(vendor_state))
    subprocess.run(
        ["git", "-C", str(repo), "add", ".agents/skill-manager/vendor-lock.json"],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(repo), "commit", "-qm", "orphan vendor record"],
        check=True,
    )
    drifted = run_command(
        tmp_path,
        "fleet-audit",
        "--manifest",
        str(manifest),
        "--host-id",
        "local",
    )

    assert drifted.returncode == 3
    drifted_repo = json.loads(drifted.stdout)["hosts"][0]["repos"]["demo"]
    assert "vendor_provenance_drift" in drifted_repo["drift_codes"]
    assert drifted_repo["unexpected_vendor_records"] == ["orphan"]


def test_host_audit_protocol_entrypoint_is_not_user_facing(tmp_path: Path) -> None:
    result = run_command(tmp_path, "--help")

    assert result.returncode == 0
    assert "render-profile" in result.stdout
    assert "fleet-audit" in result.stdout
    assert "enroll" in result.stdout
    assert "_host" not in result.stdout


def test_fleet_audit_rejects_empty_host_selection(tmp_path: Path) -> None:
    manifest = tmp_path / "fleet.toml"
    manifest.write_text("schema_version = 4\n")

    result = run_command(
        tmp_path,
        "fleet-audit",
        "--manifest",
        str(manifest),
    )

    assert result.returncode == 2
    assert json.loads(result.stdout)["validation_blockers"] == [
        "fleet audit requires at least one host"
    ]


def test_host_protocol_rejects_incomplete_versioned_request(
    tmp_path: Path,
) -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "skills_skill_manager_orchestration",
            "_host",
        ],
        cwd=tmp_path,
        input=(
            f'{{"schema_version":{HOST_PROTOCOL_VERSION},"operation":"audit",'
            '"request":{"schema_version":4}}'
        ),
        text=True,
        capture_output=True,
        check=False,
        env=os.environ.copy(),
    )

    assert result.returncode == 2
    assert result.stdout == ""
    assert result.stderr.strip() == "host audit request missing field: host_id"
