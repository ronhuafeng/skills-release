from __future__ import annotations

import getpass
import json
import socket
import subprocess
from pathlib import Path

import pytest

import skills_skill_manager_orchestration.reconcile as reconcile_module
import skills_skill_manager_orchestration.source_remote as source_remote_module
import skills_skill_manager_orchestration.__main__ as cli_module
from skills_skill_manager_orchestration.core import BlockedOperation
from skills_skill_manager_orchestration.enrollment import identity_path
from skills_skill_manager_orchestration.fleet_domain import (
    FleetConfigError,
    HostSourceBinding,
)
from skills_skill_manager_orchestration.reconcile import apply_fleet_revision
from skills_skill_manager_orchestration.source_remote import (
    managed_source_path,
    materialize_source_checkout,
)


def _git(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(root), *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def test_managed_source_git_uses_bounded_slow_fetch_budget(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, object] = {}

    def run(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        observed.update(kwargs)
        return subprocess.CompletedProcess(args[0], 0, "", "")

    monkeypatch.setattr(source_remote_module.subprocess, "run", run)

    source_remote_module._run_materialization_git(tmp_path, "status")

    assert observed["timeout"] == 300


def _source_remote(tmp_path: Path) -> tuple[Path, str]:
    checkout = tmp_path / "source-upstream"
    skill = checkout / "skills" / "demo"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text(
        "---\nname: demo\ndescription: Demo.\n---\n"
    )
    subprocess.run(["git", "init", "-q", "-b", "main", checkout], check=True)
    _git(checkout, "config", "user.email", "test@example.com")
    _git(checkout, "config", "user.name", "Test")
    _git(checkout, "add", ".")
    _git(checkout, "commit", "-qm", "source")
    revision = _git(checkout, "rev-parse", "HEAD")
    bare = tmp_path / "source.git"
    subprocess.run(["git", "clone", "--quiet", "--bare", checkout, bare], check=True)
    return bare, revision


def _target_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "target"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=repo, check=True)
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test")
    (repo / "README.md").write_text("target\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "target")
    _git(repo, "remote", "add", "origin", "git@example.com:owner/target.git")
    return repo


def _redirect_git_url(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    remote: Path,
) -> None:
    config = tmp_path / "gitconfig"
    subprocess.run(
        [
            "git",
            "config",
            "-f",
            str(config),
            f"url.file://{remote}.insteadOf",
            "https://example.com/owner/shared.git",
        ],
        check=True,
    )
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(config))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")


def _published_fleet(
    tmp_path: Path,
    source_revision: str,
    source_path: Path,
    repo: Path,
    *,
    vendor: bool = False,
) -> tuple[Path, str]:
    checkout = tmp_path / "fleet"
    checkout.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=checkout, check=True)
    _git(checkout, "config", "user.email", "test@example.com")
    _git(checkout, "config", "user.name", "Test")
    manifest = checkout / "fleet.toml"
    manifest.write_text(
        f'''schema_version = 5

[global]
include = ["demo"]

[sources.shared]
kind = "git"
origin = "example.com/owner/shared"
revision = "{source_revision}"

[repos.target]
remote = "example.com/owner/target"

[hosts.local]
enrollment_id = "11111111-1111-4111-8111-111111111111"
hostname = "{socket.gethostname()}"
username = "{getpass.getuser()}"
transport = "local"
profile = "{tmp_path / 'profiles.toml'}"
runtime = "/tmp/skill-manager"
global_registry = "{tmp_path / '.agents' / 'skills'}"
global_add = []
global_remove = []

[hosts.local.sources.shared]
path = "{source_path}"
fetch_url = "https://example.com/owner/shared.git"

[hosts.local.repos.target]
path = "{repo}"
include = []
vendor = {['demo'] if vendor else []}
'''
    )
    _git(checkout, "add", "fleet.toml")
    _git(checkout, "commit", "-qm", "fleet")
    revision = _git(checkout, "rev-parse", "HEAD")
    bare = tmp_path / "fleet.git"
    subprocess.run(["git", "clone", "--quiet", "--bare", checkout, bare], check=True)
    _git(checkout, "remote", "add", "origin", str(bare))
    return manifest, revision


