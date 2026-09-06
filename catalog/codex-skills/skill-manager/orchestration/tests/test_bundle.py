from __future__ import annotations

import getpass
import hashlib
import json
import os
import platform
import socket
import subprocess
import sys
from pathlib import Path

import pytest

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
SPEC = PACKAGE_ROOT / "packaging" / "skill-manager.spec"


@pytest.mark.skipif(
    sys.platform != "darwin" or platform.machine() != "arm64",
    reason="the distributed runtime targets macOS arm64",
)
def test_bundle_rebuilds_identically_and_runs_schema_4_audit(tmp_path: Path) -> None:
    build_environment = os.environ.copy()
    build_environment.pop("SKILL_MANAGER_CODESIGN_IDENTITY", None)
    build_environment.update(
        PYTHONDONTWRITEBYTECODE="1",
        PYTHONHASHSEED="0",
        SKILL_MANAGER_SOURCE_REVISION="1" * 40,
        SOURCE_DATE_EPOCH="0",
    )
    artifacts = []
    for build_name in ("first", "second"):
        build_root = tmp_path / build_name
        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "PyInstaller",
                "--clean",
                "--noconfirm",
                "--workpath",
                str(build_root / "build"),
                "--distpath",
                str(build_root / "dist"),
                str(SPEC),
            ],
            cwd=PACKAGE_ROOT,
            env=build_environment,
            text=True,
            capture_output=True,
            check=False,
        )
        assert completed.returncode == 0, completed.stderr
        artifacts.append(build_root / "dist" / "skill-manager")

    first_digest = hashlib.sha256(artifacts[0].read_bytes()).hexdigest()
    second_digest = hashlib.sha256(artifacts[1].read_bytes()).hexdigest()
    assert first_digest == second_digest

    signature = subprocess.run(
        ["/usr/bin/codesign", "--verify", "--strict", str(artifacts[0])],
        text=True,
        capture_output=True,
        check=False,
    )
    assert signature.returncode == 0, signature.stderr

    identity = subprocess.run(
        [str(artifacts[0]), "--identity"],
        cwd=tmp_path,
        env={"PATH": "/usr/bin:/bin", "TMPDIR": str(tmp_path)},
        text=True,
        capture_output=True,
        check=False,
    )
    assert identity.returncode == 0, identity.stderr
    assert json.loads(identity.stdout) == {
        "artifact_name": "skill-manager-runtime",
        "artifact_version": "0.12.0",
        "fleet_protocol_version": 4,
        "host_protocol_version": 6,
        "identity_version": 1,
        "source_revision": "1" * 40,
        "target": {"architecture": "arm64", "platform": "macos"},
    }

    source_root = tmp_path / "source"
    skill = source_root / "skills" / "demo"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text(
        "---\nname: demo\ndescription: Bundle audit fixture.\n---\n"
    )
    git = ["/usr/bin/git", "-C", str(source_root)]
    subprocess.run(["/usr/bin/git", "init", "-q", str(source_root)], check=True)
    subprocess.run([*git, "config", "user.email", "test@example.com"], check=True)
    subprocess.run([*git, "config", "user.name", "Test"], check=True)
    subprocess.run(
        [*git, "remote", "add", "origin", "https://example.com/owner/source.git"],
        check=True,
    )
    subprocess.run([*git, "add", "."], check=True)
    subprocess.run(
        [*git, "-c", "commit.gpgsign=false", "commit", "-qm", "fixture"],
        check=True,
    )
    revision = subprocess.run(
        [*git, "rev-parse", "HEAD"],
        text=True,
        capture_output=True,
        check=True,
    ).stdout.strip()
    tree_oid = subprocess.run(
        [*git, "rev-parse", "HEAD:skills/demo"],
        text=True,
        capture_output=True,
        check=True,
    ).stdout.strip()
    (skill / "generated.tmp").write_text("host-local artifact\n")

    profile = tmp_path / "profiles.toml"
    profile.write_text(
        "[source_roots]\n"
        f'"shared" = "{source_root}"\n\n'
        "[sources]\n"
        f'"demo" = "{skill}"\n\n'
        "[global]\n"
        'include = ["demo"]\n'
    )
    home = tmp_path / "home"
    identity_path = home / ".config" / "skill-manager" / "identity.toml"
    identity_path.parent.mkdir(parents=True, mode=0o700)
    identity_path.write_text(
        'schema_version = 1\n'
        'enrollment_id = "11111111-1111-4111-8111-111111111111"\n'
    )
    identity_path.chmod(0o600)
    registry = home / ".agents" / "skills"
    registry.mkdir(parents=True)
    (registry / "demo").symlink_to(skill)
    manifest = tmp_path / "fleet.toml"
    manifest.write_text(
        f"""
schema_version = 4

[global]
include = ["demo"]

[sources.shared]
kind = "git"
origin = "example.com/owner/source"
revision = "{revision}"

[hosts.local]
enrollment_id = "11111111-1111-4111-8111-111111111111"
hostname = "{socket.gethostname()}"
username = "{getpass.getuser()}"
transport = "local"
profile = "{profile}"
runtime = "{artifacts[0]}"
global_registry = "{registry}"
global_add = []
global_remove = []

[hosts.local.sources.shared]
path = "{source_root}"
discovery_path = "."
"""
    )
    runtime_tmp = tmp_path / "runtime-tmp"
    runtime_tmp.mkdir()
    runtime_environment = {
        "CODEX_HOME": str(tmp_path / "codex-home"),
        "HOME": str(home),
        "PATH": "/usr/bin:/bin",
        "TMPDIR": str(runtime_tmp),
    }
    result = subprocess.run(
        [
            str(artifacts[0]),
            "fleet-audit",
            "--manifest",
            str(manifest),
            "--host-id",
            "local",
        ],
        cwd=tmp_path,
        env=runtime_environment,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["schema_version"] == 4
    assert payload["status"] == "converged"
    host = payload["hosts"][0]
    assert host["status"] == "converged"
    assert host["runtime"]["protocol_version"] == 4
    assert host["profile"]["matches"] is True
    assert host["sources"]["shared"]["observed_revision"] == revision
    assert (
        host["sources"]["shared"]["aliases"]["demo"]["observed_tree_oid"]
        == tree_oid
    )
