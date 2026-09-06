from __future__ import annotations

import json
import getpass
import socket
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import pytest
from skills_snapshot_plan import tree_digest
from skills_skill_manager_orchestration.fleet_domain import SourceSkill


TEST_ENROLLMENT_ID = "11111111-1111-4111-8111-111111111111"


@pytest.fixture(autouse=True)
def isolated_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    identity = tmp_path / ".config" / "skill-manager" / "identity.toml"
    identity.parent.mkdir(parents=True, mode=0o700)
    identity.write_text(
        'schema_version = 1\n'
        f'enrollment_id = "{TEST_ENROLLMENT_ID}"\n'
    )
    identity.chmod(0o600)


@dataclass(frozen=True)
class RemoteFleetProtocolFixture:
    root: Path
    profile: Path
    runtime: Path
    manifest: Path
    catalogs: dict[str, dict[str, SourceSkill]]


@pytest.fixture
def remote_fleet_protocol(
    tmp_path: Path,
) -> RemoteFleetProtocolFixture:
    source_root = tmp_path / "shared"
    skill = source_root / "skills" / "demo"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text("---\nname: demo\ndescription: Demo skill.\n---\n")
    revision = _initialize_git_repo(
        source_root,
        "https://example.com/owner/shared.git",
    )
    demo_tree_oid = _git_tree_oid(source_root, "skills/demo")

    repo = tmp_path / "repo"
    repo_registry = repo / ".agents" / "skills"
    repo_registry.mkdir(parents=True)
    shutil.copytree(skill, repo_registry / "demo")
    repo_state = repo / ".agents" / "skill-manager"
    repo_state.mkdir()
    demo_digest = tree_digest(skill)
    (repo_state / "vendor-lock.json").write_text(
        json.dumps(
            {
                "version": 1,
                "snapshots": {
                    "demo": {
                        "source_alias": "demo",
                        "source_digest": demo_digest,
                        "target_digest": demo_digest,
                    }
                },
            }
        )
    )
    _initialize_git_repo(
        repo,
        "https://example.com/owner/demo-repo.git",
    )

    profile = tmp_path / "profiles.toml"
    profile.write_text(
        "[source_roots]\n"
        f'"shared" = "{source_root}"\n'
        "\n"
        "[sources]\n"
        f'"demo" = "{skill}"\n'
        "\n"
        "[global]\n"
        'include = ["demo"]\n'
        "\n"
        f'[repos."{repo}"]\n'
        "include = []\n"
        'vendor = ["demo"]\n'
    )
    global_registry = tmp_path / "global"
    global_registry.mkdir()
    (global_registry / "demo").symlink_to(skill)

    runtime = tmp_path / "skill-manager"
    runtime.write_text(
        "#!/bin/sh\n"
        f'exec "{sys.executable}" -m skills_skill_manager_orchestration "$@"\n'
    )
    runtime.chmod(0o755)
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

[repos.demo]
remote = "example.com/owner/demo-repo"

[hosts.remote]
enrollment_id = "{TEST_ENROLLMENT_ID}"
hostname = "{socket.gethostname()}"
username = "{getpass.getuser()}"
transport = "ssh"
endpoint = "test-host"
profile = "{profile}"
runtime = "{runtime}"
global_registry = "{global_registry}"
global_add = []
global_remove = []

[hosts.remote.sources.shared]
path = "{source_root}"
discovery_path = "."

[hosts.remote.repos.demo]
path = "{repo}"
include = []
vendor = ["demo"]
"""
    )
    return RemoteFleetProtocolFixture(
        root=tmp_path,
        profile=profile,
        runtime=runtime,
        manifest=manifest,
        catalogs={
            "shared": {
                "demo": SourceSkill("skills/demo", demo_tree_oid),
            }
        },
    )


def _initialize_git_repo(path: Path, remote: str) -> str:
    subprocess.run(["git", "init", "-q", str(path)], check=True)
    subprocess.run(
        ["git", "-C", str(path), "config", "user.email", "test@example.com"],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(path), "config", "user.name", "Test"],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(path), "remote", "add", "origin", remote],
        check=True,
    )
    subprocess.run(["git", "-C", str(path), "add", "."], check=True)
    subprocess.run(
        ["git", "-C", str(path), "commit", "-qm", "fixture"],
        check=True,
    )
    return subprocess.run(
        ["git", "-C", str(path), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _git_tree_oid(root: Path, relative_path: str) -> str:
    return subprocess.run(
        ["git", "-C", str(root), "rev-parse", f"HEAD:{relative_path}"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
