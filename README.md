# Agent Skills

Reusable Agent Skills for engineering, skill management, and Codex session work.

Users can use the Skills without the maintainer's private environment.
Contributors can change and verify one capability without learning the whole
repository. This public repository owns development, verification, and releases.

The Skills favor user-visible outcomes, one clear authority, short execution
paths, honest failure, and evidence that matches the claim. They add tooling
only when a stable mechanical boundary protects those properties.

## Start with the job

This map explains how the main Skills relate. It is not a second catalog.

| Job | Skill |
|-----|-------|
| Plan an ordered delivery path | [`plan-issue-roadmap`](catalog/engineering/plan-issue-roadmap/) |
| Implement an accepted ticket queue | [`implement-tickets`](catalog/engineering/implement-tickets/) |
| Reduce unnecessary engineering context | [`context-reduce`](catalog/engineering/context-reduce/) |
| Remove replaced implementation paths | [`prune-legacy`](catalog/engineering/prune-legacy/) |
| Define and audit live evidence | [`live-story-review`](catalog/engineering/live-story-review/) and [`live-gate-review`](catalog/engineering/live-gate-review/) |
| Check stateful and concurrent designs | [`model-with-tla`](catalog/engineering/model-with-tla/) |
| Manage Skill placement | [`skill-manager`](catalog/codex-skills/skill-manager/) |
| Manage Codex sessions | [`session-management`](catalog/codex-sessions/session-management/) |

## Repository layout

- [`catalog/`](catalog/) contains the published Skills. Each Skill owns its
  `SKILL.md`, optional client metadata, and only the references or executables
  required by its contract.
- [`agents/recruit.md`](agents/recruit.md) is an explicitly loaded meta-agent
  contract for proposing specialist roles from retrospective evidence.
  `agents/` prompts are not installed Skills or automatically activated agents.
- [`harnesses/`](harnesses/) contains reusable mechanical APIs used by Skills.
- [`docs/`](docs/) contains current architecture and verification decisions.

The catalog and each Skill's metadata are the inventory. This README does not
maintain a second Skill list.

## Install

### Engineering plugin

The public GitHub repository marketplace is the engineering Plugin's default
distribution channel. Add it in a supported Codex client:

```sh
codex plugin marketplace add ronhuafeng/skills-release --ref main
codex plugin marketplace list
```

In Codex CLI, start `codex`, open `/plugins`, find
`ronhuafeng-engineering` in `ronhuafeng-skills`, and select **Install plugin**.
Start a new Codex CLI session and confirm the installed Plugin and Skills.
The marketplace CLI commands above register and inspect the source; they do
not themselves prove that the Plugin is installed or active.
The committed [marketplace entry](.agents/plugins/marketplace.json) points to
the repository root. No `dist/` build or ZIP is needed.

The repository root is the `ronhuafeng-engineering` Plugin. Its
[Codex manifest](.codex-plugin/plugin.json) and
[Claude manifest](.claude-plugin/plugin.json) both expose only
`catalog/engineering`. Keep their identity, version, and Skill path equal;
the existing Skill directories remain the single content source.

For Claude Code, add the source marketplace and install the same plugin:

```text
/plugin marketplace add ronhuafeng/skills-release
/plugin install ronhuafeng-engineering@ronhuafeng-skills
```

The consuming repository owns project enablement and may pin an accepted Git
commit with `source.sha`. A Git reference is not an installed plugin: each host
must install or refresh it through its client, then verify discovery in a new
session. The plugin adds no MCP server, hook, or authentication requirement.
It does not include `skill-manager` or `session-management`.

Plugin installation does not install system tools or external Skills.
`implement-tickets` still needs Matt's `implement`, `tdd`, and `code-review`;
`model-with-tla` still needs uv and Java 11+. Existing Skill invocation policies
and bundled resources are unchanged.

### Standalone Skills compatibility

Use `npx skills` when installing individual standalone Skills, including
non-Plugin catalog entries. This path does not install the engineering Plugin.
Global Codex installation writes to the shared `~/.agents/skills` registry.

```sh
npx skills@latest add ronhuafeng/skills-release -g --agent codex
npx skills@latest add ronhuafeng/skills-release \
  -g --agent codex --skill context-reduce
```

Use [`skill-manager`](catalog/codex-skills/skill-manager/) when placement
needs ownership, provenance, or multi-host reconciliation.

### Runtime prerequisites

The installer copies Skill instructions and resources. It does not install
system tools or compile executables. Read the selected Skill's precheck before
use; some workflows also require external Skills or connected application tools.

| Skill | Additional requirement |
|-------|------------------------|
| `skill-manager` | The `skill-manager` executable; Git and an explicit profile or Fleet configuration |
| `session-management` | The `session-management` executable; Codex App tools for app-owned operations |
| `model-with-tla` | uv and Java 11+; the checker and TLA+ JAR ship inside the Skill |

Build a required executable from a full checkout, not from the copied Skill
directory. Shared source dependencies stay in this repository:

```sh
git clone https://github.com/ronhuafeng/skills-release.git
cd skills-release
./install-runtime skill-manager "$HOME/.local/bin"
# Only if using session-management:
./install-runtime session-management "$HOME/.local/bin"
```

Build `skill-manager` with uv (which obtains the pinned Python version), or
`session-management` with Go 1.23+. Put the chosen directory on your agent's
`PATH`. The executables do not need this checkout after installation. To update,
pull the accepted public revision and repeat the same install command.
Building requires network access for locked dependencies. Runtime builds target
the current machine; macOS Apple silicon and Linux x86-64 are the validation
targets. Other platforms are not claimed as verified.

## Invocation

A manual-only Skill runs only when the user names it. It sets
`policy.allow_implicit_invocation: false` in `agents/openai.yaml` for Codex.
Explicit `$skill` invocation remains available. Claude Code uses
`disable-model-invocation: true` in `SKILL.md`; `user-invocable: true` keeps
its manual command visible. Claude fields do not replace the Codex policy.

A model-reachable Skill sets the Codex policy to `true` or omits it (the default)
and omits the Claude model-invocation restriction or sets it to `false`.
Its description states when the model should select it. Plugin packaging
preserves each Skill's policy; marketplace installation and plugin enablement
do not define implicit invocation. `agents/openai.yaml` also owns Codex display
metadata. See the [Codex Skill metadata contract](https://developers.openai.com/codex/skills#optional-metadata).

## Validate changes

Use [`docs/develop/gates.md`](docs/develop/gates.md) to select the required
gate. Exact Python and Go commands live in the closest package README. CI checks
source behavior and installation separately.

## Releases

Public `main` is the development source. Formal releases add repository-level
semantic version tags to verified public commits.
See [`release/README.md`](release/README.md).

## Contributing and security

See [`CONTRIBUTING.md`](CONTRIBUTING.md) for the contribution path and
[`SECURITY.md`](SECURITY.md) for private vulnerability reporting.

## License

Original repository content is licensed under the
[Apache License 2.0](LICENSE). Bundled third-party artifacts retain their own
terms; see [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md).