def _apply_fixture(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    vendor: bool = False,
) -> tuple[Path, str]:
    source_remote, source_revision = _source_remote(tmp_path)
    source_path = managed_source_path("shared")
    repo = _target_repo(tmp_path)
    manifest, revision = _published_fleet(
        tmp_path,
        source_revision,
        source_path,
        repo,
        vendor=vendor,
    )
    _redirect_git_url(tmp_path, monkeypatch, source_remote)
    return manifest, revision


def test_materialization_rebuilds_only_manager_owned_checkout(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    remote, revision = _source_remote(tmp_path)
    _redirect_git_url(tmp_path, monkeypatch, remote)
    target = managed_source_path("shared")

    assert materialize_source_checkout(
        "shared",
        target,
        "example.com/owner/shared",
        revision,
        fetch_url="https://example.com/owner/shared.git",
    ) == "changed"
    assert materialize_source_checkout(
        "shared",
        target,
        "example.com/owner/shared",
        revision,
        fetch_url="https://example.com/owner/shared.git",
    ) == "unchanged"
    (target / "ignored.tmp").write_text("drift\n")
    (target / ".git" / "info" / "exclude").write_text("ignored.tmp\n")
    assert materialize_source_checkout(
        "shared",
        target,
        "example.com/owner/shared",
        revision,
        fetch_url="https://example.com/owner/shared.git",
    ) == "changed"
    assert not (target / "ignored.tmp").exists()
    assert _git(target, "config", "--get", "remote.origin.url") == (
        "https://example.com/owner/shared.git"
    )

    with pytest.raises(FleetConfigError, match="Skill Manager-owned path"):
        materialize_source_checkout(
            "shared",
            tmp_path / "development-checkout",
            "example.com/owner/shared",
            revision,
            fetch_url="https://example.com/owner/shared.git",
        )


def test_materialization_replaces_checkout_with_stale_fetch_transport(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    remote, revision = _source_remote(tmp_path)
    _redirect_git_url(tmp_path, monkeypatch, remote)
    target = managed_source_path("shared")
    declared = "https://example.com/owner/shared.git"
    materialize_source_checkout(
        "shared",
        target,
        "example.com/owner/shared",
        revision,
        fetch_url=declared,
    )
    _git(
        target,
        "remote",
        "set-url",
        "origin",
        "https://old-token@example.com/owner/shared.git",
    )

    assert materialize_source_checkout(
        "shared",
        target,
        "example.com/owner/shared",
        revision,
        fetch_url=declared,
    ) == "changed"
    assert _git(target, "config", "--get", "remote.origin.url") == declared


def test_materialization_rejects_credential_fetch_url_directly(
    tmp_path: Path,
) -> None:
    _, revision = _source_remote(tmp_path)

    with pytest.raises(FleetConfigError, match="must not contain"):
        materialize_source_checkout(
            "shared",
            managed_source_path("shared"),
            "example.com/owner/shared",
            revision,
            fetch_url="https://secret@example.com/owner/shared.git",
        )


def test_materialization_never_replaces_linked_development_worktree(
    tmp_path: Path,
) -> None:
    _, revision = _source_remote(tmp_path)
    development = tmp_path / "source-upstream"
    _git(
        development,
        "remote",
        "add",
        "origin",
        "git@example.com:owner/shared.git",
    )
    linked = managed_source_path("linked")
    linked.parent.mkdir(parents=True)
    _git(development, "worktree", "add", "--quiet", "--detach", str(linked), revision)
    (linked / "local-change.txt").write_text("preserve\n")

    with pytest.raises(FleetConfigError, match="linked development worktree"):
        materialize_source_checkout(
            "linked",
            linked,
            "example.com/owner/shared",
            revision,
            fetch_url="git@example.com:owner/shared.git",
        )

    assert (linked / "local-change.txt").read_text() == "preserve\n"


def test_materialization_rejects_cache_symlink(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    remote, revision = _source_remote(tmp_path)
    _redirect_git_url(tmp_path, monkeypatch, remote)
    outside = tmp_path / "outside-cache"
    outside.mkdir()
    (tmp_path / ".cache").symlink_to(outside)

    with pytest.raises(FleetConfigError, match="must not traverse a symlink"):
        materialize_source_checkout(
            "shared",
            managed_source_path("shared"),
            "example.com/owner/shared",
            revision,
            fetch_url="https://example.com/owner/shared.git",
        )

    assert list(outside.iterdir()) == []


def test_materialization_restores_checkout_when_swap_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    remote, revision = _source_remote(tmp_path)
    _redirect_git_url(tmp_path, monkeypatch, remote)
    target = managed_source_path("shared")
    materialize_source_checkout(
        "shared",
        target,
        "example.com/owner/shared",
        revision,
        fetch_url="https://example.com/owner/shared.git",
    )
    (target / "local-change.txt").write_text("preserve\n")
    original_replace = Path.replace

    def fail_staged_install(path: Path, destination: Path) -> Path:
        if path.name.startswith(".shared-") and destination == target:
            raise OSError("injected install failure")
        return original_replace(path, destination)

    monkeypatch.setattr(Path, "replace", fail_staged_install)

    with pytest.raises(OSError, match="injected install failure"):
        materialize_source_checkout(
            "shared",
            target,
            "example.com/owner/shared",
            revision,
            fetch_url="https://example.com/owner/shared.git",
        )

    assert (target / "local-change.txt").read_text() == "preserve\n"
    assert _git(target, "rev-parse", "HEAD") == revision


@pytest.mark.parametrize(
    "fetch_url",
    [
        "https://secret-token@example.com/owner/shared.git",
        "https://user:password@example.com/owner/shared.git",
        "ssh://git:password@example.com/owner/shared.git",
    ],
)
def test_host_source_binding_rejects_credential_bearing_fetch_url(
    tmp_path: Path,
    fetch_url: str,
) -> None:
    with pytest.raises(FleetConfigError, match="must not contain"):
        HostSourceBinding.from_raw(
            "shared",
            {"path": str(tmp_path / "source"), "fetch_url": fetch_url},
        )


def test_apply_is_profile_free_and_idempotent(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest, revision = _apply_fixture(tmp_path, monkeypatch)

    first = apply_fleet_revision(manifest, revision)
    second = apply_fleet_revision(manifest, revision)

    assert first["status"] == "success", first
    assert first["target"]["host_id"] == "local"
    assert first["config_revision"] == revision
    assert first["readback"]["after_status"] == "converged"
    assert first["actions"][0]["applied_actions"] == 1
    assert second["status"] == "success"
    assert sum(phase["applied_actions"] for phase in second["actions"]) == 0
    assert not (tmp_path / "profiles.toml").exists()
    link = tmp_path / ".agents" / "skills" / "demo"
    assert link.is_symlink()
    assert link.resolve() == managed_source_path("shared") / "skills" / "demo"
    assert [phase["name"] for phase in first["actions"]] == ["links"]
    assert not (
        tmp_path / "target" / ".agents" / "skill-manager" / "vendor-lock.json"
    ).exists()


def test_apply_reports_vendored_publication_without_failing_placement(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest, revision = _apply_fixture(tmp_path, monkeypatch, vendor=True)

    receipt = apply_fleet_revision(manifest, revision)

    assert receipt["status"] == "success"
    assert receipt["readback"]["placement"]["status"] == "converged"
    assert receipt["readback"]["after_status"] == "drifted"
    assert receipt["readback"]["pending_repository_publication"] == [
        {
            "repo_id": "target",
            "path": str(tmp_path / "target"),
            "drift_codes": ["git_visibility_drift", "vendor_provenance_drift"],
        }
    ]
    assert (tmp_path / "target" / ".agents" / "skills" / "demo").is_dir()


def test_apply_reports_partial_failure_after_readback(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest, revision = _apply_fixture(tmp_path, monkeypatch)
    monkeypatch.setattr(
        reconcile_module,
        "apply_sync_plan",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            BlockedOperation("ambiguous link effect")
        ),
    )

    receipt = apply_fleet_revision(manifest, revision)

    assert receipt["status"] == "partial"
    assert receipt["error"] == "ambiguous link effect"
    assert receipt["actions"][0]["status"] == "failed"
    assert receipt["actions"][0]["applied_actions"] is None
    assert receipt["readback"]["after_status"] == "drifted"
    # Source convergence completed before the ambiguous link phase failed.
    assert receipt["before_fingerprint"] != receipt["after_fingerprint"]


def test_apply_refuses_missing_enrollment_before_target_mutation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest, revision = _apply_fixture(tmp_path, monkeypatch)
    identity_path().unlink()

    with pytest.raises(FleetConfigError, match="host identity is not a regular file"):
        apply_fleet_revision(manifest, revision)

    assert not (tmp_path / ".agents" / "skills").exists()
    assert not managed_source_path("shared").exists()


def test_apply_reads_back_after_source_materialization_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest, revision = _apply_fixture(tmp_path, monkeypatch)

    def fail_after_effect(
        _source_id: str,
        destination: Path | str,
        _origin: str,
        _revision: str,
        **_kwargs: object,
    ) -> str:
        Path(destination).mkdir(parents=True)
        raise RuntimeError("source effect failed")

    monkeypatch.setattr(
        reconcile_module,
        "materialize_source_checkout",
        fail_after_effect,
    )

    receipt = apply_fleet_revision(manifest, revision)

    assert receipt["status"] == "partial"
    assert receipt["source_actions"][0]["status"] == "failed"
    assert receipt["readback"]["placement"]["status"] == "incomplete"
    assert receipt["before_fingerprint"] != receipt["after_fingerprint"]


def test_apply_reads_back_keyboard_interrupt(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest, revision = _apply_fixture(tmp_path, monkeypatch)
    monkeypatch.setattr(
        reconcile_module,
        "apply_sync_plan",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(KeyboardInterrupt()),
    )

    receipt = apply_fleet_revision(manifest, revision)

    assert receipt["status"] == "partial"
    assert receipt["error"] == "interrupted"
    assert receipt["actions"][0]["status"] == "failed"


def test_apply_returns_partial_receipt_when_final_fingerprint_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest, revision = _apply_fixture(tmp_path, monkeypatch)
    real_fingerprint = reconcile_module._deployment_fingerprint
    calls = 0

    def fail_final_fingerprint(*args: object) -> str:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("injected fingerprint failure")
        return real_fingerprint(*args)

    monkeypatch.setattr(
        reconcile_module,
        "_deployment_fingerprint",
        fail_final_fingerprint,
    )

    receipt = apply_fleet_revision(manifest, revision)

    assert receipt["status"] == "partial"
    assert receipt["after_fingerprint"] is None
    assert receipt["error"] == (
        "final deployment fingerprint failed: injected fingerprint failure"
    )
    assert receipt["readback"]["placement"]["status"] == "converged"
    assert receipt["readback"]["evidence_gaps"] == ["deployment fingerprint"]


@pytest.mark.parametrize(("status", "exit_code"), [("success", 0), ("partial", 3)])
def test_public_apply_cli_emits_receipt_and_status_exit_code(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    status: str,
    exit_code: int,
) -> None:
    receipt = {"version": 1, "status": status, "config_revision": "1" * 40}
    monkeypatch.setattr(cli_module, "apply_fleet_revision", lambda *_args: receipt)

    result = cli_module.main(
        [
            "apply",
            "--manifest",
            str(tmp_path / "fleet.toml"),
            "--revision",
            "1" * 40,
        ]
    )

    assert result == exit_code
    assert json.loads(capsys.readouterr().out) == receipt
