from __future__ import annotations

from pathlib import Path
from typing import Any

import tomllib

from skills_frontmatter import read_frontmatter


def load_profile(path: Path | str, missing_ok: bool = True) -> dict[str, Any]:
    resolved = Path(path).expanduser()
    if not resolved.exists():
        if missing_ok:
            return {}
        raise FileNotFoundError(f"profile not found: {resolved}")
    with resolved.open("rb") as handle:
        data = tomllib.load(handle)
    return data if isinstance(data, dict) else {}


def as_abs(path: str | Path) -> str:
    return str(Path(path).expanduser().resolve(strict=False))


def validate_skill_name(name: str, label: str = "name") -> str:
    if (
        not name
        or name in {".", ".."}
        or name.startswith(".")
        or "/" in name
        or "\\" in name
        or "\0" in name
    ):
        raise ValueError(f"invalid {label}: {name}")
    return name


def require_table(profile: dict[str, Any], key: str) -> dict[str, Any]:
    value = profile.setdefault(key, {})
    if not isinstance(value, dict):
        raise ValueError(f"[{key}] must be a TOML table")
    return value


def include_list(table: dict[str, Any]) -> list[str]:
    include = table.setdefault("include", [])
    if not isinstance(include, list):
        raise ValueError("include must be a TOML array")
    normalized = [validate_skill_name(str(item), "skill name") for item in include]
    table["include"] = normalized
    return normalized


def vendor_list(table: dict[str, Any]) -> list[str]:
    vendor = table.setdefault("vendor", [])
    if not isinstance(vendor, list):
        raise ValueError("vendor must be a TOML array")
    normalized = [validate_skill_name(str(item), "skill name") for item in vendor]
    if len(set(normalized)) != len(normalized):
        raise ValueError("vendor must not contain duplicate skill names")
    table["vendor"] = normalized
    return normalized


def normalize_profile(profile: dict[str, Any]) -> dict[str, Any]:
    require_table(profile, "source_roots")
    require_table(profile, "sources")
    global_table = require_table(profile, "global")
    include_list(global_table)
    repos = require_table(profile, "repos")
    for repo_path, repo_data in list(repos.items()):
        if not isinstance(repo_data, dict):
            raise ValueError(f"repo entry must be a table: {repo_path}")
        include_list(repo_data)
        vendors = vendor_list(repo_data)
        overlap = set(include_list(repo_data)) & set(vendors)
        if overlap:
            raise ValueError(
                f"repo skills cannot be both included and vendored: {', '.join(sorted(overlap))}"
            )
    return profile


