# Domain documentation

This repository has multiple contexts. Start with the root
[CONTEXT-MAP.md](../../CONTEXT-MAP.md), then read only the `CONTEXT.md` relevant
to the task.

Use each context as a glossary:

- define project-specific terms in one or two sentences;
- choose one canonical term and name avoided synonyms;
- do not put procedures, command syntax, validation policy, or implementation
  decisions in a glossary;
- use the established term in issues, code, tests, and proposals.

Repository decisions live in [docs/adr/](../adr/), are classified by context,
and are routed through the [ADR index](../architecture/INDEX.md). Read only
decisions that touch the current work. If a proposal contradicts an accepted
ADR, surface the conflict instead of silently overriding it.

Create a new context or ADR only when the domain boundary or a hard-to-reverse
trade-off has actually been resolved. Missing template files are not work by
themselves.
