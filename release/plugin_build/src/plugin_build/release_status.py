from __future__ import annotations

import hashlib
import json
import os
import subprocess
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
    source_merged: bool
    plugin_release: bool
    package_verified: bool
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
    declared_version: str | None = None,
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
    verified = distribution_passed and activation_status == "passed"
    if built_version is None:
        return _status(
            "source_merged" if source_merged else "",
            source_merged,
            False,
            source_commit,
            declared_version,
            repository_release,
            None,
            bounded_surface,
        )
    if built_commit != source_commit:
        raise ReleaseError("identity_mismatch", "package commit does not match the source commit")
    if bounded_surface == "public":
        raise ReleaseError("surface_mismatch", "workspace publication is not public")
    if approval is not None and _notes_match(release_notes, built_version) and verified:
        _require_record(approval, built_version, built_commit, built_zip_sha256, "directory-review")
        if publication is not None:
            _require_record(publication, built_version, built_commit, built_zip_sha256, "public")
            return _status(
                "public_published",
                source_merged,
                True,
                source_commit,
                built_version,
                repository_release,
                built_zip_sha256,
                "public",
            )
        return _status(
            "public_approved",
            source_merged,
            True,
            source_commit,
            built_version,
            repository_release,
            built_zip_sha256,
            "directory-review",
        )
    if bounded_surface and verified:
        return _status(
            "bounded_distribution",
            source_merged,
            True,
            source_commit,
            built_version,
            repository_release,
            built_zip_sha256,
            bounded_surface,
        )
    state = "package_verified" if verified else "package_built"
    return _status(
        state,
        source_merged,
        verified,
        source_commit,
        built_version,
        repository_release,
        built_zip_sha256,
        bounded_surface,
    )


def current_publication(repository: Path) -> PublicationStatus:
    repository = repository.resolve()
    metadata = _read_json(repository / "release" / "plugins" / "engineering" / "source.json")
    version = str(metadata["version"])
    commit = _head(repository)
    marketplace = read_openai_marketplace(repository)
    configured_surface = str(marketplace["plugins"][0]["source"]["path"])
    built_commit, built_version, digest = _built_package(repository, commit, version)
    notes_path = repository / "release" / "plugins" / "engineering" / "release-notes.md"
    notes = notes_path.read_text(encoding="utf-8") if notes_path.is_file() else None
    return publication_status(
        source_merged=_source_merged(repository, commit),
        source_commit=commit,
        repository_release=_repository_release(repository),
        declared_version=version,
        built_version=built_version,
        built_commit=built_commit,
        built_zip_sha256=digest,
        distribution_passed=False,
        activation_status="unavailable",
        bounded_surface=configured_surface,
        release_notes=notes,
        approval=None,
        publication=None,
        prior_publication=None,
    )


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


def main() -> int:
    report = current_publication(Path.cwd())
    print(f"state={report.state}")
    print(f"source_merged={str(report.source_merged).lower()}")
    print(f"plugin_release={str(report.plugin_release).lower()}")
    print(f"package_verified={str(report.package_verified).lower()}")
    print(f"source_commit={report.source_commit}")
    print(f"package_version={report.package_version or ''}")
    print(f"repository_release={report.repository_release}")
    print(f"zip_sha256={report.zip_sha256 or ''}")
    print(f"surface={report.surface or ''}")
    return 0


def _built_package(repository: Path, commit: str, version: str) -> tuple[str | None, str | None, str | None]:
    metadata = _read_json(repository / "release" / "plugins" / "engineering" / "source.json")
    name = str(metadata["name"])
    root = repository / "dist" / "plugins" / name
    provenance_path = root / "assets" / "provenance.json"
    zip_path = repository / "dist" / "plugins" / f"{name}-{version}.zip"
    if not provenance_path.is_file() or not zip_path.is_file():
        return None, None, None
    provenance = _read_json(provenance_path)
    if provenance.get("source_commit") != commit or provenance.get("version") != version:
        return None, None, None
    digest = hashlib.sha256(zip_path.read_bytes()).hexdigest()
    return commit, version, digest


def _repository_release(repository: Path) -> str:
    changelog = repository / "CHANGELOG.md"
    if not changelog.is_file():
        return "unreleased"
    for line in changelog.read_text(encoding="utf-8").splitlines():
        if line.startswith("## ") and not line.startswith("## Unreleased"):
            return line.removeprefix("## ").split(" ", 1)[0]
    return "unreleased"


def _source_merged(repository: Path, commit: str) -> bool:
    if os.environ.get("GITHUB_REF") == "refs/heads/main":
        return True
    result = subprocess.run(
        ["git", "-C", str(repository), "merge-base", "--is-ancestor", commit, "main"],
        capture_output=True,
        check=False,
    )
    return result.returncode == 0


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
    source_merged: bool,
    package_verified: bool,
    source_commit: str,
    package_version: str | None,
    repository_release: str,
    zip_sha256: str | None,
    surface: str | None,
) -> PublicationStatus:
    return PublicationStatus(
        state=state,
        source_merged=source_merged,
        plugin_release=state == "public_published",
        package_verified=package_verified,
        source_commit=source_commit,
        package_version=package_version,
        repository_release=repository_release,
        zip_sha256=zip_sha256,
        surface=surface,
    )


def _read_json(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ReleaseError("identity_mismatch", path.name)
    return data


def _head(repository: Path) -> str:
    result = subprocess.run(
        ["git", "-C", str(repository), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
    )
    return result.stdout.decode().strip()


if __name__ == "__main__":
    raise SystemExit(main())
