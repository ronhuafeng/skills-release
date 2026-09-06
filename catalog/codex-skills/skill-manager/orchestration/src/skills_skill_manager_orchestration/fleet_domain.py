from __future__ import annotations

import hashlib
import json
import posixpath
import re
import uuid
from dataclasses import dataclass, replace
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import urlparse

import tomllib
from skills_profile_toml import validate_skill_name

FLEET_SCHEMA_VERSION = 4
ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
GIT_OBJECT_ID_PATTERN = re.compile(r"^[0-9a-f]{40}$")
SHA256_DIGEST_PATTERN = re.compile(r"^[0-9a-f]{64}$")
CANONICAL_GIT_IDENTITY_PATTERN = re.compile(
    r"^[A-Za-z0-9.-]+(?::[0-9]+)?/[A-Za-z0-9._~/-]+$"
)


class FleetConfigError(ValueError):
    pass


def canonical_digest(value: object) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def require_table(parent: dict[str, Any], key: str) -> dict[str, Any]:
    value = parent.get(key, {})
    if not isinstance(value, dict):
        raise FleetConfigError(f"{key} must be a TOML table")
    return value


def reject_unknown_keys(
    value: dict[str, Any],
    allowed: set[str],
    label: str,
) -> None:
    unknown = sorted(set(value) - allowed)
    if unknown:
        raise FleetConfigError(
            f"{label} contains unknown field(s): {', '.join(unknown)}"
        )


def logical_id(value: object, label: str) -> str:
    text = str(value)
    if not ID_PATTERN.fullmatch(text):
        raise FleetConfigError(f"invalid {label}: {text}")
    return text


def canonical_enrollment_id(value: object, label: str) -> str:
    text = str(value)
    try:
        parsed = uuid.UUID(text)
    except (AttributeError, ValueError) as exc:
        raise FleetConfigError(f"{label} must be a canonical UUID") from exc
    if str(parsed) != text:
        raise FleetConfigError(f"{label} must be a canonical UUID")
    return text


def string_list(value: object, label: str) -> list[str]:
    if not isinstance(value, list):
        raise FleetConfigError(f"{label} must be a TOML array")
    result = [validate_skill_name(str(item), label) for item in value]
    if len(result) != len(set(result)):
        raise FleetConfigError(f"{label} must not contain duplicates")
    return result


def absolute_path(value: object, label: str) -> str:
    text = str(value)
    if not PurePosixPath(text).is_absolute():
        raise FleetConfigError(f"{label} must be an absolute POSIX path")
    return posixpath.normpath(text)


def relative_path(value: object, label: str) -> str:
    text = str(value)
    path = PurePosixPath(text)
    if (
        "\\" in text
        or path.is_absolute()
        or not path.parts
        or any(part in {"", ".", ".."} for part in path.parts)
    ):
        raise FleetConfigError(f"{label} must be a non-traversing relative POSIX path")
    return path.as_posix()


def canonical_git_identity(value: object, label: str) -> str:
    text = str(value)
    path = text.split("/", 1)[1] if "/" in text else ""
    if (
        not CANONICAL_GIT_IDENTITY_PATTERN.fullmatch(text)
        or text.endswith(".git")
        or "//" in text
        or any(part in {"", ".", ".."} for part in PurePosixPath(path).parts)
    ):
        raise FleetConfigError(f"{label} must use canonical Git identity")
    return text


def credential_free_fetch_url(value: object, label: str) -> str:
    text = str(value)
    parsed = urlparse(text)
    if parsed.query or parsed.fragment:
        raise FleetConfigError(f"{label} must not contain query or fragment data")
    if parsed.scheme == "https" and (
        parsed.username is not None or parsed.password is not None
    ):
        raise FleetConfigError(f"{label} must not contain HTTPS credentials")
    if parsed.scheme == "ssh" and parsed.password is not None:
        raise FleetConfigError(f"{label} must not contain an SSH password")
    if not parsed.scheme and "@" in text and ":" in text.split("@", 1)[0]:
        raise FleetConfigError(f"{label} must not contain a password")
    return text


