---
name: engineering-agent-kit
description: Install five reusable, project-scoped Codex specialist agents for product design, interaction design, UI implementation, quality review, and context reduction. Use when the user explicitly requests installing or updating these agents.
user-invocable: true
disable-model-invocation: true
---

# Engineering Agent Kit

Distribute five standalone Codex agent TOML templates as resources in the existing engineering Plugin. **Installing the Plugin does not register these agents.** Codex loads custom agents from a project's .codex/agents/ directory or from the user's ~/.codex/agents/ directory, not from Plugin manifest agent fields.

## When to use

Only when a user explicitly requests agent setup, inspection, or installation. Read the target project's AGENTS.md and relevant project instructions first. These templates are cross-project and do not override business rules, design systems, or permissions. Check actual client support and installed Skills; a mention of $skill-name does not grant invocation permission.

## Templates

The five canonical templates live in this Skill's templates/ directory:

- product_architect.toml — user journeys, decisions, and product state semantics.
- interaction_designer.toml — control semantics, layout, evidence comparison, and accessibility.
- ui_engineer.toml — authorized implementation, design system, and behavior validation.
- quality_reviewer.toml — independent acceptance and evidence review.
- context_maintainer.toml — remove unnecessary engineering context without weakening correctness.

These templates are **Agent roles, not five new Skills**. The named $... Skills supply methods; the Agent owns judgment and handoff.

## Install / update

1. Resolve the target project and the roles requested. Default to project-scoped .codex/agents/, never silently install globally.
2. Inspect all selected destination files before writing. Parse the source TOML and verify each filename matches its name field, with nonempty description and developer_instructions.
3. If a destination file is identical, do nothing. If it differs, show the meaningful diff and obtain permission before replacing it. Never clobber user customizations.
4. For authorized new or replaced files, copy the template bytes from this Skill's own templates/ directory into the target .codex/agents/. Do not symlink to a transient Plugin cache, or invent an unsupported Plugin manifest key.
5. Parse and read back the installed files. If a supported Codex client is available, verify discovery in a new session. If not, report discovery as not_evaluated.
6. Report destination, installed / unchanged / conflicting roles, required Skills not available, and exact verification scope.

Copying a template is not permission to activate agents, change product code, run external operations, commit, merge, or deploy.

## Invocation boundaries

- $radical-kiss-ui and $prune-legacy have explicit invocation policies. A template does not override them: require the user's explicit invocation where necessary.
- $context-reduce without confirmed findings starts read-only; installing the role does not authorize apply.
- $live-story-review and $live-gate-review require accepted contract and evidence prerequisites, and do not authorize live or paid operations.
- $apple-design and $emil-design-eng are external Skills, not bundled here. Their availability must be checked.
- Stitch MCP is an external design tool, not a Skill; follow the target project's requirements for its use.

## Completion

Requested TOML files exist at the authorized destination and have been read back; no conflicts were overwritten without approval. Separate syntax checks from verified host discovery. Do not claim automatic Agent registration through Plugin installation.
