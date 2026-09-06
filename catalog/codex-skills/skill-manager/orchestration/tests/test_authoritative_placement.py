from __future__ import annotations

import hashlib
import json
import subprocess
from dataclasses import asdict
from pathlib import Path

import pytest
from skills_profile_toml import render_profile

from skills_skill_manager_orchestration.core import (
    BlockedOperation,
    _authoritative_link_plan,
    _jsonable,
    _restrict_link_plan,
    apply_sync_plan,
    apply_vendor_plan,
    plan_sync,
    plan_vendor,
)
from skills_skill_manager_orchestration.enrollment import AcceptedFleetRevision
from skills_symlink_plan import plan_directory as plan_link_directory


ACCEPTED_REVISION = "1" * 40


def _skill(path: Path, description: str = "Source") -> Path:
    path.mkdir(parents=True)
    (path / "SKILL.md").write_text(
        f"---\nname: {path.name}\ndescription: {description}.\n---\n"
    )
    return path


def _source_skill(path: Path) -> Path:
    source = _skill(path)
    root = source.parent
    subprocess.run(["git", "init", "-q", "-b", "main", str(root)], check=True)
    subprocess.run(["git", "-C", str(root), "add", "."], check=True)
    subprocess.run(
        [
            "git",
            "-C",
            str(root),
            "-c",
            "user.name=Test",
            "-c",
            "user.email=test@example.com",
            "-c",
            "commit.gpgsign=false",
            "commit",
            "-qm",
            "source",
        ],
        check=True,
    )
    return source


def _repo(path: Path) -> Path:
    path.mkdir()
    (path / "README.md").write_text("# Target\n")
    subprocess.run(["git", "init", "-q", "-b", "main", str(path)], check=True)
    subprocess.run(
        [
            "git",
            "-C",
            str(path),
            "remote",
            "add",
            "origin",
            f"https://example.com/owner/{path.name}.git",
        ],
        check=True,
    )
    subprocess.run(["git", "-C", str(path), "add", "."], check=True)
    subprocess.run(
        [
            "git",
            "-C",
            str(path),
            "-c",
            "user.name=Test",
            "-c",
            "user.email=test@example.com",
            "-c",
            "commit.gpgsign=false",
            "commit",
            "-qm",
            "target",
        ],
        check=True,
    )
    return path


