from __future__ import annotations

import subprocess
from pathlib import Path

import skills_skill_manager_orchestration.source_remote as source_remote


def test_revision_catalog_is_scoped_to_discovery_path(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    subprocess.run(["git", "init", "-q", str(source)], check=True)
    subprocess.run(
        ["git", "-C", str(source), "config", "user.email", "test@example.com"],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(source), "config", "user.name", "Test"],
        check=True,
    )
    subprocess.run(
        [
            "git",
            "-C",
            str(source),
            "remote",
            "add",
            "origin",
            "https://example.com/owner/source.git",
        ],
        check=True,
    )
    public = source / "skills" / "demo"
    public.mkdir(parents=True)
    (public / "SKILL.md").write_text(
        "---\nname: demo\ndescription: Public Skill.\n---\n"
    )
    internal = source / "internal" / "runtime"
    internal.mkdir(parents=True)
    (internal / "SKILL.md").write_text(
        "---\nname: runtime\ndescription: Use <value>.\n---\n"
    )
    subprocess.run(["git", "-C", str(source), "add", "."], check=True)
    subprocess.run(
        ["git", "-C", str(source), "commit", "-qm", "source"], check=True
    )
    revision = subprocess.run(
        ["git", "-C", str(source), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()

    catalog = source_remote.inspect_source_revision(
        source,
        "example.com/owner/source",
        revision,
        "skills",
    )

    assert list(catalog) == ["demo"]
    assert catalog["demo"].relative_path == "skills/demo"


def test_remote_observation_allows_clean_local_revision_drift(
    tmp_path: Path,
    monkeypatch,
) -> None:
    source = tmp_path / "source"
    source.mkdir()
    subprocess.run(["git", "init", "-q", str(source)], check=True)
    subprocess.run(
        ["git", "-C", str(source), "config", "user.email", "test@example.com"],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(source), "config", "user.name", "Test"],
        check=True,
    )
    subprocess.run(
        [
            "git",
            "-C",
            str(source),
            "remote",
            "add",
            "origin",
            "https://example.com/owner/source.git",
        ],
        check=True,
    )
    tracked = source / "tracked"
    tracked.write_text("first\n")
    subprocess.run(["git", "-C", str(source), "add", "tracked"], check=True)
    subprocess.run(["git", "-C", str(source), "commit", "-qm", "first"], check=True)

    tracked.write_text("second\n")
    subprocess.run(["git", "-C", str(source), "commit", "-qam", "second"], check=True)
    local_revision = subprocess.run(
        ["git", "-C", str(source), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    real_run = subprocess.run

    def run(command, **kwargs):
        if command[3:5] == ["ls-remote", "--exit-code"]:
            return subprocess.CompletedProcess(
                command,
                0,
                stdout=f"{local_revision}\tHEAD\n",
                stderr="",
            )
        return real_run(command, **kwargs)

    monkeypatch.setattr(source_remote.subprocess, "run", run)

    assert (
        source_remote.observe_remote_candidate(
            source,
            "example.com/owner/source",
        )
        == local_revision
    )
