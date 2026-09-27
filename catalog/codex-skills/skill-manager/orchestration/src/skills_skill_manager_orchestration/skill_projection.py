from __future__ import annotations

import os
import re
import shutil
import tempfile
from pathlib import Path, PurePosixPath
from typing import Any

import yaml
from skills_snapshot_plan import tree_digest

from .fleet_domain import FleetConfigError, FleetManifest, HostBinding, ResolvedSkill
from .source_policy import validate_fleet_source


def projection_path(
    manifest: FleetManifest,
    host: HostBinding,
    skill: ResolvedSkill,
) -> str:
    binding = PurePosixPath(host.source_bindings[skill.source_id].path)
    if binding.name != skill.source_id or binding.parent.name != "sources":
        raise FleetConfigError(
            f"host source {skill.source_id} path cannot derive rendered Skill root"
        )
    manager_root = binding.parent.parent
    return str(manager_root / "rendered" / manifest.digest / skill.alias)


def materialize_host_projections(
    manifest: FleetManifest,
    host_id: str,
) -> list[dict[str, Any]]:
    host = manifest.host(host_id)
    desired = set(host.desired_global(manifest.global_include))
    for binding in host.repo_bindings.values():
        desired.update(binding.include)
        desired.update(binding.vendor)

    actions: list[dict[str, Any]] = []
    for alias in sorted(desired):
        skill = manifest.resolved_skill(alias)
        if not skill.requires_projection:
            continue
        source = Path(host.source_bindings[skill.source_id].path) / skill.relative_path
        target = Path(projection_path(manifest, host, skill))
        action = _materialize_projection(source, target, skill)
        actions.append(action)
    return actions


def _materialize_projection(
    source: Path,
    target: Path,
    skill: ResolvedSkill,
) -> dict[str, Any]:
    if not source.is_dir():
        raise FleetConfigError(f"projection source is not a Skill directory: {source}")
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix=f".{skill.alias}-",
        dir=target.parent,
    ) as directory:
        staged = Path(directory) / "skill"
        shutil.copytree(source, staged, symlinks=True)
        if skill.alias != skill.source_name or skill.implicit_invocation != "default":
            _rewrite_skill_frontmatter(
                staged / "SKILL.md",
                alias=(skill.alias if skill.alias != skill.source_name else None),
                implicit_invocation=skill.implicit_invocation,
            )
        if skill.implicit_invocation != "default":
            _rewrite_openai_policy(
                staged / "agents" / "openai.yaml",
                skill.implicit_invocation == "allow",
            )
        validate_fleet_source(staged)
        expected_digest = tree_digest(staged)
        if target.is_dir() and not target.is_symlink():
            try:
                current_digest = tree_digest(target)
            except ValueError:
                current_digest = None
            if current_digest == expected_digest:
                return {
                    "alias": skill.alias,
                    "path": str(target),
                    "implicit_invocation": skill.implicit_invocation,
                    "digest": expected_digest,
                    "status": "unchanged",
                }
        if target.exists() or target.is_symlink():
            if target.is_symlink() or not target.is_dir():
                target.unlink()
            else:
                shutil.rmtree(target)
        os.replace(staged, target)
    return {
        "alias": skill.alias,
        "path": str(target),
        "implicit_invocation": skill.implicit_invocation,
        "digest": expected_digest,
        "status": "changed",
    }


def _rewrite_skill_frontmatter(
    path: Path,
    *,
    alias: str | None,
    implicit_invocation: str,
) -> None:
    if path.is_symlink() or not path.is_file():
        raise FleetConfigError("projected SKILL.md must be a regular file")
    try:
        content = path.read_text()
    except (OSError, UnicodeError) as exc:
        raise FleetConfigError("projected SKILL.md is unreadable") from exc
    match = re.match(r"^---\r?\n(.*?)\r?\n---(?:\r?\n|$)", content, re.DOTALL)
    if match is None:
        raise FleetConfigError("projected SKILL.md has invalid YAML frontmatter")
    try:
        frontmatter = yaml.safe_load(match.group(1))
    except yaml.YAMLError as exc:
        raise FleetConfigError("projected SKILL.md frontmatter is invalid") from exc
    if not isinstance(frontmatter, dict):
        raise FleetConfigError("projected SKILL.md frontmatter must be a mapping")
    if alias is not None:
        frontmatter["name"] = alias
    if implicit_invocation != "default":
        frontmatter["disable-model-invocation"] = implicit_invocation == "deny"
    rendered = yaml.safe_dump(
        frontmatter,
        allow_unicode=True,
        sort_keys=False,
        width=1000,
    ).rstrip()
    path.write_text(f"---\n{rendered}\n---\n{content[match.end() :]}")


def _rewrite_openai_policy(path: Path, allow_implicit_invocation: bool) -> None:
    metadata: dict[str, Any] = {}
    if path.exists() or path.is_symlink():
        if path.is_symlink() or not path.is_file():
            raise FleetConfigError(
                "projected agents/openai.yaml must be a regular file"
            )
        try:
            loaded = yaml.safe_load(path.read_text())
        except (OSError, UnicodeError, yaml.YAMLError) as exc:
            raise FleetConfigError("projected agents/openai.yaml is invalid") from exc
        if loaded is not None and not isinstance(loaded, dict):
            raise FleetConfigError("projected agents/openai.yaml must be a mapping")
        metadata = {} if loaded is None else dict(loaded)
    policy = metadata.get("policy", {})
    if not isinstance(policy, dict):
        raise FleetConfigError("projected agents/openai.yaml policy must be a mapping")
    metadata["policy"] = {
        **policy,
        "allow_implicit_invocation": allow_implicit_invocation,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(
            metadata,
            allow_unicode=True,
            sort_keys=False,
            width=1000,
        )
    )


__all__ = ["materialize_host_projections", "projection_path"]
