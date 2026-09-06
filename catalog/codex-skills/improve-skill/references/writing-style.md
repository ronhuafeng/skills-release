# Skill Writing Guide

This guide defines how a Skill and its references communicate. It does not define workflow, risk
policy, or tool choice.

Preserve the artifact's chosen language unless the user requests translation. Use direct technical
language and apply the rules below in that language.

## Write precise instructions

- Give each sentence one main instruction. Put the condition before the action.
- Use one term for one concept. Keep established domain terms when they improve precision.
- Use concrete verbs and explicit subjects. Avoid pronouns with unclear referents.
- Separate observed facts, decisions, actions, and results.

Use the canonical vocabulary of the target repository. Keep command names, protocol fields,
configuration keys, and code identifiers exact. Do not replace a precise domain term with a broader,
less accurate word.

State applicable rules directly. Do not describe the writing method or add a compliance disclaimer
unless the contract depends on it.

## Name the task directly

Titles name the task, action, or artifact. Do not use conversational introductions.

```text
Avoid: How I can help you check the service
Use:   Check the service
```

Start with the task contract. Do not explain why the Skill exists or how its wording was developed.

## Define observable results

State what the result contains, how to judge it, and which states can occur. Replace vague phrases
such as "handle errors appropriately" or "confirm when needed" with observable conditions.

```text
Avoid: Handle invalid input appropriately.
Use:   If schema validation fails, report the invalid field and do not write the file.
```

Use `unknown` when evidence is missing. Do not choose a convenient explanation.

## Separate evidence from conclusions

Keep these roles distinct:

- tool or command: how evidence is obtained;
- observation: what the tool or system returned;
- decision: what the evidence permits;
- action: what changes state;
- result: what was observed after the action.

A conclusion must trace to an observation. A successful command exit does not prove an external
result unless the command owns and verifies that result.

## State boundaries and sequence

State the conditions that change behavior. Say what is allowed, forbidden, or paused. Do not add a
generic safety checklist. The target Skill owns its risk policy.

Use ordered steps only when order affects correctness, authorization, or the result. Name steps with
concrete verbs. Within each step, state the condition before the action. End with stop conditions and
completion evidence.

## Define user-visible output

List the facts, decisions, side effects, next actions, and unknowns that the user needs. Do not expose
the internal tool transcript by default.

## Write references as references

A reference defines its topic and scope. Organize it by concept, and separate mechanisms, limits, and
exceptions. Use neutral prose. Do not turn a reference into a dialogue, execution log, or design
history.
