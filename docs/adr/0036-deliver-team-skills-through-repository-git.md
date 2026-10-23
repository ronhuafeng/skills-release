---
status: accepted
---

# Deliver team Skills through repository Git

A team repository that must work without the maintainer's Skill Manager commits
complete Skill files under `.agents/skills/`. Its Git workflow owns acceptance
and distribution. The shared source owns upstream development; the consuming
repository owns its accepted version and local customizations.

Keep one useful source record, including the upstream repository, accepted
revision and source paths when known. Git records the accepted files. Developers
use clone and pull, not host enrollment or a personal cache. Required tools,
resources, client metadata and licenses remain part of the delivery contract.

Personal Fleet configuration need not describe these repositories. Withdraw
existing Fleet scopes explicitly before transferring ownership, without deleting
project files. Explicit managed placements retain their existing contract until
that transfer; this decision does not silently change a published Fleet scope.

The same Skills use one delivery route within the repository. Other Plugins and
personal Skills may remain, but their installation does not prove project-local
discovery. Verify the target client's actual discovery separately when claiming
activation.

Repositories may accept updates at different times. This is deliberate version
selection, not a reason to build continuous synchronization, patch stacks or
another registry.
