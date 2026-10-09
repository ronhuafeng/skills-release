# Optional portable Plugin build

Build one ignored engineering Plugin package from the canonical Skill catalog
and the committed root Codex manifest. `release/plugins/engineering/source.json`
owns only ZIP presentation/keywords/assets; it must not declare identity,
version, inventory, or configurable parity rules.
The public GitHub marketplace loads the committed repository root directly;
this build is for an explicitly chosen ZIP release and is not an install step.

The build reads the committed Git tree at `HEAD`. It does not change canonical
Skill source, and it does not publish the Plugin.

## Build

From the repository root:

```sh
PYTHONPATH=release/plugin_build/src \
  uv run --locked --project harnesses python -m plugin_build
```

The command writes these ignored outputs:

- `dist/plugins/ronhuafeng-engineering/`
- `dist/plugins/ronhuafeng-engineering-<version>.zip`

## Validation

From the repository root:

```sh
uv run --locked --project harnesses pytest release/plugin_build/tests/test_build.py
```

These tests prove deterministic package contents, canonical Skill provenance,
shared manifest identity, and rejection of missing, duplicate, escaping, or
over-limit packages. They do not prove Skill activation. Activation evidence
is a separate gate in `docs/develop/gates.md`.

## Source authority

`src/plugin_build/source.py` validates the committed root manifests and tracked
canonical catalog for marketplace, builder, activation, and release reporting.
It requires safe regular tracked files, semantic shared identity parity, and a
checkout matching HEAD at those boundaries. Inventory is discovered from tracked
`catalog/engineering/*/SKILL.md`; all tracked catalog resources are validated.
Git-ignored runtime caches are not source. Optional ZIP configuration is read
only by the builder. Activation owns its labelled golden prompts, and release
reporting owns artifact/publication evidence. Neither infers live client success.

Run the complete contracts from the repository root:

```sh
uv run --locked --project harnesses pytest release/plugin_build/tests
```