def _authority(
    profile: dict[str, object],
    registry: Path,
    *,
    linked: dict[str, tuple[str, ...]] | None = None,
    vendored: dict[str, tuple[str, ...]] | None = None,
) -> AcceptedFleetRevision:
    sources = {
        str(alias): Path(path).resolve()
        for alias, path in dict(profile.get("sources", {})).items()
    }
    revisions: dict[str, str] = {}
    tree_oids: dict[str, str] = {}
    for alias, source in sources.items():
        root = source.parent
        revisions[alias] = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        tree_oids[alias] = subprocess.run(
            ["git", "-C", str(root), "rev-parse", f"HEAD:{source.name}"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    repo_paths = set((linked or {})) | set((vendored or {}))
    return AcceptedFleetRevision(
        revision=ACCEPTED_REVISION,
        host_id="test-host",
        enrollment_id="11111111-1111-4111-8111-111111111111",
        profile_toml=render_profile(profile),
        profile_path=str(registry.parents[1] / "profiles.toml"),
        global_registry=str(registry),
        linked_scopes=linked or {},
        vendored_scopes=vendored or {},
        repo_origins={
            repo: f"example.com/owner/{Path(repo).name}" for repo in repo_paths
        },
        source_revisions=revisions,
        source_tree_oids=tree_oids,
    )


def _forge_desired(artifact: Path, destination: Path) -> str:
    document = json.loads(artifact.read_text())
    payload = document["payload"]
    item = payload["registries"][0]
    item["desired"] = []
    sources = {name: Path(path) for name, path in payload["sources"].items()}
    reusable = {
        name: Path(path) for name, path in payload["reusable_targets"].items()
    }
    managed = item.get("managed_names")
    forged_plan = plan_link_directory(
        item["scope"],
        Path(item["directory"]),
        [],
        sources,
        reusable,
    )
    forged_plan = _authoritative_link_plan(
        forged_plan,
        set(),
        sources,
        reusable,
        None if managed is None else set(managed),
    )
    if managed is not None:
        forged_plan = _restrict_link_plan(forged_plan, set(managed))
    item["plan"] = _jsonable(asdict(forged_plan))
    digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    destination.write_text(
        json.dumps({"digest": digest, "payload": payload}, indent=2, sort_keys=True)
        + "\n"
    )
    return digest


def test_authoritative_global_replaces_conflicts_and_removes_extras(
    tmp_path: Path,
) -> None:
    source = _source_skill(tmp_path / "source" / "demo")
    registry = tmp_path / ".agents" / "skills"
    _skill(registry / "demo", "Conflicting user copy")
    _skill(registry / "obsolete", "Outside accepted global set")
    _skill(registry / ".hidden", "Hidden global copy")
    profile_path = tmp_path / "profiles.toml"
    artifact = tmp_path / "plan.json"
    profile = {
        "sources": {"demo": str(source)},
        "global": {"include": ["demo"]},
    }
    request = {
        "profile_path": str(profile_path),
        "profile": profile,
        "registries": [
            {"scope": "global", "directory": str(registry), "desired": ["demo"]}
        ],
        "sources": {"demo": str(source)},
    }

    authority = _authority(profile, registry)
    summary = plan_sync(
        request,
        artifact,
        authority=authority,
    )

    assert summary["status"] == "success"
    assert summary["actions"] == {
        "create": 0,
        "retarget": 0,
        "overwrite": 1,
        "remove": 2,
        "unresolved": 0,
        "conflicts": 0,
        "unchanged": 0,
        "preserved": 0,
    }
    assert summary["destructive_approval_required"] is False

    forged = tmp_path / "forged-global.json"
    forged_digest = _forge_desired(artifact, forged)
    with pytest.raises(BlockedOperation, match="Fleet authority is invalid"):
        apply_sync_plan(
            forged,
            forged_digest,
            False,
            authority=authority,
        )
    with pytest.raises(BlockedOperation, match="matching Fleet authority"):
        apply_sync_plan(artifact, summary["digest"], False)
    applied = apply_sync_plan(
        artifact,
        summary["digest"],
        False,
        authority=authority,
    )

    assert applied["status"] == "success"
    assert (registry / "demo").is_symlink()
    assert (registry / "demo").resolve() == source.resolve()
    assert not (registry / "obsolete").exists()
    assert not (registry / ".hidden").exists()


def test_authoritative_repo_replaces_only_configured_name_and_preserves_owned(
    tmp_path: Path,
) -> None:
    source = _source_skill(tmp_path / "source" / "demo")
    repo = _repo(tmp_path / "repo")
    registry = repo / ".agents" / "skills"
    _skill(registry / "demo", "Conflicting repo copy")
    owned = _skill(registry / "repo-owned", "Repository authority")
    profile_path = tmp_path / "profiles.toml"
    artifact = tmp_path / "plan.json"
    profile = {
        "sources": {"demo": str(source)},
        "repos": {str(repo): {"include": ["demo"], "vendor": []}},
    }
    request = {
        "profile_path": str(profile_path),
        "profile": profile,
        "registries": [
            {"scope": str(repo), "directory": str(registry), "desired": ["demo"]}
        ],
        "sources": {"demo": str(source)},
    }

    authority = _authority(
        profile,
        tmp_path / ".agents" / "skills",
        linked={str(repo): ("demo",)},
    )
    summary = plan_sync(
        request,
        artifact,
        authority=authority,
    )

    assert summary["status"] == "success"
    assert summary["actions"]["overwrite"] == 1
    assert summary["actions"]["preserved"] == 1
    forged = tmp_path / "forged-repo.json"
    forged_digest = _forge_desired(artifact, forged)
    with pytest.raises(BlockedOperation, match="Fleet authority is invalid"):
        apply_sync_plan(
            forged,
            forged_digest,
            False,
            authority=authority,
        )
    apply_sync_plan(artifact, summary["digest"], False, authority=authority)
    assert (registry / "demo").resolve() == source.resolve()
    assert owned.is_dir()
    assert "Repository authority" in (owned / "SKILL.md").read_text()


def test_authoritative_vendor_restores_drift_and_removes_managed_snapshot(
    tmp_path: Path,
) -> None:
    source = _source_skill(tmp_path / "source" / "demo")
    repo = _repo(tmp_path / "repo")
    registry = repo / ".agents" / "skills"
    state_path = repo / ".agents" / "skill-manager" / "vendor-lock.json"
    profile_path = tmp_path / "profiles.toml"

    def request(
        desired: list[str],
    ) -> tuple[dict[str, object], AcceptedFleetRevision]:
        profile: dict[str, object] = {
            "sources": {"demo": str(source)},
            "repos": {str(repo): {"include": [], "vendor": desired}},
        }
        value = {
            "profile_path": str(profile_path),
            "profile": profile,
            "repo": str(repo),
            "registry": str(registry),
            "state_path": str(state_path),
            "sources": {"demo": str(source)},
            "desired": desired,
        }
        authority = _authority(
            profile,
            tmp_path / ".agents" / "skills",
            vendored={str(repo): tuple(desired)},
        )
        return value, authority

    create_artifact = tmp_path / "create.json"
    create_request, create_authority = request(["demo"])
    created = plan_vendor(
        create_request,
        create_artifact,
        authority=create_authority,
    )
    with pytest.raises(BlockedOperation, match="matching Fleet authority"):
        apply_vendor_plan(create_artifact, created["digest"], False)
    apply_vendor_plan(
        create_artifact,
        created["digest"],
        False,
        authority=create_authority,
    )
    (registry / "demo" / "SKILL.md").write_text(
        "---\nname: demo\ndescription: Local drift.\n---\n"
    )

    restore_artifact = tmp_path / "restore.json"
    restore_request, restore_authority = request(["demo"])
    restored = plan_vendor(
        restore_request,
        restore_artifact,
        authority=restore_authority,
    )

    assert restored["status"] == "success"
    assert restored["actions"]["overwrite"] == 1
    assert restored["actions"]["conflicts"] == 0
    apply_vendor_plan(
        restore_artifact,
        restored["digest"],
        False,
        authority=restore_authority,
    )
    assert (registry / "demo" / "SKILL.md").read_text() == (
        source / "SKILL.md"
    ).read_text()

    remove_artifact = tmp_path / "remove.json"
    remove_request, remove_authority = request([])
    removed = plan_vendor(
        remove_request,
        remove_artifact,
        authority=remove_authority,
    )
    assert removed["actions"]["remove"] == 1
    assert removed["destructive_approval_required"] is False
    apply_vendor_plan(
        remove_artifact,
        removed["digest"],
        False,
        authority=remove_authority,
    )
    assert not (registry / "demo").exists()
    assert json.loads(state_path.read_text())["snapshots"] == {}


def test_authoritative_apply_still_blocks_target_change_after_plan(
    tmp_path: Path,
) -> None:
    source = _source_skill(tmp_path / "source" / "demo")
    registry = tmp_path / ".agents" / "skills"
    conflict = _skill(registry / "demo", "Before plan")
    artifact = tmp_path / "plan.json"
    profile = {
        "sources": {"demo": str(source)},
        "global": {"include": ["demo"]},
    }
    authority = _authority(profile, registry)
    summary = plan_sync(
        {
            "profile_path": str(tmp_path / "profiles.toml"),
            "profile": profile,
            "registries": [
                {
                    "scope": "global",
                    "directory": str(registry),
                    "desired": ["demo"],
                }
            ],
            "sources": {"demo": str(source)},
        },
        artifact,
        authority=authority,
    )
    (conflict / "SKILL.md").write_text(
        "---\nname: demo\ndescription: Changed after plan.\n---\n"
    )

    with pytest.raises(BlockedOperation, match="link state changed after plan"):
        apply_sync_plan(
            artifact,
            summary["digest"],
            False,
            authority=authority,
        )


def test_authoritative_apply_blocks_source_content_change_after_plan(
    tmp_path: Path,
) -> None:
    source = _source_skill(tmp_path / "source" / "demo")
    details = source / "details.md"
    details.write_text("Before plan\n")
    subprocess.run(["git", "-C", str(source.parent), "add", "."], check=True)
    subprocess.run(
        [
            "git",
            "-C",
            str(source.parent),
            "-c",
            "user.name=Test",
            "-c",
            "user.email=test@example.com",
            "-c",
            "commit.gpgsign=false",
            "commit",
            "-qm",
            "details",
        ],
        check=True,
    )
    registry = tmp_path / ".agents" / "skills"
    artifact = tmp_path / "plan.json"
    profile = {
        "sources": {"demo": str(source)},
        "global": {"include": ["demo"]},
    }
    authority = _authority(profile, registry)
    summary = plan_sync(
        {
            "profile_path": str(tmp_path / "profiles.toml"),
            "profile": profile,
            "registries": [
                {
                    "scope": "global",
                    "directory": str(registry),
                    "desired": ["demo"],
                }
            ],
            "sources": {"demo": str(source)},
        },
        artifact,
        authority=authority,
    )
    details.write_text("Changed after plan\n")

    with pytest.raises(BlockedOperation, match="Fleet authority is invalid"):
        apply_sync_plan(
            artifact,
            summary["digest"],
            False,
            authority=authority,
        )


def test_authoritative_repo_plan_rejects_registry_outside_repo(
    tmp_path: Path,
) -> None:
    source = _source_skill(tmp_path / "source" / "demo")
    repo = _repo(tmp_path / "repo")
    profile = {
        "sources": {"demo": str(source)},
        "repos": {str(repo): {"include": ["demo"], "vendor": []}},
    }

    with pytest.raises(ValueError, match="repo registry must be"):
        plan_sync(
            {
                "profile_path": str(tmp_path / "profiles.toml"),
                "profile": profile,
                "registries": [
                    {
                        "scope": str(repo),
                        "directory": str(tmp_path / "outside"),
                        "desired": ["demo"],
                    }
                ],
                "sources": {"demo": str(source)},
            },
            tmp_path / "plan.json",
            authority=_authority(
                profile,
                tmp_path / ".agents" / "skills",
                linked={str(repo): ("demo",)},
            ),
        )


def test_public_request_cannot_claim_an_accepted_revision(tmp_path: Path) -> None:
    registry = tmp_path / ".agents" / "skills"

    with pytest.raises(ValueError, match="available only to Fleet apply"):
        plan_sync(
            {
                "accepted_revision": ACCEPTED_REVISION,
                "profile_path": str(tmp_path / "profiles.toml"),
                "profile": {},
                "registries": [
                    {
                        "scope": "global",
                        "directory": str(registry),
                        "desired": [],
                    }
                ],
                "sources": {},
            },
            tmp_path / "plan.json",
        )


def test_authoritative_plan_rejects_symlinked_registry_root(tmp_path: Path) -> None:
    source = _source_skill(tmp_path / "source" / "demo")
    outside = tmp_path / "outside"
    outside.mkdir()
    registry = tmp_path / ".agents" / "skills"
    registry.parent.mkdir(parents=True)
    registry.symlink_to(outside, target_is_directory=True)
    profile = {
        "sources": {"demo": str(source)},
        "global": {"include": ["demo"]},
    }

    with pytest.raises(ValueError, match="must not traverse a symlink"):
        plan_sync(
            {
                "profile_path": str(tmp_path / "profiles.toml"),
                "profile": profile,
                "registries": [
                    {
                        "scope": "global",
                        "directory": str(registry),
                        "desired": ["demo"],
                    }
                ],
                "sources": {"demo": str(source)},
            },
            tmp_path / "plan.json",
            authority=_authority(profile, registry),
        )


def test_authoritative_plan_rejects_source_outside_accepted_profile(
    tmp_path: Path,
) -> None:
    accepted_source = _source_skill(tmp_path / "accepted" / "demo")
    other_source = _source_skill(tmp_path / "other" / "demo")
    registry = tmp_path / ".agents" / "skills"
    profile = {
        "sources": {"demo": str(accepted_source)},
        "global": {"include": ["demo"]},
    }

    with pytest.raises(ValueError, match="exactly match profile sources"):
        plan_sync(
            {
                "profile_path": str(tmp_path / "profiles.toml"),
                "profile": profile,
                "registries": [
                    {
                        "scope": "global",
                        "directory": str(registry),
                        "desired": ["demo"],
                    }
                ],
                "sources": {"demo": str(other_source)},
            },
            tmp_path / "plan.json",
            authority=_authority(profile, registry),
        )


def test_authoritative_repo_rejects_caller_managed_scope(tmp_path: Path) -> None:
    source = _source_skill(tmp_path / "source" / "demo")
    repo = _repo(tmp_path / "repo")
    registry = repo / ".agents" / "skills"
    profile = {
        "sources": {"demo": str(source)},
        "repos": {str(repo): {"include": ["demo"], "vendor": []}},
    }

    with pytest.raises(ValueError, match="derives managed names"):
        plan_sync(
            {
                "managed_names": ["repo-owned"],
                "profile_path": str(tmp_path / "profiles.toml"),
                "profile": profile,
                "registries": [
                    {
                        "scope": str(repo),
                        "directory": str(registry),
                        "desired": ["demo"],
                    }
                ],
                "sources": {"demo": str(source)},
            },
            tmp_path / "plan.json",
            authority=_authority(
                profile,
                tmp_path / ".agents" / "skills",
                linked={str(repo): ("demo",)},
            ),
        )


def test_authoritative_plan_rejects_checkout_drift_after_acceptance(
    tmp_path: Path,
) -> None:
    source = _source_skill(tmp_path / "source" / "demo")
    registry = tmp_path / ".agents" / "skills"
    profile = {
        "sources": {"demo": str(source)},
        "global": {"include": ["demo"]},
    }
    authority = _authority(profile, registry)
    (source / "untracked.md").write_text("not in accepted tree\n")

    with pytest.raises(ValueError, match="checkout is not clean"):
        plan_sync(
            {
                "profile_path": str(tmp_path / "profiles.toml"),
                "profile": profile,
                "registries": [
                    {
                        "scope": "global",
                        "directory": str(registry),
                        "desired": ["demo"],
                    }
                ],
                "sources": {"demo": str(source)},
            },
            tmp_path / "plan.json",
            authority=authority,
        )


def test_authoritative_plan_rejects_ignored_source_content(tmp_path: Path) -> None:
    source = _source_skill(tmp_path / "source" / "demo")
    ignore = source.parent / ".gitignore"
    ignore.write_text("*.ignored\n")
    subprocess.run(["git", "-C", str(source.parent), "add", ".gitignore"], check=True)
    subprocess.run(
        [
            "git",
            "-C",
            str(source.parent),
            "-c",
            "user.name=Test",
            "-c",
            "user.email=test@example.com",
            "-c",
            "commit.gpgsign=false",
            "commit",
            "-qm",
            "ignore policy",
        ],
        check=True,
    )
    registry = tmp_path / ".agents" / "skills"
    profile = {
        "sources": {"demo": str(source)},
        "global": {"include": ["demo"]},
    }
    authority = _authority(profile, registry)
    (source / "generated.ignored").write_text("not published\n")

    with pytest.raises(ValueError, match="checkout is not clean"):
        plan_sync(
            {
                "profile_path": str(tmp_path / "profiles.toml"),
                "profile": profile,
                "registries": [
                    {
                        "scope": "global",
                        "directory": str(registry),
                        "desired": ["demo"],
                    }
                ],
                "sources": {"demo": str(source)},
            },
            tmp_path / "plan.json",
            authority=authority,
        )


def test_authoritative_apply_rejects_repo_identity_change_after_plan(
    tmp_path: Path,
) -> None:
    source = _source_skill(tmp_path / "source" / "demo")
    repo = _repo(tmp_path / "repo")
    registry = repo / ".agents" / "skills"
    profile = {
        "sources": {"demo": str(source)},
        "repos": {str(repo): {"include": ["demo"], "vendor": []}},
    }
    authority = _authority(
        profile,
        tmp_path / ".agents" / "skills",
        linked={str(repo): ("demo",)},
    )
    artifact = tmp_path / "plan.json"
    planned = plan_sync(
        {
            "profile_path": str(tmp_path / "profiles.toml"),
            "profile": profile,
            "registries": [
                {
                    "scope": str(repo),
                    "directory": str(registry),
                    "desired": ["demo"],
                }
            ],
            "sources": {"demo": str(source)},
        },
        artifact,
        authority=authority,
    )
    subprocess.run(
        [
            "git",
            "-C",
            str(repo),
            "remote",
            "set-url",
            "origin",
            "https://example.com/other/repo.git",
        ],
        check=True,
    )

    with pytest.raises(BlockedOperation, match="Fleet authority is invalid"):
        apply_sync_plan(
            artifact,
            planned["digest"],
            False,
            authority=authority,
        )


def test_authoritative_vendor_blocks_invalid_unconfigured_provenance(
    tmp_path: Path,
) -> None:
    repo = _repo(tmp_path / "repo")
    registry = repo / ".agents" / "skills"
    owned = _skill(registry / "repo-owned", "Repository authority")
    state_path = repo / ".agents" / "skill-manager" / "vendor-lock.json"
    state_path.parent.mkdir(parents=True)
    state_path.write_text(
        json.dumps(
            {
                "version": 1,
                "snapshots": {"repo-owned": {"source_alias": "wrong"}},
            }
        )
    )
    profile: dict[str, object] = {
        "repos": {str(repo): {"include": [], "vendor": []}},
    }
    authority = _authority(
        profile,
        tmp_path / ".agents" / "skills",
        vendored={str(repo): ()},
    )

    with pytest.raises(ValueError, match="provenance is invalid"):
        plan_vendor(
            {
                "profile_path": str(tmp_path / "profiles.toml"),
                "profile": profile,
                "repo": str(repo),
                "registry": str(registry),
                "state_path": str(state_path),
                "sources": {},
                "desired": [],
            },
            tmp_path / "plan.json",
            authority=authority,
        )
    assert owned.is_dir()
