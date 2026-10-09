from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from plugin_build.marketplace import MarketplaceError, verify_marketplace_checkout


@pytest.fixture
def checkout(tmp_path: Path) -> Path:
    source = Path(__file__).resolve().parents[3]
    target = tmp_path / "consumer"
    subprocess.run(["git", "clone", "--local", "--no-hardlinks", str(source), str(target)], check=True, capture_output=True)
    return target


def test_committed_checkout_exposes_canonical_plugin_without_package(checkout: Path) -> None:
    contract = verify_marketplace_checkout(checkout)
    assert contract.commit == subprocess.check_output(["git", "-C", str(checkout), "rev-parse", "HEAD"], text=True).strip()
    assert contract.version == "0.1.0"
    assert len(contract.skills) == 9
    assert not (checkout / "dist").exists()


def test_missing_or_uncommitted_marketplace_targets_fail(checkout: Path) -> None:
    manifest = checkout / ".codex-plugin/plugin.json"
    manifest.unlink()
    with pytest.raises(MarketplaceError, match="missing marketplace target"):
        verify_marketplace_checkout(checkout)

    manifest.write_bytes(subprocess.check_output(["git", "-C", str(checkout), "show", "HEAD:.codex-plugin/plugin.json"]))
    metadata_path = checkout / "release/plugins/engineering/source.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    metadata["skills"].append("uncommitted")
    metadata_path.write_text(json.dumps(metadata), encoding="utf-8")
    skill = checkout / "catalog/engineering/uncommitted/SKILL.md"
    skill.parent.mkdir()
    skill.write_text("---\nname: uncommitted\n---\n", encoding="utf-8")
    with pytest.raises(MarketplaceError, match="uncommitted engineering Skill"):
        verify_marketplace_checkout(checkout)


def test_local_dist_source_cannot_pass(checkout: Path) -> None:
    path = checkout / ".agents/plugins/marketplace.json"
    catalog = json.loads(path.read_text(encoding="utf-8"))
    catalog["plugins"][0]["source"] = {"source": "local", "path": "./dist/plugins/ronhuafeng-engineering"}
    path.write_text(json.dumps(catalog), encoding="utf-8")
    with pytest.raises(MarketplaceError, match="public Git repository root"):
        verify_marketplace_checkout(checkout)
