from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from plugin_build import build_portable_package
from plugin_build.marketplace import MarketplaceError, verify_marketplace_checkout
from test_build import git, recommit, write_json


@pytest.fixture
def checkout(tmp_path: Path) -> Path:
    source = Path(__file__).resolve().parents[3]
    target = tmp_path / "consumer"
    subprocess.run(["git", "clone", "--local", "--no-hardlinks", str(source), str(target)], check=True, capture_output=True)
    return target


def test_committed_checkout_exposes_canonical_plugin_without_package(checkout: Path) -> None:
    contract = verify_marketplace_checkout(checkout)
    assert contract.commit == git(checkout, "rev-parse", "HEAD").stdout.decode().strip()
    assert contract.version == json.loads((checkout / ".codex-plugin/plugin.json").read_text())["version"]
    assert contract.skills == tuple(sorted(path.parent.name for path in (checkout / "catalog/engineering").glob("*/SKILL.md")))
    assert not (checkout / "dist").exists()


def test_marketplace_has_no_optional_release_dependency(checkout: Path) -> None:
    import shutil
    shutil.rmtree(checkout / "release/plugins/engineering")
    assert verify_marketplace_checkout(checkout).skills


def test_future_skill_and_version_derive_from_committed_authority(checkout: Path) -> None:
    previous = verify_marketplace_checkout(checkout)
    name = "future-skill"
    target = checkout / f"catalog/engineering/{name}/SKILL.md"
    target.parent.mkdir()
    target.write_text(f"---\nname: {name}\ndescription: A future Skill.\n---\n", encoding="utf-8")
    (target.parent / "resource.txt").write_text("committed resource\n")
    for relative in (".codex-plugin/plugin.json", ".claude-plugin/plugin.json"):
        path = checkout / relative
        manifest = json.loads(path.read_text())
        manifest["version"] = "1.2.3"
        write_json(path, manifest)
    # No shadow inventory or release config update is needed.
    recommit(checkout, "add legitimate future Skill and version")
    contract = verify_marketplace_checkout(checkout)
    assert contract.version == "1.2.3"
    assert contract.skills == tuple(sorted((*previous.skills, name)))
    package = build_portable_package(
        checkout, version=contract.version, source_commit=contract.commit,
        destination=checkout.parent / "future-zip",
    )
    assert tuple(skill.name for skill in package.skills) == contract.skills
    assert package.version == contract.version


@pytest.mark.parametrize("relative", [
    ".codex-plugin/plugin.json",
    ".claude-plugin/plugin.json",
    ".agents/plugins/marketplace.json",
    ".claude-plugin/marketplace.json",
    "catalog/engineering/context-reduce/SKILL.md",
    "catalog/engineering/context-reduce/references/review-guide.md",
    "catalog/engineering/model-with-tla/.tools/tla2tools.jar",
])
@pytest.mark.parametrize("mutation", ["missing", "dirty", "staged", "untracked", "symlink"])
def test_marketplace_rejects_noncommitted_targets(checkout: Path, relative: str, mutation: str) -> None:
    path = checkout / relative
    if mutation == "missing":
        path.unlink()
    elif mutation in {"dirty", "staged"}:
        path.write_bytes(path.read_bytes() + b"\nchanged\n")
        if mutation == "staged":
            git(checkout, "add", relative)
    elif mutation == "untracked":
        git(checkout, "rm", "--cached", relative)
    else:
        original = path.read_bytes()
        outside = checkout.parent / "outside"
        outside.write_bytes(original)
        path.unlink()
        path.symlink_to(outside)
    with pytest.raises(MarketplaceError):
        verify_marketplace_checkout(checkout)


def test_untracked_new_skill_and_resource_fail(checkout: Path) -> None:
    resource = checkout / "catalog/engineering/context-reduce/untracked.txt"
    resource.write_text("resource\n")
    with pytest.raises(MarketplaceError, match="uncommitted"):
        verify_marketplace_checkout(checkout)
    resource.unlink()
    skill = checkout / "catalog/engineering/new-skill/SKILL.md"
    skill.parent.mkdir()
    skill.write_text("new Skill\n")
    with pytest.raises(MarketplaceError, match="uncommitted"):
        verify_marketplace_checkout(checkout)


@pytest.mark.parametrize("mutation", ["local-source", "claude-identity", "claude-path", "claude-marketplace"])
def test_committed_manifest_and_marketplace_semantics_fail(checkout: Path, mutation: str) -> None:
    relative = {
        "local-source": ".agents/plugins/marketplace.json",
        "claude-identity": ".claude-plugin/plugin.json",
        "claude-path": ".claude-plugin/plugin.json",
        "claude-marketplace": ".claude-plugin/marketplace.json",
    }[mutation]
    path = checkout / relative
    document = json.loads(path.read_text())
    if mutation == "local-source":
        document["plugins"][0]["source"] = {"source": "local", "path": "./dist/plugins/ronhuafeng-engineering"}
    elif mutation == "claude-identity":
        document["version"] = "9.9.9"
    elif mutation == "claude-path":
        document["skills"] = "./catalog/codex-skills"
    else:
        document["plugins"][0]["source"] = "./dist"
    write_json(path, document)
    recommit(checkout, "commit invalid consumer contract")
    with pytest.raises(MarketplaceError):
        verify_marketplace_checkout(checkout)


@pytest.mark.parametrize("mutation", ["resource-symlink", "directory-symlink", "case-collision", "gitlink"])
def test_committed_unsafe_resources_fail(checkout: Path, mutation: str) -> None:
    root = checkout / "catalog/engineering/context-reduce"
    if mutation == "resource-symlink":
        (root / "escape").symlink_to("/tmp")
    elif mutation == "directory-symlink":
        import shutil
        saved = checkout.parent / "saved"
        shutil.move(root / "references", saved)
        (root / "references").symlink_to(saved, target_is_directory=True)
    elif mutation == "case-collision":
        (root / "SKILL.MD").write_text("collision\n")
    else:
        git(checkout, "update-index", "--add", "--cacheinfo", f"160000,{git(checkout, 'rev-parse', 'HEAD').stdout.decode().strip()},catalog/engineering/context-reduce/submodule")
    if mutation == "gitlink":
        git(checkout, "commit", "-m", "commit unsafe canonical resource")
    else:
        recommit(checkout, "commit unsafe canonical resource")
    with pytest.raises(MarketplaceError):
        verify_marketplace_checkout(checkout)


def test_client_specific_manifest_fields_do_not_need_byte_parity(checkout: Path) -> None:
    path = checkout / ".claude-plugin/plugin.json"
    document = json.loads(path.read_text())
    document["keywords"] = ["claude"]
    write_json(path, document)
    recommit(checkout, "add client-specific field")
    assert verify_marketplace_checkout(checkout).skills


def test_ignored_untracked_skill_cannot_become_inventory(checkout: Path) -> None:
    skill = checkout / "catalog/engineering/ignored-skill/SKILL.md"
    skill.parent.mkdir()
    skill.write_text("untracked Skill\n")
    with (checkout / ".git/info/exclude").open("a") as excludes:
        excludes.write("\ncatalog/engineering/ignored-skill/\n")
    with pytest.raises(MarketplaceError, match="uncommitted engineering Skill inventory"):
        verify_marketplace_checkout(checkout)
