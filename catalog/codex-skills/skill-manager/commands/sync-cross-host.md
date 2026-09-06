# Cross-Host Linked Placement

Use the same contract as [sync.md](./sync.md), but collect and mutate state in
the selected host environment.

- Resolve the host from the Fleet Manifest or explicit user-selected SSH
  environment. Verify its identity before mutation.
- Prefer the installed audit runtime for structured read-only evidence. A
  missing runtime does not grant permission to install one; use bounded SSH
  inspection instead or stop when evidence is insufficient.
- Transfer no orchestration checkout or dependency environment. Execute the
  guarded link plan where the target paths exist, or invoke the same primitive
  through an explicit remote command.
- One plan belongs to one host. Do not reuse local absolute paths remotely.
- After an ambiguous SSH result, inspect the target state before deciding
  whether any action remains. Do not blindly retry.

Report remote identity, exact paths, source evidence, actions, readback, and
any state that remains unknown.
