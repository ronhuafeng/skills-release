# Agent Skills

Reusable Agent Skills and deterministic harnesses for engineering, skill
management, and Codex session work.

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
- [`harnesses/`](harnesses/) contains reusable mechanical APIs used by Skills.
- [`docs/`](docs/) contains current architecture and verification decisions.

The catalog and each Skill's metadata are the inventory. This README does not
maintain a second Skill list.

## Install

Use the standard Skills installer. Global Codex installation writes to the
shared `~/.agents/skills` registry.

```sh
npx skills@latest add ronhuafeng/skills-release -g --agent codex
```

The installer lets you select Skills. To install one Skill directly:

```sh
npx skills@latest add ronhuafeng/skills-release \
  -g --agent codex --skill context-reduce
```

Use [`skill-manager`](catalog/codex-skills/skill-manager/) only when placement
needs ownership, provenance, or multi-host reconciliation.

## Invocation

A manual-only Skill runs only when the user names it. It sets
`disable-model-invocation: true` for compatible clients and
`policy.allow_implicit_invocation: false` in `agents/openai.yaml` for Codex.

A model-reachable Skill omits those restrictions. Its description states the
conditions in which the model should select it. `agents/openai.yaml` also owns
Codex display metadata.

## Validate changes

Use [`docs/develop/gates.md`](docs/develop/gates.md) to select the required
gate. Exact Python and Go commands live in the closest package README. Public
CI runs the complete repository test set and verifies the public export from a
clean checkout.

## Releases

Public `main` contains the current synchronized snapshot. `SOURCE_REVISION`
identifies its exact source commit. Formal releases add repository-level
semantic version tags to verified public commits. The public repository has
independent history and never inherits the private development history.
See [`release/README.md`](release/README.md).

## Contributing and security

See [`CONTRIBUTING.md`](CONTRIBUTING.md) for the contribution path and
[`SECURITY.md`](SECURITY.md) for private vulnerability reporting.

## License

Original repository content is licensed under the
[Apache License 2.0](LICENSE). Bundled third-party artifacts retain their own
terms; see [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md).
