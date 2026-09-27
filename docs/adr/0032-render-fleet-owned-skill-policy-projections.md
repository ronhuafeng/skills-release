---
status: accepted
---

# Render Fleet-owned Skill policy projections

Fleet Manifest schema 5 owns the effective implicit-invocation policy for a
managed Skill. A source can define a `default`, `allow`, or `deny` default. An
explicit Skill alias can select one native Skill from a source, resolve a name
collision, and override that default. The precedence is Skill override, source
default, then unchanged upstream metadata.

Pinned source checkouts remain exact upstream evidence. Fleet does not edit
them and does not require a public adapter repository. When the effective
policy is not `default`, or the Fleet alias differs from the native name,
`apply` materializes a disposable copy at
`~/.cache/skill-manager/rendered/<manifest-digest>/<alias>`. It changes only the
frontmatter name when needed and the agent-specific invocation fields: Codex
`agents/openai.yaml` `policy.allow_implicit_invocation` and Claude
`SKILL.md` `disable-model-invocation`.

The deterministic Runtime Profile points at the derived copy. Accepted
placement authority binds its filesystem digest, so a changed projection
blocks apply. Render, apply receipts, and Fleet audit expose the source default,
Skill override, effective policy, and whether projection is required. The
host-audit wire protocol remains version 4 because the canonical profile already
contains the effective source paths; schema 5 is a desired-state change, not a
new remote observation contract.
