# Cross-Host Reconciliation

This page owns the small set of rules shared by source, link, and snapshot
changes across hosts.

## Authority

- An enrolled host uses its explicit Fleet Manifest as desired-state authority
  only when its local enrollment ID and current host/user guards match.
- An unenrolled host uses one explicit host-local profile confirmed by the
  configuration owner.
- A generated profile is a projection, not a second authority.
- Missing local configuration does not prove that a host is unenrolled.

## Agent and tool boundary

The Agent interprets user intent, compares source contracts, decides ownership,
chooses replacements, orders work, and decides recovery from new observations.
Tools provide bounded facts and safe mechanics: manifest/profile parsing,
catalog and Git identity, fleet audit, link or snapshot planning, digest-bound
apply, SSH transport, and postcondition readback.

Do not persist an Agent decision as a review state machine. Keep temporary plan
artifacts only for the guarded mutation they bind, then discard them.

## Cross-host rules

1. Resolve the local enrollment ID, current hostname and username, and the exact
   Host Binding before reading placement paths.
2. Collect source projection, registry, repository, ownership, provenance, and
   bounded agent-native exposure evidence on the host where those paths exist.
3. Show destructive scope before mutation. A verified, published Fleet
   revision authorizes its exact managed scope; an explicit host-local profile
   still needs separate destructive approval.
4. Apply one host or repository at a time. Preserve unrelated state.
5. Treat transport ambiguity as unknown; read back before any retry.
6. Complete only after the owning configuration and affected targets agree.
   Fleet work also requires an affected-host audit.

A converged Fleet proves managed desired state. Claim equivalent work
environments only after bounded agent-native, plugin, system, and agent-reported
skill exposure also agrees. External discovery supports findings and
recommendations; it does not grant authority to modify those locations.

Runtime installation and Git publication are separate actions. One-host Fleet
apply owns disposable pinned-source materialization. Their absence may block
evidence, but does not expand authority.
