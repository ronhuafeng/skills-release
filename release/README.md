# Release

Develop and review changes in the public repository. Merging to `main` makes
the committed engineering Plugin source available to the GitHub marketplace;
each consumer still installs and enables it in a supported client. The root
README also documents standalone Skills installation.
There is no export, mirror, or private-source synchronization step.

The Codex and Claude manifests expose the engineering catalog through the same
source revision. Shared identity fields must match. Do not require the whole
manifests to be byte-equal when client-specific fields diverge. Validate the
Claude entrypoints separately:

```sh
claude plugin validate .claude-plugin/plugin.json --strict
claude plugin validate .claude-plugin/marketplace.json --strict
```

Use Codex's native plugin read to check that its discovered Skills match
`catalog/engineering`. Separately validate `agents/openai.yaml` policies,
Skill identity, client metadata, and bundled resources. Plugin discovery alone
does not report implicit-invocation policy. Check that Claude's
`disable-model-invocation` agrees with the Codex implicit-invocation policy;
do not remove client-specific fields to pass
a Codex-only frontmatter allowlist. A valid manifest alone does not prove
complete discovery or invocation policy. Keep canonical Skill content in the
existing catalog. The optional portable engineering Plugin is generated under
ignored `dist/`; it is not a second Skill source.

## GitHub engineering Plugin marketplace

The committed `.agents/plugins/marketplace.json` points to the public Git
repository root at `main`. Its `.codex-plugin/plugin.json` loads
`catalog/engineering/` directly. From a clean checkout, run
`uv run --locked --project harnesses pytest release/plugin_build/tests/test_marketplace.py`
to verify the marketplace source, Plugin identity, and tracked Skill inventory
without generating `dist/`. A passing contract is source evidence only. In a
supported client, add the marketplace, install/enable the Plugin, and verify
Skill discovery and activation separately. The repository's CI does not claim
live installation or activation.


## Portable engineering Plugin

`release/plugins/engineering/source.json` is the package source metadata.
`catalog/engineering/` remains the canonical Skill source. Build an ignored
package for the current commit:

```sh
PYTHONPATH=release/plugin_build/src \
  uv run --locked --project harnesses python -m plugin_build
```

The build writes `dist/plugins/ronhuafeng-engineering/` and
`dist/plugins/ronhuafeng-engineering-<version>.zip`. Do not commit `dist/`.
The build checks shared identity fields against the Codex and Claude
compatibility manifests. It does not require those whole files to equal the
portable manifest. It does not publish the Plugin.

`verify` keeps separate jobs. **Plugin distribution contracts** checks the
committed marketplace source without building a package. **Plugin activation
evaluation** checks the labelled
golden prompts and reports live activation as unavailable when this repository
has no supported Plugin surface. A green distribution job does not mean a
Skill was selected. **Plugin release ladder** tests the optional portable
builder and reports ZIP publication state. It does not publish the Plugin.

## Plugin publication states

The Plugin version is the shared `version` in
`release/plugins/engineering/source.json` and the two compatibility manifests.
It is not the repository tag in `CHANGELOG.md`. A repository release is not a
Plugin release.

Answer these from evidence for one package. Do not infer a later state from an
earlier one:

| State | Evidence |
|-------|----------|
| `source_merged` | The canonical commit is on `main`. No package is required. |
| `package_built` | The ZIP and provenance name that commit and the Plugin version. |
| `package_verified` | Portable package contracts passed and live activation passed for that ZIP. Unavailable activation does not verify the package. |
| `bounded_distribution` | The verified package is available through an explicitly configured bounded package surface. GitHub repository marketplace availability is separate from this ZIP state. |
| `public_approved` | An operator reviewed the package, behavior evidence, `release/plugins/engineering/release-notes.md`, and `release/plugins/engineering/activation/golden-prompts.json`. |
| `public_published` | The operator published that approved ZIP in the universal Plugins Directory. |

The GitHub repository marketplace points to the committed Plugin root and does
not copy `catalog/engineering/`. The Claude marketplace remains a separate
client surface. Do not store publisher credentials in Git, GitHub, or the ZIP.

A versioned Plugin release attaches that exact ZIP to the release record.
Record the source commit, Plugin version, ZIP sha256, surface, and state.
A new Skill or metadata change needs a new version and a new ZIP. Do not
replace a published ZIP. Roll forward with a new version. Do not publish to
the universal directory on merge.

For a versioned repository release:

1. Update `CHANGELOG.md` with user-visible changes and merge the change.
2. Require `verify` to pass for the exact public commit being released.
3. List and install from the public URL with a recorded Skills CLI version.
   For runtime changes, verify the installed executable outside the checkout.
4. Tag that public commit and publish the GitHub Release:

```sh
git tag -a <version> <verified-commit> -m "Agent Skills <version>"
git push origin refs/tags/<version>
gh release create <version> --repo ronhuafeng/skills-release \
  --verify-tag --title "Agent Skills <version>" --notes-file <release-notes>
```

Read back the remote tag target and release metadata. Keep published tags
immutable; correct a release with a new version. Publication does not install
Skills, plugins, or runtimes on any user's machine.
