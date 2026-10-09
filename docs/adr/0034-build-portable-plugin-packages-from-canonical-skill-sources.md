---
status: amended by 0035
---

# Build portable Plugin packages from canonical Skill sources

The repository remains the **source monorepo**, not the distributable OpenAI
Plugin root. `catalog/engineering/` stays the canonical source of engineering
Skills. A deterministic packaging step materializes a portable Plugin package
for a specific source commit and semantic version.

The target distribution shape is:

```text
catalog/engineering/                 canonical Skill source
release/plugins/engineering/         package/release source metadata
          |
          | deterministic build
          v
dist/plugins/ronhuafeng-engineering/ generated, uncommitted package
├── plugin.json                      portable Agent Plugins manifest
├── skills/                          materialized engineering Skills
└── assets/                          package-owned distribution assets
          |
          v
ronhuafeng-engineering-<version>.zip complete release/submission artifact
```

The generated `dist/` tree is disposable evidence, not a second source
authority. Do not commit generated copies of `catalog/engineering/`.
Packaging must preserve one-to-one provenance from each packaged Skill to its
canonical source and fail when required resources are missing, duplicated, or
escape the package root.

The portable package uses root `plugin.json` with the Agent Plugins schema.
Portable identity stays at the manifest root. OpenAI-specific presentation,
onboarding, review, and publication metadata belongs under
`extensions.com.openai`. The initial package is skills-only: do not add an
MCP server merely to satisfy a Plugin shape. Add MCP only for a separately
accepted capability that requires live data, authentication, controlled
external actions, or hosted execution.

`agents/` remains a separate role-contract layer and is not packaged as a
Plugin component. `harnesses/` remains repository/runtime source; local
mechanical capabilities are not converted to MCP by default.

Existing Codex and Claude compatibility manifests remain supported migration
surfaces until the portable path has equivalent verified consumers. Once
client-specific metadata diverges, validation should require **semantic parity
of intentionally shared identity fields**, not byte-for-byte equality of whole
manifests.

Keep publication states distinct:

1. **source merged** — canonical repository content is accepted;
2. **package built** — one portable package exists for an exact source commit
   and version;
3. **package verified** — structural distribution contracts and applicable
   activation evaluations pass for that exact package;
4. **bounded distribution** — the verified package is available through a
   repo/local marketplace or workspace;
5. **public approved** — the submitted ZIP passed directory review;
6. **public published** — that approved version is visible in the universal
   Plugins Directory.

Evidence for one state does not prove another. In particular, merging to
`main` does not itself publish a Plugin, workspace publication is not public
publication, and structural package validation does not prove model activation
behavior.

Distribution verification should use a semantic CI owner for Plugin package
contracts and separate behavior evaluation. Activation evaluation uses labelled
direct, indirect, negative, follow-up, and unsupported prompts while keeping
the expected result outside the prompt shown to the candidate. A live
activation result is bound to the tested package revision and client surface.

Public Plugin publication remains an explicit operator action. The release path
must identify the canonical source commit, Plugin version, complete verified
ZIP, distribution surface, and publication state. Private reviewer credentials
and secrets never enter the repository or package.

Implementation is tracked by #7, #8, and #9 under architecture issue #6.

OpenAI package, metadata, evaluation, and publication semantics are defined by:

- https://developers.openai.com/plugins/build/plugins
- https://developers.openai.com/plugins/build/skills
- https://developers.openai.com/plugins/guides/optimize-metadata
- https://developers.openai.com/plugins/deploy/submission