@dataclass(frozen=True)
class SourceSkill:
    relative_path: str
    tree_oid: str

    @classmethod
    def from_raw(cls, alias: str, raw: object) -> SourceSkill:
        if not isinstance(raw, dict):
            raise FleetConfigError(f"source alias {alias} must be a TOML table")
        reject_unknown_keys(
            raw,
            {"relative_path", "tree_oid"},
            f"source alias {alias}",
        )
        normalized_path = relative_path(
            raw.get("relative_path", ""),
            f"source alias {alias} relative_path",
        )
        tree_oid = str(raw.get("tree_oid", ""))
        if not GIT_OBJECT_ID_PATTERN.fullmatch(tree_oid):
            raise FleetConfigError(
                f"source alias {alias} tree_oid must be a lowercase Git object ID"
            )
        return cls(relative_path=normalized_path, tree_oid=tree_oid)

    def as_dict(self) -> dict[str, str]:
        return {
            "relative_path": self.relative_path,
            "tree_oid": self.tree_oid,
        }


@dataclass(frozen=True)
class SourceSpec:
    source_id: str
    origin: str
    revision: str
    skills: dict[str, SourceSkill]

    @classmethod
    def from_raw(cls, raw_source_id: object, raw: object) -> SourceSpec:
        source_id = logical_id(raw_source_id, "source_id")
        if not isinstance(raw, dict):
            raise FleetConfigError(f"source {source_id} must be a TOML table")
        reject_unknown_keys(
            raw,
            {"kind", "origin", "revision"},
            f"source {source_id}",
        )
        if raw.get("kind") != "git":
            raise FleetConfigError(f"source {source_id} kind must be git")
        origin = canonical_git_identity(
            raw.get("origin", ""),
            f"source {source_id} origin",
        )
        revision = str(raw.get("revision", ""))
        if not GIT_OBJECT_ID_PATTERN.fullmatch(revision):
            raise FleetConfigError(f"source {source_id} revision must be a full commit")
        return cls(
            source_id=source_id,
            origin=origin,
            revision=revision,
            skills={},
        )

    @classmethod
    def from_wire(cls, raw_source_id: object, raw: object) -> SourceSpec:
        if not isinstance(raw, dict):
            raise FleetConfigError("host audit source must be an object")
        reject_unknown_keys(raw, {"kind", "origin", "revision", "skills"}, "host audit source")
        source = cls.from_raw(
            raw_source_id,
            {key: raw[key] for key in ("kind", "origin", "revision") if key in raw},
        )
        skills = {
            validate_skill_name(str(alias), "source skill"): SourceSkill.from_raw(
                validate_skill_name(str(alias), "source skill"), skill
            )
            for alias, skill in require_table(raw, "skills").items()
        }
        return replace(source, skills=skills)

    def as_dict(self) -> dict[str, Any]:
        return {
            "kind": "git",
            "origin": self.origin,
            "revision": self.revision,
        }

    def as_wire_dict(self) -> dict[str, Any]:
        return {
            **self.as_dict(),
            "skills": {
                alias: data.as_dict() for alias, data in sorted(self.skills.items())
            },
        }

