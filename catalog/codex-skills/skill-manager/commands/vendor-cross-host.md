# Cross-Host Vendored Placement

Use the same contract as [vendor.md](./vendor.md), but inspect and apply inside
the host that owns the repository path.

- Verify host, repository remote, source origin and revision, target ownership,
  vendor lock, and Git baseline before mutation.
- Do not transfer an orchestration checkout or infer source identity from equal
  filenames. A durable accepted source checkout must already exist, or source
  bootstrap must be separately authorized.
- Build and apply one guarded snapshot plan per repository in its host
  environment. Never reuse another host's absolute plan.
- Treat an ambiguous SSH result as unknown. Inspect snapshot and lock state
  before any follow-up action.
- Keep ignore changes, staging, commit, pull, and push separate.

Report host evidence, source and repository identity, plan actions, approval,
provenance readback, Git visibility, and unresolved work.
