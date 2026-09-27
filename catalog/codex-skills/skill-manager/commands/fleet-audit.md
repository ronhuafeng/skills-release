# Audit Fleet Reconciliation

## Goal

Compare one fleet manifest with stable read-only facts from selected local or
SSH hosts. Do not repair drift.

Read
[`fleet-model.md`](../references/fleet-model.md) for desired state and
[`fleet-audit-contract.md`](../references/fleet-audit-contract.md) for evidence,
drift states, and completion gates.

## Contract

- Require an explicit manifest. An omitted `--host-id` selects every declared
  host; repeated `--host-id` values select only those stable host identities.
- Render desired state before inspection. Invalid manifest or host bindings
  stop with no host mutation.
- Require matching host-local enrollment ID, hostname, and username evidence.
  Missing or mismatched identity makes that host result `incomplete`.
- For Local and SSH transports, send one versioned host-scoped JSON request to
  the configured absolute runtime. Do not substitute the coordinator process
  or expose another host's inventory.
- Audit the in-memory profile projection, requested and effective invocation
  policy, source Git identity and content, registry link targets and metadata,
  repo remote identity, vendor provenance, repo-owned
  declarations, and Git visibility.
- `converged` proves only the manifest-managed state. It does not prove that
  coding agents expose the same complete skill set through native directories,
  plugins, or system packages.
- Fingerprint relevant state before and after inspection. Report
  `concurrent_change` instead of a convergence claim when it changes.
- Preserve completed host results when another host is incomplete. Do not
  bootstrap, upgrade, copy, refresh, apply, commit, push, or pull.

## Command

```text
skill-manager fleet-audit \
  --manifest "/absolute/fleet.toml" \
  [--host-id "<stable-host-id>"]...
```

Exit codes:

- `0`: `converged`;
- `2`: `invalid`;
- `3`: `drifted`;
- `4`: `incomplete`.

Stdout is one versioned JSON object. Human-readable transport or runtime
diagnostics remain in the corresponding host's blockers.

## Workflow

1. Confirm the manifest owner and selected logical hosts.
2. Verify that installing or updating any missing target runtime is a separate
   authorized operation. Audit itself must not perform it.
3. Run `fleet-audit` once and retain every host result.
4. Separate deterministic drift from missing evidence. Do not classify an
   undeclared real repo directory as owned.
5. When the request concerns complete environment visibility, perform the
   bounded discovery from `inspect` on each selected host. Keep these findings
   outside the command's managed-state result.
6. Report the required `sync`, `vendor`, or `refresh-source` action for each
   repairable difference. Do not edit the Fleet Manifest or apply a repair.
7. State that a separately authorized repair completes only after the same
   audit proves `converged`. The audit request itself authorizes observation
   only.

## Report

Report the manifest digest, overall state, each host state, effective Skill
policies, drift codes, identity mismatches, ownership or evidence gaps, and before/after
fingerprints. Report managed convergence separately from external effective
exposure and cross-host visibility differences. Summarize large alias sets;
preserve exact JSON privately when it is needed for repair planning.
