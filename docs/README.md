# Documentation map

This repository keeps the default agent path small. Route to one authority for
the question at hand; do not assemble current truth from every document.

## Authority map

| Question | Authority |
|----------|-----------|
| What terms mean | [CONTEXT-MAP.md](../CONTEXT-MAP.md) and the relevant `CONTEXT.md` |
| How domain terms and decisions are maintained | [agents/domain.md](./agents/domain.md) |
| Why a system boundary exists | [architecture/INDEX.md](./architecture/INDEX.md) and the relevant ADR |
| How a selected skill behaves | That skill's `SKILL.md`, command documents, and metadata |
| How a primitive or orchestration API behaves | Its source and closest package README |
| What validation a change requires | [develop/gates.md](./develop/gates.md) |
| Where work and PRDs are tracked | [agents/issue-tracker.md](./agents/issue-tracker.md) |
| How to publish a release | [release/README.md](../release/README.md) |
| What happened in a past Codex session | Private `codex_journal*`, when present in a development checkout and history is explicitly requested |

`catalog/` plus each skill's `SKILL.md` and optional `agents/openai.yaml` are
the catalog inventory. A hand-maintained catalog list elsewhere is not an
authority.

## Evidence classes

- **Normative:** canonical vocabulary from the relevant glossary, and behavior
  decisions from accepted ADRs, skill contracts, or API contracts. Change the
  owning source deliberately when behavior changes.
- **Verified fact:** established by source, configuration, focused tests, or a
  scoped live run. Record it next to the component that owns the fact and state
  the scope when it is not universal.
- **Working state:** issue content, `.tmp/` plans, private artifacts, and local
  wiring. Useful during execution, never current product truth.
- **Historical:** private development journals, when present, and superseded
  ADRs. They explain how the repository arrived here but must not reintroduce
  removed behavior.

If a verified fact conflicts with a normative document, report the conflict.
Do not silently turn an observation into a guarantee or edit metadata to make
two sources appear synchronized.

## Root entrypoints

| File | Role |
|------|------|
| `AGENTS.md` | Task-to-authority router and default exclusions |
| `CONTEXT-MAP.md` | Context boundary router |
| `CONTEXT.md` | Repository-wide glossary |
| `docs/README.md` | Documentation authority map |

## Local-only state

- `.tmp/` is scratch space and is not committed documentation.
- Absolute `.agents/skills/` links in other repositories are local workspace
  wiring.
- Caches, virtual environments, generated schemas, and execution artifacts are
  not knowledge sources.
