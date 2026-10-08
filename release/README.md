# Release

Develop and review changes in the public repository. Merging to `main` makes
the current Skills available through the install command in the root README.
There is no export, mirror, or private-source synchronization step.

The Codex and Claude manifests expose the engineering catalog through the same
source revision. Check their parity and validate the Claude entrypoints:

```sh
cmp .codex-plugin/plugin.json .claude-plugin/plugin.json
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

For a versioned release:

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
