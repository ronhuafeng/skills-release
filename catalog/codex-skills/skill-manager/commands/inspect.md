# Inspect

## Goal

Explain the managed skill registry, desired profile, source ownership, and
effective skill exposure in the selected work environment without changing
files.

## Contract

- A `source` owns skill content, a `profile` records desired exposure, a `link`
  exposes a source, and a `managed snapshot` is a repo-scoped copy bound to
  source and target digests in the repo vendor lock.
- Filesystem state proves what is exposed. The profile proves what is desired;
  it is not an inventory of everything discovered.
- Effective exposure includes managed registries plus skills exposed by the
  coding agent, installed plugins, system packages, and agent-native skill
  directories. A managed-state match does not prove that two environments have
  equivalent effective exposure.
- Agent-reported active skills prove exposure for that observed session. A
  filesystem entry proves only that content exists at that path unless the
  selected agent's loading contract is also known.
- Discovery outside the managed registry does not establish source ownership,
  desired state, or mutation authority.
- A symlink target establishes location, not upstream ownership. Claim copied
  content matches a source only after an exact comparison.
- `agents/openai.yaml`, when present, belongs to the same source identity as
  `SKILL.md`. Report its presence and invocation policy; include it in any
  exact source-versus-copy or managed-snapshot comparison.
- Report source metadata validation errors without treating invalid metadata as
  active policy.
- Treat an unreadable, invalid JSON, or unsupported-schema repo vendor lock as
  a registry anomaly. Report the lock error and continue inspecting readable
  entries; an invalid lock never proves managed-snapshot state.
- Inspection never recommends or mutates.

Require the explicit profile selected by the configuration owner. Do not fall
back to a `~/.codex/skill-manager/` runtime-state directory.

## Command

```text
skill-manager inspect \
  --profile "/absolute/profiles.toml" \
  [--registry global "$HOME/.agents/skills"] \
  [--registry "/absolute/repo" "/repo/.agents/skills"]... \
  [--source-root "/sources"]...
```

Exit `0` means a complete snapshot, `4` means required evidence is missing,
and `2` means invalid input. Stdout is structured, privacy-safe JSON.

## Workflow

1. Resolve the smallest useful scope. A named skill or repo stays focused;
   otherwise inspect the current workspace, the canonical global registry,
   profile sources, and profile repos. Do not scan `$HOME` or unrelated
   repositories.
2. Run `inspect` to load the profile and inspect global and relevant
   `<repo>/.agents/skills` entries.
3. When effective exposure matters, also inspect the selected agent's reported
   active skills when available. Probe only these bounded candidate roots for
   the current user and current workspace: `.agents/skills`, `.codex/skills`,
   `.claude/skills`, `.cursor/skills`, and `.grok/skills`. Do not crawl other
   tool state or plugin caches; include a plugin or system skill when the agent
   reports it as active.
4. Report broken links, real files or directories, entries without `SKILL.md`,
   source aliases, profile coverage, duplicate aliases, and duplicate
   frontmatter names. For each relevant valid skill, report whether
   `agents/openai.yaml` exists, the effective invocation policy, and metadata
   validation errors.
5. When provenance matters, classify each relevant entry as:
   - `profile-managed symlink`;
   - `managed snapshot` whose current digest matches its lock;
   - `agent-native or plugin exposure` outside manager authority;
   - `local symlink`;
   - `repo-owned runbook`;
   - `official/upstream copy` proven by known source plus exact match;
   - `copied/forked or stale` when a related source diverges;
   - `unknown real directory`;
   - `broken link` or `invalid entry`.
6. Compare directory contents byte-for-byte only when copied-versus-source
   identity affects the answer. Never infer official ownership from a name.
   Call content stale only when a known accepted source proves that it was
   removed, replaced, or changed.
7. Compare effective aliases and trigger scopes. Distinguish an exact duplicate
   from divergent content with the same identity and from different skills
   whose descriptions overlap.

## Report

Use counts plus anomalies for large inventories. Include the relevant exposed
path and form, desired profile status, resolved source when known, content-match
status when checked, `agents/openai.yaml` presence and invocation policy,
managed snapshot status when present, agent-native exposure, duplicate or
overlapping scope, and any ambiguity. State separately whether managed state
matches and whether effective exposure was fully observed. Do not dump raw
JSON or long file lists.

Finish when the requested current state and provenance are explained with no
mutations. For a proven orphan from an accepted source, report that evidence so
`recommend` can choose adoption or deletion.
