# Context Map

## Contexts

- [Personal Skills](./CONTEXT.md) — shared language for reusable skills,
  harness primitives, and skill-owned orchestration.
- [Session Management](./catalog/codex-sessions/session-management/CONTEXT.md)
  — session, rollout, journal, split, rename, and rehome language.

## Relationships

- Session Management specializes the repository-wide Agent Contract and
  orchestration vocabulary; it owns all session-specific terms.
- Repository decisions live under `docs/adr/`, are classified by context, and
  are routed through
  [docs/architecture/INDEX.md](./docs/architecture/INDEX.md).
- Runtime behavior is owned by the selected skill and command documents, not
  by either glossary.
