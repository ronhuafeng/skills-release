# Personal Skills

This glossary defines language shared by Agent Skills maintained in this
repository. Domain-specific language is routed through `CONTEXT-MAP.md`;
runtime contracts and validation procedures live in their owning documents.

## Language

**Agent Contract**:
A skill document that tells Codex what to run, what to read, what not to do, and what proves completion.
_Avoid_: manual, guide, explanation, runbook

**Router Skill**:
A user-invoked skill whose job is to select one primary Subcommand Contract and
sequence only explicitly requested dependent contracts through exact verified
outputs.
_Avoid_: index, dispatcher, menu

**Subcommand Contract**:
A command document that owns one path through a router skill and states its run
steps, references, prohibitions, and completion gate.
_Avoid_: subcommand README, workflow

**Thin Skill**:
A skill whose Markdown stays focused on trigger conditions, routing, semantic
judgment, harness calls, and stopping conditions.
_Avoid_: script bundle, implementation folder

**Project Harness**:
A complete, testable software project that provides the mechanical capabilities
a skill calls through a stable CLI or API.
_Avoid_: scripts directory, helper dump

**Harness Component**:
A focused unit inside a project harness that owns one mechanical capability,
such as parsing, validation, or writing.
_Avoid_: pipeline stage, utility blob

**Primitive Capability**:
A stable, atomic harness API that performs exactly one mechanical action, such
as reading Codex SQLite diagnostic rows, parsing rollout JSONL records,
extracting session metadata, reading profile TOML, planning a symlink diff, or
applying a guarded symlink mutation.
_Avoid_: workflow command, business script, bundled operation

**Primitive Capability Package**:
A separately owned harness package for one primitive capability family. Codex
SQLite diagnostics, rollout JSONL parsing, profile TOML access, symlink
planning, and symlink mutation are separate packages, not modules collected
under one generic shared directory.
_Avoid_: shared utils, common folder, catch-all harness

**Harness Workspace**:
The current default project shape for primitive capability packages: one
repository-local `harnesses/` workspace containing multiple independently
owned packages. This is a reversible packaging choice, not a domain rule.
_Avoid_: monolithic harness, unrelated project scatter

**API-Only Harness Package**:
A primitive capability package exposes stable library APIs and does not expose
console scripts or stable CLI commands. Tests may execute the API directly, and
skill documents should reference importable APIs rather than shell entry points.
_Avoid_: CLI wrapper, command adapter, script entry point

**Skill-Specific Orchestration**:
A skill-owned orchestration layer that composes primitive capability packages
for that skill's workflow. It may be expressed as Markdown command contracts,
skill-specific library APIs, stable orchestration commands, or a combination.
It preserves flexibility for semantic workflow decisions while keeping
deterministic behavior in tested code.
_Avoid_: primitive package workflow, embedded data processing, ad hoc command script

**Orchestration Command**:
A stable, skill-owned executable interface that adapts explicit arguments or
structured input to a skill-specific orchestration library. It emits structured
results and reliable exit status without owning user-intent judgment, semantic
classification, or implicit recovery policy.
_Avoid_: primitive CLI, workflow engine, semantic automation

**Authoritative Interface**:
The highest-level supported interface that owns the target state and returns
enough evidence to verify the required post-condition.
_Avoid_: executable by default, highest layer by appearance, raw storage mutation

**Necessary Package Dependency**:
A dependency from one primitive capability package to another that is required
by the capability's contract, not merely convenient. Package dependencies must
be explainable from the capability boundary; otherwise duplicate the small
logic locally or introduce a better primitive package.
_Avoid_: convenience import, generic utility dependency, hidden workflow coupling

**Domain-Grouped Primitive Packages**:
Primitive packages may be grouped by filesystem domain, such as
`harnesses/codex/jsonl-go` and `harnesses/codex/rollout-go`. The filesystem
grouping does not imply a shared Go package; module paths and package names keep
each capability independently owned.
_Avoid_: generic `codex` import package, namespace package by default

**Fallback Reference**:
A document loaded only when the default path is unavailable or recoverably fails.
_Avoid_: appendix, background docs

**Mechanical Gate**:
A deterministic script check that rejects invalid output before mutation or rendering.
_Avoid_: reminder, guideline

**Semantic Gate**:
An agent judgment that compares proposed output against evidence when a deterministic script cannot decide.
_Avoid_: vibes, review

**Fleet Manifest**:
A version-controlled logical desired-state document that names accepted Skill
Sources, repositories, global exposure, and stable host identities without
using host paths as shared identity.
_Avoid_: shared profiles.toml, copied host inventory, fleet runtime state

**Host Binding**:
The mapping from one stable host identity to that host's absolute source,
repository, profile, runtime, and transport locations.
_Avoid_: host identity, SSH alias, portable path

**Enrollment ID**:
A non-secret canonical UUID that binds one host-user installation to one Fleet
Host Binding, guarded by the manifest hostname and username.
_Avoid_: hardware fingerprint, credential, host path, SSH alias

**Host Source Binding**:
The host-specific mapping from one accepted Skill Source to its Git checkout
root and, when profile discovery is desired, one relative discovery directory
inside that checkout.
_Avoid_: source root, source identity, skill path

**Source Alias Tree Identity**:
The Git tree object ID of an accepted alias directory at its pinned source
revision. It identifies only committed source content; host-local ignored or
untracked artifacts are outside this identity.
_Avoid_: snapshot digest, working-directory hash, source checksum

**Runtime Profile**:
The host-local `profiles.toml` representation deterministically derived from a
Fleet Manifest and one Host Binding after fleet enrollment.
_Avoid_: fleet manifest, cross-host profile, shared absolute paths

**Managed Skill Snapshot**:
A repo-scoped, one-way copy of a reusable skill source whose source and target
content identities are recorded so the copy can be safely updated or removed.
_Avoid_: permanent sync, ordinary copy, mirror, fork

**Skill Source Qualification**:
The skill-manager orchestration policy that composes primitive metadata facts
for a specific operation. Link exposure requires readable Skill identity plus
valid optional OpenAI metadata; managed snapshots and fleet enrollment require
strict frontmatter plus valid optional OpenAI metadata. Invocation policy comes
only from `agents/openai.yaml`.
_Avoid_: generic source validator, profile-owned metadata policy, one universal qualification

**Repo-Owned Skill Fork**:
A real repo-local skill whose repository owns future content changes, even when
it descends from a reusable skill source.
_Avoid_: managed snapshot, vendored copy, stale copy
