# Contributing

Open an Issue before a change that alters a Skill contract, public API, or
repository structure. A focused correction can start as a pull request.

The public repository is a release projection. A maintainer applies an
accepted contribution to the canonical development source, preserves its
authorship, and publishes it in a later release. Public pull requests are not
merged directly into the release branch.

Keep a change reusable across projects. Do not add local paths, host inventory,
session history, credentials, private deployment state, or copied upstream
documentation.

Before submitting a change:

1. Read the changed Skill or package and its closest README.
2. Run the gates selected by [`docs/develop/gates.md`](docs/develop/gates.md).
3. Update `agents/openai.yaml` when invocation policy or UI metadata changes.
4. Confirm that the change does not add generated or local-only files.

Contributions are submitted under the [Apache License 2.0](LICENSE).
