from __future__ import annotations

import hashlib
import json
import subprocess
import zipfile
from pathlib import Path

import pytest

from plugin_build import (
    PackageError,
    assert_archive_limits,
    assert_unique_package_paths,
    build_portable_package,
)

DESCRIPTION = (
    "Engineering skills for planning, implementation, context reduction, "
    "live evidence review, UI design, diagrams, and stateful-system verification."
)
SHARED_FIELDS = [
    "name",
    "version",
    "description",
    "author.name",
    "repository",
    "license",
]


def git(repo: Path, *args: str, input: bytes | None = None) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        [
            "git",
            "-C",
            str(repo),
            "-c",
            "user.name=Test",
            "-c",
            "user.email=test@example.com",
            "-c",
            "commit.gpgsign=false",
            *args,
        ],
        check=True,
        capture_output=True,
        input=input,
    )


def write_json(path: Path, document: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")


def make_repo(
    tmp_path: Path,
    *,
    skills: tuple[str, ...] = ("alpha", "beta"),
    inventory: list[str] | None = None,
    codex_description: str = DESCRIPTION,
    logo: str | None = None,
    asset: dict | None = None,
) -> tuple[Path, str]:
    repo = tmp_path / "repo"
    for name in skills:
        skill = repo / "catalog" / "engineering" / name
        skill.mkdir(parents=True)
        (skill / "SKILL.md").write_text(
            f"---\nname: {name}\ndescription: Test skill.\n---\n\n# {name}\n",
            encoding="utf-8",
        )
        (skill / "agents").mkdir()
        (skill / "agents" / "openai.yaml").write_text("interface:\n  display_name: Test\n", encoding="utf-8")
        (skill / "references").mkdir()
        (skill / "references" / "guide.md").write_text(f"# {name}\n", encoding="utf-8")
        script = skill / "run.sh"
        script.write_text("#!/bin/sh\n", encoding="utf-8")
        script.chmod(0o755)
    (repo / "agents").mkdir()
    (repo / "agents" / "role.md").write_text("secret role\n", encoding="utf-8")
    (repo / "harnesses").mkdir()
    (repo / "harnesses" / "tool.py").write_text("print(1)\n", encoding="utf-8")
    (repo / "docs").mkdir()
    (repo / "docs" / "note.md").write_text("note\n", encoding="utf-8")
    other = repo / "catalog" / "codex-skills" / "other"
    other.mkdir(parents=True)
    (other / "SKILL.md").write_text("# other\n", encoding="utf-8")
    interface = {
        "displayName": "Engineering",
        "shortDescription": "Plan, implement, and review",
        "longDescription": DESCRIPTION,
        "developerName": "ronhuafeng",
        "category": "Developer Tools",
        "capabilities": ["Read", "Write"],
        "websiteURL": "https://github.com/ronhuafeng/skills-release",
    }
    if logo is not None:
        interface["logo"] = logo
    metadata = {
        "name": "ronhuafeng-engineering",
        "version": "0.1.0",
        "description": DESCRIPTION,
        "author": {"name": "ronhuafeng"},
        "repository": "https://github.com/ronhuafeng/skills-release",
        "license": "Apache-2.0",
        "keywords": ["engineering", "planning", "verification"],
        "skills": list(skills) if inventory is None else inventory,
        "shared_identity_fields": SHARED_FIELDS,
        "compatibility_manifests": [
            ".codex-plugin/plugin.json",
            ".claude-plugin/plugin.json",
        ],
        "openai": {"interface": interface},
    }
    if asset is not None:
        metadata["assets"] = [asset]
    write_json(repo / "release" / "plugins" / "engineering" / "source.json", metadata)
    for manifest, description in (
        (".codex-plugin/plugin.json", codex_description),
        (".claude-plugin/plugin.json", DESCRIPTION),
    ):
        write_json(
            repo / manifest,
            {
                "name": "ronhuafeng-engineering",
                "version": "0.1.0",
                "description": description,
                "author": {"name": "ronhuafeng"},
                "repository": "https://github.com/ronhuafeng/skills-release",
                "license": "Apache-2.0",
                "skills": "./catalog/engineering",
            },
        )
    git(repo, "init", "-b", "main")
    git(repo, "add", ".")
    git(repo, "commit", "-m", "init")
    commit = git(repo, "rev-parse", "HEAD").stdout.decode().strip()
    return repo, commit


def build(repo: Path, commit: str, destination: Path):
    return build_portable_package(
        repo,
        version="0.1.0",
        source_commit=commit,
        destination=destination,
    )


def zip_names(path: Path) -> list[str]:
    with zipfile.ZipFile(path) as archive:
        return archive.namelist()


def test_build_materializes_one_traceable_skill_package(tmp_path: Path) -> None:
    repo, commit = make_repo(tmp_path)
    before = {
        path.relative_to(repo).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in repo.rglob("*")
        if path.is_file() and ".git" not in path.parts
    }

    package = build(repo, commit, tmp_path / "dist")

    manifest = json.loads((package.root / "plugin.json").read_text(encoding="utf-8"))
    provenance = json.loads((package.root / "assets" / "provenance.json").read_text(encoding="utf-8"))
    assert manifest["$schema"] == "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json"
    assert manifest["name"] == "ronhuafeng-engineering"
    assert manifest["version"] == "0.1.0"
    assert "skills" not in manifest
    assert "mcpServers" not in manifest
    assert manifest["extensions"]["com.openai"]["interface"]["displayName"] == "Engineering"
    assert provenance["source_commit"] == commit
    assert provenance["skills"] == [
        {"name": "alpha", "source": "catalog/engineering/alpha"},
        {"name": "beta", "source": "catalog/engineering/beta"},
    ]
    assert [item.name for item in package.skills] == ["alpha", "beta"]
    names = zip_names(package.zip_path)
    assert "plugin.json" in names
    assert "skills/alpha/SKILL.md" in names
    assert "skills/alpha/agents/openai.yaml" in names
    assert "skills/alpha/references/guide.md" in names
    assert "agents/role.md" not in names
    assert "harnesses/tool.py" not in names
    assert "docs/note.md" not in names
    assert "catalog/codex-skills/other/SKILL.md" not in names
    assert "mcp.json" not in names
    after = {
        path.relative_to(repo).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in repo.rglob("*")
        if path.is_file() and ".git" not in path.parts
    }
    assert after == before
    with zipfile.ZipFile(package.zip_path) as archive:
        info = archive.getinfo("skills/alpha/run.sh")
        assert info.external_attr >> 16 & 0o777 == 0o755


def test_same_commit_and_version_produce_the_same_zip(tmp_path: Path) -> None:
    repo, commit = make_repo(tmp_path)

    first = build(repo, commit, tmp_path / "one")
    second = build(repo, commit, tmp_path / "two")

    assert first.zip_path.read_bytes() == second.zip_path.read_bytes()


def test_missing_or_undeclared_skill_fails(tmp_path: Path) -> None:
    missing_repo, missing_commit = make_repo(tmp_path / "missing", inventory=["alpha", "gamma"])
    with pytest.raises(PackageError) as missing:
        build(missing_repo, missing_commit, tmp_path / "missing-out")
    assert missing.value.code == "missing_file"

    extra_repo, extra_commit = make_repo(tmp_path / "extra", inventory=["alpha"])
    with pytest.raises(PackageError) as extra:
        build(extra_repo, extra_commit, tmp_path / "extra-out")
    assert extra.value.code == "inventory_mismatch"


def test_duplicate_skill_inventory_fails(tmp_path: Path) -> None:
    repo, commit = make_repo(tmp_path, skills=("alpha",), inventory=["alpha", "alpha"])

    with pytest.raises(PackageError) as caught:
        build(repo, commit, tmp_path / "out")

    assert caught.value.code == "duplicate_path"


def test_symlink_escape_fails(tmp_path: Path) -> None:
    repo, _commit = make_repo(tmp_path, skills=("alpha",))
    outside = tmp_path / "secret.txt"
    outside.write_text("nope\n", encoding="utf-8")
    (repo / "catalog" / "engineering" / "alpha" / "leak.txt").symlink_to(outside)
    git(repo, "add", "catalog/engineering/alpha/leak.txt")
    git(repo, "commit", "-m", "add symlink")
    commit = git(repo, "rev-parse", "HEAD").stdout.decode().strip()

    with pytest.raises(PackageError) as caught:
        build(repo, commit, tmp_path / "out")

    assert caught.value.code == "path_escape"


def test_duplicate_package_paths_fail() -> None:
    with pytest.raises(PackageError) as caught:
        assert_unique_package_paths(["skills/Alpha/SKILL.md", "skills/alpha/SKILL.md"])

    assert caught.value.code == "duplicate_path"


def test_identity_mismatch_fails(tmp_path: Path) -> None:
    repo, commit = make_repo(tmp_path, codex_description="Different description")

    with pytest.raises(PackageError) as caught:
        build(repo, commit, tmp_path / "out")

    assert caught.value.code == "identity_mismatch"


def test_version_and_commit_binding_fail(tmp_path: Path) -> None:
    repo, commit = make_repo(tmp_path)

    with pytest.raises(PackageError) as version:
        build_portable_package(
            repo,
            version="0.2.0",
            source_commit=commit,
            destination=tmp_path / "version",
        )
    assert version.value.code == "identity_mismatch"
    with pytest.raises(PackageError) as source:
        build_portable_package(
            repo,
            version="0.1.0",
            source_commit="a" * 40,
            destination=tmp_path / "commit",
        )
    assert source.value.code == "identity_mismatch"


def test_dirty_source_fails(tmp_path: Path) -> None:
    repo, commit = make_repo(tmp_path)
    (repo / "catalog" / "engineering" / "alpha" / "SKILL.md").write_text("changed\n", encoding="utf-8")

    with pytest.raises(PackageError) as caught:
        build(repo, commit, tmp_path / "out")

    assert caught.value.code == "dirty_source"


def test_missing_referenced_asset_fails(tmp_path: Path) -> None:
    repo, commit = make_repo(
        tmp_path,
        logo="./assets/logo.png",
        asset={
            "package": "assets/guide.pdf",
            "source": "release/plugins/engineering/assets/missing.pdf",
        },
    )

    with pytest.raises(PackageError) as caught:
        build(repo, commit, tmp_path / "out")

    assert caught.value.code == "missing_file"


def test_archive_limits_fail() -> None:
    with pytest.raises(PackageError) as caught:
        assert_archive_limits(
            compressed_bytes=1,
            uncompressed_bytes=1,
            entry_count=5001,
            largest_entry=1,
        )

    assert caught.value.code == "archive_limit"


def test_zip_has_one_plugin_root_and_stays_within_limits(tmp_path: Path) -> None:
    repo, commit = make_repo(tmp_path)

    package = build(repo, commit, tmp_path / "dist")

    names = zip_names(package.zip_path)
    assert names.count("plugin.json") == 1
    assert not any(name.endswith("/plugin.json") for name in names)
    assert all(".." not in name.split("/") and not name.startswith("/") for name in names)
    assert package.zip_path.stat().st_size < 100 * 1024 * 1024


def test_current_repository_package_traces_canonical_skills(tmp_path: Path) -> None:
    repo = Path(__file__).resolve().parents[3]
    clone = tmp_path / "clone"
    subprocess.run(
        ["git", "-c", "protocol.file.allow=always", "clone", "--local", "--no-hardlinks", str(repo), str(clone)],
        check=True,
        capture_output=True,
    )
    commit = git(clone, "rev-parse", "HEAD").stdout.decode().strip()
    if not (clone / "release" / "plugins" / "engineering" / "source.json").is_file():
        pytest.fail("source metadata is not on HEAD")

    package = build(clone, commit, tmp_path / "dist")

    canonical = sorted(
        path.parent.name
        for path in (clone / "catalog" / "engineering").glob("*/SKILL.md")
    )
    assert [item.name for item in package.skills] == canonical
    assert [item.source for item in package.skills] == [f"catalog/engineering/{name}" for name in canonical]
    names = zip_names(package.zip_path)
    assert "skills/model-with-tla/.tools/tla2tools.jar" in names
    assert not any("/.venv/" in name or name.startswith("agents/") or name == "mcp.json" for name in names)
    provenance = json.loads((package.root / "assets" / "provenance.json").read_text(encoding="utf-8"))
    assert provenance["source_commit"] == commit
    assert provenance["version"] == "0.1.0"
    for name in canonical:
        packaged = (package.root / "skills" / name / "SKILL.md").read_bytes()
        committed = git(clone, "show", f"HEAD:catalog/engineering/{name}/SKILL.md").stdout
        assert packaged == committed
