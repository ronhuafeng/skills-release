# Agent instructions

## Repository boundary

This repository contains reusable Agent Skills maintained by ronhuafeng.
Committed content must be reusable across projects and must not be a
third-party mirror, upstream documentation copy, repo-bound runbook, or local
workspace wiring.

## Read route

Read the smallest authoritative path for the task:

| Task | Read |
|------|------|
| Ordinary skill execution | The selected `SKILL.md` and the command or reference it routes to; do not load repository authoring docs |
| Any repository change | [CONTEXT-MAP.md](./CONTEXT-MAP.md) and [docs/README.md](./docs/README.md) |
| Code or executable behavior change | [docs/develop/gates.md](./docs/develop/gates.md) plus the closest package README |
| System architecture or historical decision | [docs/architecture/INDEX.md](./docs/architecture/INDEX.md), then only the relevant ADR |
| Create a skill | System `skill-creator`, then `catalog/codex-skills/improve-skill/SKILL.md` |
| Review or refactor a skill | `catalog/codex-skills/improve-skill/SKILL.md`; use `mattpocock-skills:grill-with-docs` when genuine design choices remain |
| Architecture simplification, interface selection, or over-design review | `catalog/engineering/context-reduce/SKILL.md` |
| Session work | `catalog/codex-sessions/session-management/SKILL.md` and its selected command |
| Issues or PRDs | [docs/agents/issue-tracker.md](./docs/agents/issue-tracker.md) |
| Public release | [release/README.md](./release/README.md) and [release/public-files.txt](./release/public-files.txt) |

`catalog/` and each skill's metadata are the current catalog inventory. Do not
maintain a duplicate skill list in this file.

## Never by default

- private `codex_journal.md` and `codex_journal.d/`, when present in a
  development checkout, unless the user requests history;
- `.tmp/`, caches, virtual environments, generated schemas, and test artifacts;
- every ADR body when the index can route to one relevant decision;
- unrelated skill references or package READMEs;
- copied or vendored upstream material outside the task's explicit scope.

These sources may contain useful evidence, but they are not default product or
architecture authority.

## Working rules

- Use the vocabulary from the relevant `CONTEXT.md`. Keep glossaries free of
  procedures, validation commands, and implementation decisions.
- Record hard-to-reverse, non-obvious trade-offs in `docs/adr/`; update the ADR
  index when status changes.
- Keep runtime skills thin: `SKILL.md` routes, command documents own semantic
  contracts, primitive packages expose mechanical APIs, and stable executable
  composition remains skill-owned orchestration.
- When a run yields a reusable verified fact, update the closest owning
  document if the task authorizes it. Preserve its scope and evidence level;
  do not promote a one-off observation into a repository-wide rule.
- Remove superseded instructions and references in the same change. Historical
  evidence remains historical and must not create a fallback path.
- Original repositories may keep local absolute links under
  `.agents/skills/`; those links are workspace wiring and are not committed.
