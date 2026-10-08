from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


class ReleaseError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class ReleaseRecord:
    version: str
    source_commit: str
    zip_sha256: str
    surface: str


@dataclass(frozen=True)
class PublicationStatus:
    state: str
    plugin_release: bool
    source_commit: str
    package_version: str | None
    repository_release: str
    zip_sha256: str | None
    surface: str | None


def publication_status(
    *,
    source_merged: bool,
    source_commit: str,
    repository_release: str,
    built_version: str | None,
    built_commit: str | None,
    built_zip_sha256: str | None,
    distribution_passed: bool,
    activation_status: str,
    bounded_surface: str | None,
    release_notes: str | None,
    approval: ReleaseRecord | None,
    publication: ReleaseRecord | None,
    prior_publication: ReleaseRecord | None,
) -> PublicationStatus:
    built = (built_version, built_commit, built_zip_sha256)
    if any(item is None for item in built) and any(item is not None for item in built):
        raise ReleaseError("identity_mismatch", "package evidence is incomplete")
    if built_version is not None and prior_publication is not None:
        same_version = prior_publication.version == built_version
        changed_artifact = (
            prior_publication.zip_sha256 != built_zip_sha256
            or prior_publication.source_commit != built_commit
        )
        if same_version and changed_artifact:
            raise ReleaseError("immutable_artifact", "a published version cannot be replaced")
    if not source_merged:
        return _status("none", source_commit, None, repository_release, None, None)
    if built_version is None:
        return _status("source_merged", source_commit, None, repository_release, None, None)
    if built_commit != source_commit:
        raise ReleaseError("identity_mismatch", "package commit does not match the source commit")
    if bounded_surface == "public":
        raise ReleaseError("surface_mismatch", "workspace publication is not public")
    if not distribution_passed or activation_status != "passed":
        return _status("package_built", source_commit, built_version, repository_release, built_zip_sha256, None)
    if not bounded_surface:
        return _status("package_verified", source_commit, built_version, repository_release, built_zip_sha256, None)
    if approval is None or not _notes_match(release_notes, built_version):
        return _status(
            "bounded_distribution",
            source_commit,
            built_version,
            repository_release,
            built_zip_sha256,
            bounded_surface,
        )
    _require_record(approval, built_version, built_commit, built_zip_sha256, "directory-review")
    if publication is None:
        return _status(
            "public_approved",
            source_commit,
            built_version,
            repository_release,
            built_zip_sha256,
            "directory-review",
        )
    _require_record(publication, built_version, built_commit, built_zip_sha256, "public")
    return _status("public_published", source_commit, built_version, repository_release, built_zip_sha256, "public")


def read_openai_marketplace(repository: Path) -> dict:
    path = repository / ".agents" / "plugins" / "marketplace.json"
    if not path.is_file():
        raise ReleaseError("missing_file", "OpenAI marketplace is missing")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ReleaseError("surface_mismatch", "OpenAI marketplace is invalid")
    plugins = data.get("plugins")
    if not isinstance(plugins, list) or len(plugins) != 1 or not isinstance(plugins[0], dict):
        raise ReleaseError("surface_mismatch", "OpenAI marketplace must name one local package")
    source = plugins[0].get("source")
    if not isinstance(source, dict):
        raise ReleaseError("surface_mismatch", "OpenAI marketplace source is missing")
    plugin_path = source.get("path")
    if source.get("source") != "local" or not isinstance(plugin_path, str):
        raise ReleaseError("surface_mismatch", "OpenAI marketplace must use a local path")
    if not plugin_path.startswith("./dist/plugins/") or "catalog/engineering" in plugin_path:
        raise ReleaseError("surface_mismatch", "OpenAI marketplace must point at the built package")
    return data


def _notes_match(release_notes: str | None, version: str) -> bool:
    return isinstance(release_notes, str) and version in release_notes


def _require_record(
    record: ReleaseRecord,
    version: str,
    commit: str,
    digest: str,
    surface: str,
) -> None:
    if (
        record.version != version
        or record.source_commit != commit
        or record.zip_sha256 != digest
        or record.surface != surface
    ):
        raise ReleaseError("identity_mismatch", "release record does not match the package")


def _status(
    state: str,
    source_commit: str,
    package_version: str | None,
    repository_release: str,
    zip_sha256: str | None,
    surface: str | None,
) -> PublicationStatus:
    return PublicationStatus(
        state=state,
        plugin_release=state == "public_published",
        source_commit=source_commit,
        package_version=package_version,
        repository_release=repository_release,
        zip_sha256=zip_sha256,
        surface=surface,
    )
