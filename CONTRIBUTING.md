# Contributing

Open an Issue before a change that alters a Skill contract, public API, or
repository structure. A focused correction can start as a pull request.

Develop against this public repository. Submit focused pull requests to `main`.
A maintainer reviews the scope and validation evidence before merging. No
private repository or separate synchronization step is required.

Keep changes reusable across projects and do not mirror upstream documentation.
The [repository boundary](AGENTS.md#repository-boundary) names the single
exception: the Grok process itself is maintained here, not mirrored.
Do not add local paths, host inventory, session history, credentials or
private deployment state.

Before submitting a change:

1. Read the changed Skill or package and its closest README.
2. Run the gates selected by [`docs/develop/gates.md`](docs/develop/gates.md).
3. Update `agents/openai.yaml` when invocation policy or UI metadata changes.
4. Confirm that the change does not add generated or local-only files.

Contributions are submitted under the [Apache License 2.0](LICENSE).
