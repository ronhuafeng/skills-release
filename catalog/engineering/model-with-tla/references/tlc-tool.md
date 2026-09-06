# TLC Tool

Use the bundled `tla-check` command for accepted SANY and exhaustive TLC
results. It binds one model invocation to one expected outcome and reports a
structured result.

## Toolchain authority

[`toolchain.json`](../.tools/toolchain.json) is the only exact authority for
the bundled JAR version, checksum, upstream revision, build timestamp, Java
floor, pre-release status, source provenance, and retained license.

Before running a model, `tla-check` verifies:

- the JAR checksum;
- the embedded upstream revision and build timestamp;
- the available Java version;
- the SANY result before invoking TLC;
- the observed TLC result against the declared expectation;
- temporary TLC state cleanup.

Do not download a replacement during ordinary Skill execution or fall back to
a system, Maven, Toolbox, nightly, or older TLC. A maintainer upgrade replaces
the JAR and manifest together and reruns the checker integration and live
reproducer.

## Run the checker

Resolve the Skill directory from the selected `model-with-tla/SKILL.md`, then
run from any working directory:

```bash
"<skill-directory>/.tools/tla-check" check \
  --module "/absolute/path/Model.tla" \
  --config "/absolute/path/Model.cfg" \
  --expect success
```

Supported expectations are `success`, `semantic-error`, `invariant:<name>`,
`temporal`, `deadlock`, `assumption`, and `assertion`. Omit `--config` only for
`semantic-error`. Set `TLA_JAVA` to an absolute Java executable when the
default Java is too old.

Exit `0` means the observed result matched the expectation. Exit `2` means
invalid input, `3` means a blocked tool invocation, and `4` means expectation
mismatch. The JSON result contains tool identity, expected and observed
outcomes, state statistics, duration, and bounded diagnostics without caller
directory paths.

## Check configuration adequacy

A TLC configuration is one finite instance. Before accepting its result:

- justify constants and cardinalities against the identities, operations,
  values, histories, and interleavings required by the claim;
- name each state or action constraint and the behavior it excludes;
- use symmetry only when the specification and checked properties are
  invariant under the permutation;
- treat overrides as semantic changes to the checked model;
- distinguish exhaustive model checking from sampled simulation;
- decide whether a state without a successor is terminal, quiescent, or
  deadlocked before changing deadlock checking;
- preserve warnings and violated assumptions instead of treating exit zero as
  sufficient evidence.

If finite configurations cannot establish a parameterized or unbounded claim,
classify it as `unproved`. Do not install a proof system or expand the task
automatically.

## Exploratory invocation

Direct SANY or TLC invocation is allowed only when an exploratory flag is not
supported by `tla-check`. Run from the model directory so sibling modules
resolve, use the bundled JAR, and place TLC metadata and generated artifacts in
a temporary directory outside the repository.

```text
java -cp "<skill-directory>/.tools/tla2tools.jar" \
  tla2sany.SANY -error-codes "<module>.tla"

java -XX:+UseParallelGC \
  -jar "<skill-directory>/.tools/tla2tools.jar" \
  -metadir "<temporary-directory>" \
  -noGenerateSpecTE \
  -config "<model>.cfg" \
  "<module>.tla"
```

Direct invocation is diagnostic evidence, not an accepted check. A positive
result still requires the declared properties. A negative result requires the
intended violation and counterexample, not any nonzero exit.

Report the checker result with the configuration assumptions, constraints,
symmetry, overrides, deadlock decision, run mode, and any retained exploratory
output.
