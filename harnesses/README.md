# API-Only Primitive Harnesses

This workspace contains primitive capability packages used by Codex skills in
this repository.

Most members are independent `uv` packages with a `skills_*` import package.
Go primitives are independent Go modules. Primitive packages expose library APIs
only. They do not provide console scripts, workflow commands, or stable shell
entry points.

Skill workflows live in skill Markdown contracts or in skill-owned
orchestration packages outside this workspace.
Stable executable commands belong to those skill-owned orchestration packages,
not to this primitive workspace.

## Packages

- `codex/jsonl-go`: Go primitive for preserving non-empty JSONL lines.
- `codex/rollout-go`: authoritative Go rollout reader, selector, and typed
  views.
- `skills_frontmatter`: read and validate skill frontmatter and scan skill
  directories.
- `skills_openai_metadata`: inspect and validate optional skill
  `agents/openai.yaml` invocation metadata.
- `skills_profile_toml`: load, normalize, validate, and render skill profiles.
- `skills_snapshot_plan`: compute managed directory snapshot identities and plans.
- `skills_snapshot_mutation`: apply already validated managed snapshot plans.
- `skills_symlink_plan`: compute symlink plans from desired/current state.
- `skills_symlink_mutation`: apply already validated symlink plans.

## Validation

Run the workspace tests from this directory:

```bash
uv run pytest
cd codex/jsonl-go
GOWORK=off go test ./...
cd ../rollout-go
GOWORK=off go test ./...
```
