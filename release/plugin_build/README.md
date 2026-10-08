# Portable Plugin build

Build one ignored engineering Plugin package from the canonical Skill catalog
and `release/plugins/engineering/source.json`.

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
