from __future__ import annotations

import tomllib
from pathlib import Path

import pytest
import yaml

from skills_skill_manager_orchestration.fleet_domain import (
    FleetConfigError,
    FleetManifest,
    SourceSkill,
)
from skills_skill_manager_orchestration.fleet_render import (
    host_skill_policies,
    render_manifest_host,
)
from skills_skill_manager_orchestration.skill_projection import (
    materialize_host_projections,
)


ENROLLMENT_ID = "11111111-1111-4111-8111-111111111111"


def _manifest(
    tmp_path: Path,
    *,
    sources: dict[str, dict[str, object]],
    skills: dict[str, dict[str, object]],
    include: list[str],
) -> FleetManifest:
    raw_sources = {
        source_id: {
            "kind": "git",
            "origin": f"example.com/owner/{source_id}",
            "revision": "0" * 40,
            **source,
        }
        for source_id, source in sources.items()
    }
    raw = {
        "schema_version": 5,
        "global": {"include": include},
        "sources": raw_sources,
        "skills": skills,
        "repos": {},
        "hosts": {
            "local": {
                "enrollment_id": ENROLLMENT_ID,
                "hostname": "local",
                "username": "user",
                "transport": "local",
                "profile": str(tmp_path / "profiles.toml"),
                "runtime": str(tmp_path / "skill-manager"),
                "global_registry": str(tmp_path / ".agents" / "skills"),
                "global_add": [],
                "global_remove": [],
                "sources": {
                    source_id: {
                        "path": str(tmp_path / "cache" / "sources" / source_id),
                        "discovery_path": "skills",
                    }
                    for source_id in sources
                },
                "repos": {},
            }
        },
    }
    catalogs = {
        source_id: {"prototype": SourceSkill("skills/prototype", source_id[0] * 40)}
        for source_id in sources
    }
    return FleetManifest.from_raw(raw).with_catalogs(catalogs)


def test_manifest_resolves_duplicate_native_names_and_policy_precedence(
    tmp_path: Path,
) -> None:
    manifest = _manifest(
        tmp_path,
        sources={
            "matt": {"defaults": {"implicit_invocation": "default"}},
            "emil": {"defaults": {"implicit_invocation": "deny"}},
        },
        skills={
            "prototype": {"source": "matt", "source_name": "prototype"},
            "emil-prototype": {
                "source": "emil",
                "source_name": "prototype",
                "implicit_invocation": "allow",
            },
        },
        include=["prototype", "emil-prototype"],
    )

    assert manifest.resolved_skill("prototype").implicit_invocation == "default"
    assert manifest.resolved_skill("prototype").requires_projection is False
    assert manifest.resolved_skill("emil-prototype").implicit_invocation == "allow"
    assert manifest.resolved_skill("emil-prototype").requires_projection is True
    assert FleetManifest.from_raw(tomllib.loads(manifest.to_toml())).as_dict() == (
        manifest.as_dict()
    )

    policies = host_skill_policies(manifest, "local")
    assert policies["emil-prototype"] == {
        "source": "emil",
        "source_name": "prototype",
        "source_default": "deny",
        "skill_override": "allow",
        "effective": "allow",
        "projected": True,
    }


def test_manifest_rejects_invalid_implicit_invocation(tmp_path: Path) -> None:
    with pytest.raises(
        FleetConfigError,
        match="must be default, allow, or deny",
    ):
        _manifest(
            tmp_path,
            sources={"emil": {"defaults": {"implicit_invocation": "sometimes"}}},
            skills={},
            include=["prototype"],
        )


def test_projection_sets_openai_and_claude_policy_and_is_idempotent(
    tmp_path: Path,
) -> None:
    source = tmp_path / "cache" / "sources" / "emil" / "skills" / "prototype"
    (source / "agents").mkdir(parents=True)
    (source / "SKILL.md").write_text(
        "---\n"
        "name: prototype\n"
        "description: Build several UI prototypes.\n"
        "---\n"
        "Instructions.\n"
    )
    (source / "agents" / "openai.yaml").write_text(
        "interface:\n"
        "  display_name: Prototype\n"
        "  short_description: Build UI prototypes\n"
        "policy:\n"
        "  allow_implicit_invocation: true\n"
    )
    manifest = _manifest(
        tmp_path,
        sources={"emil": {"defaults": {"implicit_invocation": "deny"}}},
        skills={
            "emil-prototype": {
                "source": "emil",
                "source_name": "prototype",
            }
        },
        include=["emil-prototype"],
    )

    first = materialize_host_projections(manifest, "local")
    second = materialize_host_projections(manifest, "local")
    rendered = render_manifest_host(manifest, "local")
    projected = Path(
        tomllib.loads(str(rendered["profile_toml"]))["sources"]["emil-prototype"]
    )

    assert first[0]["status"] == "changed"
    assert second[0]["status"] == "unchanged"
    assert first[0]["digest"] == second[0]["digest"]
    skill_text = (projected / "SKILL.md").read_text()
    assert "name: emil-prototype\n" in skill_text
    assert "disable-model-invocation: true\n" in skill_text
    metadata = yaml.safe_load((projected / "agents" / "openai.yaml").read_text())
    assert metadata["interface"]["display_name"] == "Prototype"
    assert metadata["policy"]["allow_implicit_invocation"] is False
