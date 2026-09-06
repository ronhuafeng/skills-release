# Recommend

## Goal

Propose a small, explainable skill placement diff without changing files.

## Contract

- Each reusable skill has one content owner. Global and repo registries normally
  expose that owner through symlinks. A repo may intentionally store a managed
  snapshot when portability or version pinning justifies a provenance-bound copy.
- The profile records desired exposure, not every discovered source.
- Recommendations consider effective exposure outside the profile because
  duplicate identities and overlapping implicit triggers change the coding
  agent's available context and routing behavior.
- Global exposure is reserved for high-frequency, cross-project skills with a
  low false-trigger and risk cost.
- A real repo-local skill directory is valid only when it is an intentional
  repo-owned runbook or fork. Names alone do not prove ownership.
- Ambiguous, bulky, risky, rare, or experimental skills default to manual use.
- Read invocation policy from `agents/openai.yaml`, when present. Treat
  `policy.allow_implicit_invocation: false` as evidence for manual invocation;
  do not infer policy from the `SKILL.md` description. Invalid metadata blocks
  a placement recommendation that depends on invocation policy.

## Evidence Command

Use the `inspect` orchestration command and bounded environment discovery from
`commands/inspect.md` for evidence. Do not create a separate recommend command:
placement is Codex semantic judgment over that evidence.

## Workflow

1. Inspect the relevant global, repo, profile, source, agent-native, plugin, and
   agent-reported exposure without mutation.
2. For repository intent, read only bounded signals such as `AGENTS.md`,
   `CONTEXT.md`, `.agents/skills`, and the primary package manifests. Do not
   search the whole repository for keyword matches.
3. Classify real repo-local directories as `repo-owned runbook`, proven
   `official/upstream copy`, `copied/forked or stale`, or `unknown`.
4. Identify exact duplicates, divergent skills with the same identity, broken
   entries, proven stale content, and semantic trigger overlap. Give priority
   to overlap between implicitly invocable skills because it can change task
   routing even when aliases differ.
5. Assign each skill one proposed exposure:
   - `global`: frequent and broadly applicable with low trigger cost;
   - `repo`: useful for the named repository;
   - `vendor`: repo-portable, pinned managed snapshot with a known source;
   - `manual`: rare, risky, bulky, experimental, or ambiguous;
   - `remove`: broken or explicitly unwanted exposure.
6. Prefer source registration plus symlink exposure for a proven upstream copy.
   Recommend vendor only for a concrete portability or pinning need. For
   divergent or unknown real directories, preserve them and request an
   ownership decision. For a proven orphan with accepted-source provenance and
   no repo-owned or user-created claim, recommend adoption or deletion rather
   than indefinite preservation.
   For an external agent-native or plugin skill, recommend keep, adopt, update,
   replace, make manual-only, or remove. Do not apply that recommendation unless
   the user accepts it and the owning agent location is established.
7. Check that every proposed include has a valid source and that aliases are
   unambiguous. Report missing or inconsistent `agents/openai.yaml` metadata
   when it changes the proposed exposure.

## Report

Show a proposed diff grouped into:

- keep global;
- move to repo;
- make manual-only;
- remove broken or unwanted links;
- source and profile changes required;
- repo snapshots to vendor, update, or unvendor;
- agent-native or plugin skills to keep, adopt, update, replace, make
  manual-only, or remove;
- duplicate identities, overlapping trigger scopes, broken entries, and proven
  stale content;
- copied directories requiring migration or an ownership decision.

State assumptions and blockers. Do not mutate profile or links. Route accepted
Linked placement to `sync` and Vendored placement to `vendor`; each mutation
must establish Fleet or explicit profile authority first.
