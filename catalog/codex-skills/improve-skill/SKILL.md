---
name: improve-skill
description: Review or improve an existing Codex Skill from its contract, references, observed failures, and verification evidence. Use when the user asks to review, optimize, rewrite, refactor, or repair a Skill.
---

# Improve a Skill

Review evidence, diagnose the causes, and design the smallest supported change.

If the task concerns wording or information presentation, read the
[writing guide](references/writing-style.md). If the task concerns scripts, executables, stable tool
interfaces, state machines, or fixed command sequences, read the
[mechanization boundary](references/mechanization.md).

## Confirm the scope

Read the target `SKILL.md`. For a review of the complete Skill, or a change to its trigger, scope, or
behavior contract, read every directly referenced resource. For a bounded change, read each resource
that owns or consumes the affected behavior. Also read applicable repository instructions, relevant
validators, and the current worktree state. Then select the mode:

- If the user asks to optimize, rewrite, refactor, repair, or otherwise change the Skill, edit within
  the named scope unless the user sets a read-only restriction.
- If the user asks only for a review, audit, analysis, or findings, stay read-only.
- If change and read-only instructions conflict, follow the more specific instruction. If the
  conflict remains unresolved, stay read-only.
- If the user requests a new Skill, use `skill-creator`.
- If the user requests improvement candidates from session traces, use `skill-detect`. Return to
  this Skill after the candidate is confirmed.

Preserve unrelated worktree state.

## Diagnose the Skill

Use the Skill's real tasks, user corrections, observed failures, tests, and current content. Check:

- whether the description selects the intended tasks and rejects unrelated tasks;
- whether the contract defines outcomes, decision rules, stop conditions, and completion evidence;
- whether the Skill defines only the contract it owns and avoids repeating the procedures of invoked
  Skills or the coding agent;
- whether model discretion matches the operation risk;
- whether `SKILL.md` and each resource support the current contract;
- whether any content is duplicate, obsolete, unreachable, or behaviorally inert;
- whether the text names responsible subjects and separates tools, observations, decisions, actions,
  and results;
- whether verification proves the affected behavior instead of format only.

Distinguish a Skill defect from a model judgment error, tool failure, target-repository defect, or
one-time preference. Keep an unsupported explanation `unknown`; do not turn it into a rule.

## Design the smallest improvement

Choose the smallest change that can prevent recurrence. Use this order:

1. fix an existing trigger, contract, decision rule, gate, or completion condition;
2. move conditional detail to a directly linked reference;
3. delete duplicate, obsolete, inert, or out-of-scope content;
4. create a separate Skill only when the task has an independent trigger and completion contract.

Before deleting an instruction, classify it as an owned contract, required dependency gate,
duplicate procedure, or explicitly replaced behavior. Preserve confirmed contracts and gates unless
the requested change explicitly supersedes them.

Keep the current capability scope unless the user requests a scope change. Tighten or remove
unsupported constraints. If evidence is missing, report the gap; do not invent behavior. Do not turn
a wording task into implementation work.

If alternatives change user-visible behavior, ownership, or compatibility, ask for one necessary
decision and recommend one answer. If the repository or a tool can resolve a fact, resolve it before
asking the user.

## Apply the change

Change only the authorized target and necessary direct consumers. Remove replaced entrypoints,
duplicate rules, and resources that support only the old behavior. Keep the frontmatter,
`agents/openai.yaml`, reference links, and actual capability aligned.

## Verify the result

Match verification to the change risk:

- run the applicable Skill validators;
- check the structure, frontmatter, identity, direct links, and UI metadata;
- run focused checks for affected behavior;
- if a safety gate changed, test its rejection paths and target identity;
- if judgment behavior changed, use a realistic task that does not contain the expected answer.

If behavior changed, format checks alone do not prove completion. Report unavailable evidence and
the remaining risk.

For a read-only task, report evidence-backed findings in impact order. Include the evidence, behavior
impact, smallest repair, and unknowns. For an applied change, also report changed artifacts,
user-visible behavior changes, verification, and remaining risk.

Complete the task only when:

- the scope, authorization, and evidence are clear;
- each finding has a supported impact and repair;
- the selected mode has produced precise findings or applied and verified the authorized change.

Keep unverified claims `unknown`.
