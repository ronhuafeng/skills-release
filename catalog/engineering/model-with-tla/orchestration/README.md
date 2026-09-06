# model-with-tla orchestration

This package owns the stable `tla-check` command used by the
`model-with-tla` Agent Contract. It checks one exhaustive SANY/TLC outcome
against one explicit expectation and returns one JSON result.

The command owns only deterministic execution:

- bundled-tool identity and checksum;
- Java compatibility;
- SANY semantic status;
- isolated TLC metadata;
- expected versus observed result classification;
- TLC statistics and bounded diagnostics;
- temporary-data cleanup.

It does not select the abstraction, property, fairness, model cardinality,
claim class, or implementation mapping. It does not download a tool, enable a
fallback, add TLC constraints, or rewrite a model.

## Command

Runtime callers use the stable Skill-owned entrypoint:

```bash
"<skill-directory>/.tools/tla-check" check \
  --module "/absolute/path/Model.tla" \
  --config "/absolute/path/Model.cfg" \
  --expect success
```

The entrypoint owns the package execution details. Package maintainers can run
the installed project command directly with `uv run --locked tla-check` from
this directory.

Supported expectations are:

```text
success
semantic-error
invariant:<name>
temporal
deadlock
assumption
assertion
```

Set `TLA_JAVA` to an absolute Java executable when the default `java` is not
Java 11 or newer. The command exits `0` only when the observed result matches
the expectation. Exit `2` means invalid input, `3` means a tool prerequisite or
execution failure, and `4` means an expectation mismatch.

## Validation

From this directory:

```bash
TLA_JAVA="<java-11-or-newer>" uv run --locked pytest
```
