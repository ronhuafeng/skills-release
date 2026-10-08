# Release

Develop and review changes in the public repository. Merging to `main` makes
the current Skills available through the install command in the root README.
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
complete discovery or invocation policy. Keep canonical Skill content in the existing catalog. The portable
engineering Plugin is a generated package under ignored `dist/`; it is not a
second Skill source.


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

`verify` keeps separate jobs. **Plugin distribution contracts** proves the
package structure only. **Plugin activation evaluation** checks the labelled
golden prompts and reports live activation as unavailable when this repository
has no supported Plugin surface. A green distribution job does not mean a
Skill was selected. **Plugin release ladder** reports the publication state.
It does not publish the Plugin.

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
| `package_verified` | Distribution contracts passed and live activation passed for that ZIP. Unavailable activation does not verify the package. |
| `bounded_distribution` | A workspace or the repo marketplace at `.agents/plugins/marketplace.json` points at `./dist/plugins/ronhuafeng-engineering`. This is not public. |
| `public_approved` | An operator reviewed the package, behavior evidence, `release/plugins/engineering/release-notes.md`, and `release/plugins/engineering/activation/golden-prompts.json`. |
| `public_published` | The operator published that approved ZIP in the universal Plugins Directory. |

The marketplace points at the built package. It does not copy
`catalog/engineering/`. The Claude marketplace remains a separate client
surface. Do not store publisher credentials in Git, GitHub, or the ZIP.

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
