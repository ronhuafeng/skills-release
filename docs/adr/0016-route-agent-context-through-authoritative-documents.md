---
status: accepted
---

# Route agent context through authoritative documents

Repository context uses a small routed hot path instead of one comprehensive
`AGENTS.md` or repeated facts across guides. `AGENTS.md` selects the task's
authority, `CONTEXT-MAP.md` selects the glossary, `docs/README.md` separates
normative, verified, working, and historical evidence, the ADR index selects
binding decisions, and `docs/develop/gates.md` selects validation scope.

Runtime skill contracts and package APIs remain with their content owners.
Journals, `.tmp/`, superseded ADRs, generated artifacts, and unrelated
references are excluded from default reading so historical or incidental state
cannot silently become current behavior. New knowledge or archive directories
are created only when verified cross-cutting facts or valuable historical
material actually need an owner.