def quote_toml_string(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def write_string_table(lines: list[str], heading: str, values: dict[str, Any]) -> None:
    if not values:
        return
    lines.append(f"[{heading}]")
    for key in sorted(values):
        lines.append(
            f"{quote_toml_string(str(key))} = {quote_toml_string(str(values[key]))}"
        )
    lines.append("")


def render_profile(profile: dict[str, Any]) -> str:
    normalize_profile(profile)
    lines: list[str] = []
    write_string_table(lines, "source_roots", require_table(profile, "source_roots"))
    write_string_table(lines, "sources", require_table(profile, "sources"))

    global_table = require_table(profile, "global")
    lines.append("[global]")
    lines.append(
        "include = ["
        + ", ".join(quote_toml_string(item) for item in include_list(global_table))
        + "]"
    )
    lines.append("")

    repos = require_table(profile, "repos")
    for repo_path in sorted(repos):
        repo_data = repos[repo_path]
        if not isinstance(repo_data, dict):
            raise ValueError(f"repo entry must be a table: {repo_path}")
        lines.append(f"[repos.{quote_toml_string(repo_path)}]")
        lines.append(
            "include = ["
            + ", ".join(quote_toml_string(item) for item in include_list(repo_data))
            + "]"
        )
        lines.append(
            "vendor = ["
            + ", ".join(quote_toml_string(item) for item in vendor_list(repo_data))
            + "]"
        )
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def validate_source_path(path: Path | str) -> Path:
    resolved = Path(path).expanduser().resolve(strict=False)
    if not resolved.exists() or not resolved.is_dir():
        raise ValueError(f"source path is not a directory: {resolved}")
    if not (resolved / "SKILL.md").exists():
        raise ValueError(f"source path has no SKILL.md: {resolved}")
    return resolved


def validate_source_root(path: Path | str) -> None:
    resolved = Path(path).expanduser().resolve(strict=False)
    if not resolved.exists() or not resolved.is_dir():
        raise ValueError(f"source root is not a directory: {resolved}")


def validate_repo(path: Path | str) -> None:
    resolved = Path(path).expanduser().resolve(strict=False)
    if not resolved.exists() or not resolved.is_dir():
        raise ValueError(f"repo path is not a directory: {resolved}")


def add_unique(items: list[str], item: str) -> bool:
    if item in items:
        return False
    items.append(item)
    return True


def remove_item(items: list[str], item: str) -> bool:
    if item not in items:
        return False
    items.remove(item)
    return True


def add_source_root(
    profile: dict[str, Any], alias: str, raw_path: str | Path
) -> list[str]:
    validate_skill_name(alias, "source root alias")
    path = Path(raw_path).expanduser().resolve(strict=False)
    validate_source_root(path)
    roots = require_table(profile, "source_roots")
    current = roots.get(alias)
    if current is not None and as_abs(str(current)) != str(path):
        raise ValueError(
            f"source root alias already points elsewhere: {alias} -> {current}"
        )
    roots[alias] = str(path)
    return [f"source root {alias} -> {path}"]


def add_source(profile: dict[str, Any], alias: str, raw_path: str | Path) -> list[str]:
    validate_skill_name(alias, "source alias")
    path = validate_source_path(raw_path)
    frontmatter = read_frontmatter(path)
    sources = require_table(profile, "sources")
    current = sources.get(alias)
    if current is not None and as_abs(str(current)) != str(path):
        raise ValueError(f"source alias already points elsewhere: {alias} -> {current}")
    sources[alias] = str(path)
    changes = [f"source {alias} -> {path}"]
    fm_name = frontmatter.get("name")
    if isinstance(fm_name, str) and fm_name and fm_name != alias:
        changes.append(
            f"warning: alias {alias} differs from frontmatter name {fm_name}"
        )
    if "description" not in frontmatter:
        changes.append("warning: source frontmatter has no description")
    return changes


def remove_source(profile: dict[str, Any], alias: str) -> list[str]:
    source_alias = validate_skill_name(alias, "source alias")
    sources = require_table(profile, "sources")
    current = sources.pop(source_alias, None)
    if current is None:
        return [f"source {source_alias} already absent"]
    return [f"remove source {source_alias} -> {current}"]


def add_repo(profile: dict[str, Any], raw_repo: str | Path) -> list[str]:
    repo = Path(raw_repo).expanduser().resolve(strict=False)
    validate_repo(repo)
    repos = require_table(profile, "repos")
    repo_key = str(repo)
    created = repo_key not in repos
    repos.setdefault(repo_key, {"include": [], "vendor": []})
    include_list(repos[repo_key])
    vendor_list(repos[repo_key])
    return [f"{'add' if created else 'keep'} repo {repo_key}"]


def scope_table(
    profile: dict[str, Any],
    *,
    global_scope: bool = False,
    repo: str | Path | None = None,
) -> tuple[str, dict[str, Any]]:
    if global_scope:
        table = require_table(profile, "global")
        table.setdefault("include", [])
        return "global", table
    if repo is None:
        raise ValueError("choose global_scope=True or repo=<repo-root>")
    repo_path = Path(repo).expanduser().resolve(strict=False)
    validate_repo(repo_path)
    repos = require_table(profile, "repos")
    repo_key = str(repo_path)
    table = repos.setdefault(repo_key, {"include": [], "vendor": []})
    if not isinstance(table, dict):
        raise ValueError(f"repo entry must be a table: {repo_key}")
    table.setdefault("include", [])
    return f"repo {repo_key}", table


def include_skill(
    profile: dict[str, Any],
    skill: str,
    *,
    global_scope: bool = False,
    repo: str | Path | None = None,
) -> list[str]:
    scope, table = scope_table(profile, global_scope=global_scope, repo=repo)
    skill_name = validate_skill_name(str(skill), "skill name")
    if not global_scope and skill_name in vendor_list(table):
        raise ValueError(f"repo skill is already vendored: {skill_name}")
    changed = add_unique(include_list(table), skill_name)
    sources = require_table(profile, "sources")
    changes = [f"{'include' if changed else 'keep'} {skill_name} in {scope}"]
    if skill_name not in sources:
        changes.append(
            f"warning: {skill_name} has no [sources] mapping; apply may require an existing reusable symlink target"
        )
    return changes


def exclude_skill(
    profile: dict[str, Any],
    skill: str,
    *,
    global_scope: bool = False,
    repo: str | Path | None = None,
) -> list[str]:
    scope, table = scope_table(profile, global_scope=global_scope, repo=repo)
    skill_name = validate_skill_name(str(skill), "skill name")
    changed = remove_item(include_list(table), skill_name)
    return [f"{'exclude' if changed else 'already absent'} {skill_name} from {scope}"]


def vendor_skill(profile: dict[str, Any], skill: str, *, repo: str | Path) -> list[str]:
    scope, table = scope_table(profile, repo=repo)
    skill_name = validate_skill_name(str(skill), "skill name")
    if skill_name in include_list(table):
        raise ValueError(f"repo skill is already exposed as a symlink: {skill_name}")
    changed = add_unique(vendor_list(table), skill_name)
    sources = require_table(profile, "sources")
    changes = [f"{'vendor' if changed else 'keep vendored'} {skill_name} in {scope}"]
    if skill_name not in sources:
        changes.append(f"warning: {skill_name} has no [sources] mapping")
    return changes


def unvendor_skill(
    profile: dict[str, Any], skill: str, *, repo: str | Path
) -> list[str]:
    scope, table = scope_table(profile, repo=repo)
    skill_name = validate_skill_name(str(skill), "skill name")
    changed = remove_item(vendor_list(table), skill_name)
    return [
        f"{'unvendor' if changed else 'already not vendored'} {skill_name} from {scope}"
    ]


def source_map(profile: dict[str, Any]) -> dict[str, Path]:
    sources = profile.get("sources", {})
    if not isinstance(sources, dict):
        return {}
    return {
        validate_skill_name(str(name), "source alias"): Path(str(path))
        .expanduser()
        .resolve(strict=False)
        for name, path in sources.items()
    }


def profile_source_roots(profile: dict[str, Any] | None) -> list[Path]:
    if not profile:
        return []
    roots = profile.get("source_roots", {})
    if not isinstance(roots, dict):
        return []
    return [
        Path(str(path)).expanduser().resolve(strict=False)
        for _, path in sorted(roots.items())
    ]


def profile_sources(profile: dict[str, Any] | None) -> dict[str, Path]:
    if not profile:
        return {}
    sources = profile.get("sources", {})
    if not isinstance(sources, dict):
        return {}
    return {
        str(alias): Path(str(path)).expanduser().resolve(strict=False)
        for alias, path in sorted(sources.items())
    }


def repo_profiles(
    profile: dict[str, Any], repo: Path | str | None = None
) -> dict[str, list[str]]:
    repos = profile.get("repos", {})
    if not isinstance(repos, dict):
        if repo is None:
            return {}
        raise ValueError("profile has no [repos] table")
    if repo is None:
        return {
            str(path): include_list(data)
            for path, data in repos.items()
            if isinstance(data, dict)
        }
    repo_abs = str(Path(repo).expanduser().resolve(strict=False))
    data = repos.get(repo_abs, repos.get(str(repo)))
    if data is None:
        raise ValueError(f"profile has no repo entry for {repo_abs}")
    if not isinstance(data, dict):
        raise ValueError(f"repo entry must be a table: {repo_abs}")
    return {repo_abs: include_list(data)}


def repo_vendors(
    profile: dict[str, Any], repo: Path | str | None = None
) -> dict[str, list[str]]:
    repos = profile.get("repos", {})
    if not isinstance(repos, dict):
        if repo is None:
            return {}
        raise ValueError("profile has no [repos] table")
    if repo is None:
        return {
            str(path): vendor_list(data)
            for path, data in repos.items()
            if isinstance(data, dict)
        }
    repo_abs = str(Path(repo).expanduser().resolve(strict=False))
    data = repos.get(repo_abs, repos.get(str(repo)))
    if data is None:
        raise ValueError(f"profile has no repo entry for {repo_abs}")
    if not isinstance(data, dict):
        raise ValueError(f"repo entry must be a table: {repo_abs}")
    return {repo_abs: vendor_list(data)}