def _toml_quote(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def _toml_array(values: tuple[str, ...]) -> str:
    return "[" + ", ".join(_toml_quote(value) for value in values) + "]"


@dataclass(frozen=True)
class HostSourceBinding:
    path: str
    discovery_path: str | None
    fetch_url: str | None

    @classmethod
    def from_raw(cls, source_id: str, raw: object) -> HostSourceBinding:
        if not isinstance(raw, dict):
            raise FleetConfigError(f"host source {source_id} must be a TOML table")
        reject_unknown_keys(
            raw,
            {"path", "discovery_path", "fetch_url"},
            f"host source {source_id}",
        )
        raw_discovery_path = raw.get("discovery_path")
        if raw_discovery_path is not None and type(raw_discovery_path) is not str:
            raise FleetConfigError(
                f"host source {source_id} discovery_path must be a string"
            )
        if raw_discovery_path == ".":
            discovery_path = "."
        elif isinstance(raw_discovery_path, str):
            discovery_path = relative_path(
                raw_discovery_path,
                f"host source {source_id} discovery_path",
            )
        else:
            discovery_path = None
        raw_fetch_url = raw.get("fetch_url")
        if raw_fetch_url is not None and (
            type(raw_fetch_url) is not str or not raw_fetch_url
        ):
            raise FleetConfigError(
                f"host source {source_id} fetch_url must be a non-empty string"
            )
        return cls(
            path=absolute_path(raw.get("path", ""), f"host source {source_id} path"),
            discovery_path=discovery_path,
            fetch_url=(
                None
                if raw_fetch_url is None
                else credential_free_fetch_url(
                    raw_fetch_url,
                    f"host source {source_id} fetch_url",
                )
            ),
        )

    def as_dict(self) -> dict[str, str]:
        result = {"path": self.path}
        if self.discovery_path is not None:
            result["discovery_path"] = self.discovery_path
        if self.fetch_url is not None:
            result["fetch_url"] = self.fetch_url
        return result


def index_source_skills(sources: dict[str, SourceSpec]) -> dict[str, str]:
    owners: dict[str, str] = {}
    for source_id, source in sources.items():
        for alias in source.skills:
            if alias in owners:
                raise FleetConfigError(
                    f"source alias is declared more than once: {alias}"
                )
            owners[alias] = source_id
    return owners


@dataclass(frozen=True)
class RepoSpec:
    repo_id: str
    remote: str

    @classmethod
    def from_raw(cls, raw_repo_id: object, raw: object) -> RepoSpec:
        repo_id = logical_id(raw_repo_id, "repo_id")
        if not isinstance(raw, dict):
            raise FleetConfigError(f"repo {repo_id} must be a TOML table")
        reject_unknown_keys(
            raw,
            {"remote"},
            f"repo {repo_id}",
        )
        remote = canonical_git_identity(
            raw.get("remote", ""),
            f"repo {repo_id} remote",
        )
        return cls(repo_id=repo_id, remote=remote)

    def as_dict(self) -> dict[str, Any]:
        return {"remote": self.remote}


@dataclass(frozen=True)
class RepoBinding:
    path: str
    include: tuple[str, ...]
    vendor: tuple[str, ...]

    @classmethod
    def from_raw(cls, repo_id: str, raw: object) -> RepoBinding:
        if not isinstance(raw, dict):
            raise FleetConfigError(f"host repo {repo_id} must be a TOML table")
        reject_unknown_keys(
            raw,
            {"path", "include", "vendor"},
            f"host repo {repo_id}",
        )
        include = string_list(raw.get("include", []), f"host repo {repo_id} include")
        vendor = string_list(raw.get("vendor", []), f"host repo {repo_id} vendor")
        if set(include) & set(vendor):
            raise FleetConfigError(
                f"host repo {repo_id} include and vendor must be disjoint"
            )
        return cls(
            path=absolute_path(raw.get("path", ""), f"host repo {repo_id} path"),
            include=tuple(sorted(include)),
            vendor=tuple(sorted(vendor)),
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "include": list(self.include),
            "vendor": list(self.vendor),
        }


@dataclass(frozen=True)
class HostTarget:
    host_id: str
    enrollment_id: str
    hostname: str
    username: str
    transport: str
    endpoint: str | None
    profile: str
    runtime: str
    global_registry: str
    source_bindings: dict[str, HostSourceBinding]
    repo_bindings: dict[str, RepoBinding]

    @staticmethod
    def parse(
        raw_host_id: object,
        raw: object,
        *,
        source_ids: set[str],
        repo_ids: set[str],
        source_bindings_key: str = "sources",
        repo_bindings_key: str = "repos",
    ) -> HostTarget:
        host_id = logical_id(raw_host_id, "host_id")
        if not isinstance(raw, dict):
            raise FleetConfigError(f"host {host_id} must be a TOML table")
        transport = raw.get("transport")
        if type(transport) is not str:
            raise FleetConfigError(f"host {host_id} transport must be local or ssh")
        if transport not in {"local", "ssh"}:
            raise FleetConfigError(f"host {host_id} transport must be local or ssh")
        endpoint = raw.get("endpoint")
        if transport == "ssh" and (type(endpoint) is not str or not endpoint):
            raise FleetConfigError(f"host {host_id} ssh transport requires endpoint")
        if transport == "local" and endpoint is not None:
            raise FleetConfigError(
                f"host {host_id} local transport must not set endpoint"
            )
        raw_source_bindings = require_table(raw, source_bindings_key)
        normalized_source_ids = {
            logical_id(source_id, "source_id") for source_id in raw_source_bindings
        }
        unknown_sources = sorted(normalized_source_ids - source_ids)
        if unknown_sources:
            raise FleetConfigError(
                f"host binds unknown source_id: {unknown_sources[0]}"
            )
        source_bindings = {
            logical_id(source_id, "source_id"): HostSourceBinding.from_raw(
                logical_id(source_id, "source_id"),
                binding,
            )
            for source_id, binding in raw_source_bindings.items()
        }
        raw_repo_bindings = require_table(raw, repo_bindings_key)
        normalized_repo_ids = {
            logical_id(repo_id, "repo_id") for repo_id in raw_repo_bindings
        }
        unknown_repos = sorted(normalized_repo_ids - repo_ids)
        if unknown_repos:
            raise FleetConfigError(f"host binds unknown repo_id: {unknown_repos[0]}")
        repo_bindings = {
            logical_id(repo_id, "repo_id"): RepoBinding.from_raw(
                logical_id(repo_id, "repo_id"),
                binding,
            )
            for repo_id, binding in raw_repo_bindings.items()
        }
        repo_paths = [binding.path for binding in repo_bindings.values()]
        if len(set(repo_paths)) != len(repo_paths):
            duplicate = next(
                path
                for path in repo_paths
                if repo_paths.count(path) > 1
            )
            raise FleetConfigError(
                f"host repo bindings must use unique paths: {duplicate}"
            )
        return HostTarget(
            host_id=host_id,
            enrollment_id=canonical_enrollment_id(
                raw.get("enrollment_id", ""),
                f"host {host_id} enrollment_id",
            ),
            hostname=logical_id(raw.get("hostname", ""), f"host {host_id} hostname"),
            username=logical_id(raw.get("username", ""), f"host {host_id} username"),
            transport=transport,
            endpoint=endpoint if isinstance(endpoint, str) else None,
            profile=absolute_path(raw.get("profile", ""), f"host {host_id} profile"),
            runtime=absolute_path(raw.get("runtime", ""), f"host {host_id} runtime"),
            global_registry=absolute_path(
                raw.get("global_registry", ""),
                f"host {host_id} global_registry",
            ),
            source_bindings=source_bindings,
            repo_bindings=repo_bindings,
        )


@dataclass(frozen=True)
class HostBinding(HostTarget):
    global_add: tuple[str, ...]
    global_remove: tuple[str, ...]

    @classmethod
    def from_raw(
        cls,
        raw_host_id: object,
        raw: object,
        *,
        source_ids: set[str],
        repo_ids: set[str],
        baseline: set[str],
    ) -> HostBinding:
        host_id = logical_id(raw_host_id, "host_id")
        if not isinstance(raw, dict):
            raise FleetConfigError(f"host {host_id} must be a TOML table")
        reject_unknown_keys(
            raw,
            {
                "enrollment_id",
                "hostname",
                "username",
                "transport",
                "endpoint",
                "profile",
                "runtime",
                "global_registry",
                "global_add",
                "global_remove",
                "sources",
                "repos",
            },
            f"host {host_id}",
        )
        target = HostTarget.parse(
            host_id,
            raw,
            source_ids=source_ids,
            repo_ids=repo_ids,
        )
        additions = set(
            string_list(raw.get("global_add", []), f"host {host_id} global_add")
        )
        removals = set(
            string_list(raw.get("global_remove", []), f"host {host_id} global_remove")
        )
        if additions & removals:
            raise FleetConfigError("host global_add and global_remove must be disjoint")
        invalid_removals = sorted(removals - baseline)
        if invalid_removals:
            raise FleetConfigError(
                "host global_remove aliases must exist in global.include: "
                + ", ".join(invalid_removals)
            )
        return cls(
            host_id=target.host_id,
            enrollment_id=target.enrollment_id,
            hostname=target.hostname,
            username=target.username,
            transport=target.transport,
            endpoint=target.endpoint,
            profile=target.profile,
            runtime=target.runtime,
            global_registry=target.global_registry,
            source_bindings=target.source_bindings,
            repo_bindings=target.repo_bindings,
            global_add=tuple(sorted(additions)),
            global_remove=tuple(sorted(removals)),
        )

    def desired_global(self, baseline: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(
            sorted((set(baseline) | set(self.global_add)) - set(self.global_remove))
        )

    def as_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "enrollment_id": self.enrollment_id,
            "hostname": self.hostname,
            "username": self.username,
            "transport": self.transport,
            "profile": self.profile,
            "runtime": self.runtime,
            "global_registry": self.global_registry,
            "global_add": list(self.global_add),
            "global_remove": list(self.global_remove),
            "sources": {
                source_id: binding.as_dict()
                for source_id, binding in sorted(self.source_bindings.items())
            },
            "repos": {
                repo_id: binding.as_dict()
                for repo_id, binding in sorted(self.repo_bindings.items())
            },
        }
        if self.endpoint is not None:
            result["endpoint"] = self.endpoint
        return result


@dataclass(frozen=True)
class FleetManifest:
    global_include: tuple[str, ...]
    sources: dict[str, SourceSpec]
    repos: dict[str, RepoSpec]
    hosts: dict[str, HostBinding]

    @classmethod
    def load(cls, path: Path | str) -> FleetManifest:
        manifest_path = Path(path).expanduser()
        if not manifest_path.is_file():
            raise FleetConfigError(f"fleet manifest not found: {manifest_path}")
        with manifest_path.open("rb") as handle:
            return cls.from_raw(tomllib.load(handle))

    @classmethod
    def from_raw(cls, raw: object) -> FleetManifest:
        if not isinstance(raw, dict):
            raise FleetConfigError("fleet manifest must be a TOML table")
        reject_unknown_keys(
            raw,
            {"schema_version", "global", "sources", "repos", "hosts"},
            "fleet manifest",
        )
        if raw.get("schema_version") != FLEET_SCHEMA_VERSION:
            raise FleetConfigError(
                f"fleet manifest schema_version must be {FLEET_SCHEMA_VERSION}"
            )
        global_table = require_table(raw, "global")
        reject_unknown_keys(global_table, {"include"}, "global")
        baseline = tuple(
            sorted(string_list(global_table.get("include", []), "global.include"))
        )
        sources = {
            logical_id(source_id, "source_id"): SourceSpec.from_raw(
                source_id,
                source,
            )
            for source_id, source in require_table(raw, "sources").items()
        }
        repos = {
            logical_id(repo_id, "repo_id"): RepoSpec.from_raw(repo_id, repo)
            for repo_id, repo in require_table(raw, "repos").items()
        }
        hosts = {
            logical_id(host_id, "host_id"): HostBinding.from_raw(
                host_id,
                host,
                source_ids=set(sources),
                repo_ids=set(repos),
                baseline=set(baseline),
            )
            for host_id, host in require_table(raw, "hosts").items()
        }
        manifest = cls(
            global_include=baseline,
            sources=sources,
            repos=repos,
            hosts=hosts,
        )
        enrollment_ids = [host.enrollment_id for host in hosts.values()]
        if len(enrollment_ids) != len(set(enrollment_ids)):
            raise FleetConfigError("hosts contain duplicate enrollment_id")
        selectors = [(host.hostname, host.username) for host in hosts.values()]
        if len(selectors) != len(set(selectors)):
            raise FleetConfigError("hosts contain ambiguous hostname and username")
        return manifest

    def with_catalogs(
        self,
        catalogs: dict[str, dict[str, SourceSkill]],
    ) -> FleetManifest:
        if set(catalogs) != set(self.sources):
            raise FleetConfigError("source catalogs must exactly match declared sources")
        sources = {
            source_id: replace(source, skills=dict(sorted(catalogs[source_id].items())))
            for source_id, source in self.sources.items()
        }
        manifest = replace(self, sources=sources)
        manifest._validate_host_desired_state(index_source_skills(sources))
        return manifest

    def _validate_host_desired_state(self, alias_owners: dict[str, str]) -> None:
        for host in self.hosts.values():
            desired_aliases = set(host.desired_global(self.global_include))
            for binding in host.repo_bindings.values():
                desired_aliases.update(binding.include)
                desired_aliases.update(binding.vendor)
            unknown_aliases = sorted(desired_aliases - set(alias_owners))
            if unknown_aliases:
                raise FleetConfigError(
                    f"desired alias has no declared source: {unknown_aliases[0]}"
                )
            for alias in sorted(desired_aliases):
                source_id = alias_owners[alias]
                if source_id not in host.source_bindings:
                    raise FleetConfigError(
                        f"host {host.host_id} has no binding for source {source_id}"
                    )

    @property
    def digest(self) -> str:
        return canonical_digest(self.as_dict())

    @property
    def alias_owners(self) -> dict[str, str]:
        return {
            alias: source_id
            for source_id, source in self.sources.items()
            for alias in source.skills
        }

    def host(self, host_id: str) -> HostBinding:
        normalized = logical_id(host_id, "host_id")
        try:
            return self.hosts[normalized]
        except KeyError as exc:
            raise FleetConfigError(f"unknown host_id: {normalized}") from exc

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": FLEET_SCHEMA_VERSION,
            "global": {"include": list(self.global_include)},
            "sources": {
                source_id: source.as_dict()
                for source_id, source in sorted(self.sources.items())
            },
            "repos": {
                repo_id: repo.as_dict() for repo_id, repo in sorted(self.repos.items())
            },
            "hosts": {
                host_id: host.as_dict() for host_id, host in sorted(self.hosts.items())
            },
        }

    def to_toml(self) -> str:
        lines = [f"schema_version = {FLEET_SCHEMA_VERSION}", ""]
        lines.extend(
            [
                "[global]",
                f"include = {_toml_array(self.global_include)}",
                "",
            ]
        )

        for source_id, source in sorted(self.sources.items()):
            lines.extend(
                [
                    f"[sources.{_toml_quote(source_id)}]",
                    'kind = "git"',
                    f"origin = {_toml_quote(source.origin)}",
                    f"revision = {_toml_quote(source.revision)}",
                    "",
                ]
            )
        for repo_id, repo in sorted(self.repos.items()):
            lines.extend(
                [
                    f"[repos.{_toml_quote(repo_id)}]",
                    f"remote = {_toml_quote(repo.remote)}",
                    "",
                ]
            )

        for host_id, host in sorted(self.hosts.items()):
            lines.extend(
                [
                    f"[hosts.{_toml_quote(host_id)}]",
                    f"enrollment_id = {_toml_quote(host.enrollment_id)}",
                    f"hostname = {_toml_quote(host.hostname)}",
                    f"username = {_toml_quote(host.username)}",
                    f"transport = {_toml_quote(host.transport)}",
                ]
            )
            if host.endpoint is not None:
                lines.append(f"endpoint = {_toml_quote(host.endpoint)}")
            lines.extend(
                [
                    f"profile = {_toml_quote(host.profile)}",
                    f"runtime = {_toml_quote(host.runtime)}",
                    f"global_registry = {_toml_quote(host.global_registry)}",
                    f"global_add = {_toml_array(host.global_add)}",
                    f"global_remove = {_toml_array(host.global_remove)}",
                    "",
                ]
            )
            for source_id, source_binding in sorted(host.source_bindings.items()):
                lines.extend(
                    [
                        f"[hosts.{_toml_quote(host_id)}.sources.{_toml_quote(source_id)}]",
                        f"path = {_toml_quote(source_binding.path)}",
                    ]
                )
                if source_binding.discovery_path is not None:
                    lines.append(
                        f"discovery_path = {_toml_quote(source_binding.discovery_path)}"
                    )
                if source_binding.fetch_url is not None:
                    lines.append(
                        f"fetch_url = {_toml_quote(source_binding.fetch_url)}"
                    )
                lines.append("")
            for repo_id, repo_binding in sorted(host.repo_bindings.items()):
                lines.extend(
                    [
                        f"[hosts.{_toml_quote(host_id)}.repos.{_toml_quote(repo_id)}]",
                        f"path = {_toml_quote(repo_binding.path)}",
                        f"include = {_toml_array(repo_binding.include)}",
                        f"vendor = {_toml_array(repo_binding.vendor)}",
                        "",
                    ]
                )

        return "\n".join(lines).rstrip() + "\n"


__all__ = [
    "FLEET_SCHEMA_VERSION",
    "GIT_OBJECT_ID_PATTERN",
    "SHA256_DIGEST_PATTERN",
    "canonical_enrollment_id",
    "FleetConfigError",
    "FleetManifest",
    "HostBinding",
    "HostSourceBinding",
    "HostTarget",
    "RepoBinding",
    "RepoSpec",
    "SourceSkill",
    "SourceSpec",
    "absolute_path",
    "canonical_digest",
    "canonical_git_identity",
    "index_source_skills",
    "logical_id",
    "reject_unknown_keys",
    "relative_path",
    "require_table",
    "string_list",
]
