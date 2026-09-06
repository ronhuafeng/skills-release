---
status: accepted
---

# Make repo placement host-specific

Fleet Manifest schema 2 keeps each `repo_id` and canonical Git remote as shared
identity, but moves `path`, `include`, and `vendor` into each host's repo
binding. A host that does not bind the repo has no desired placement for it.

Real enrollment evidence showed the same repository linked on one host and
vendored on another, with different desired alias sets. The undeployed schema
1 model could represent only one common repo placement and therefore could not
render both accepted host profiles without losing intent.

Schema 2 directly replaces schema 1. The parser rejects bare repo paths and
common repo `include` or `vendor` fields; no migration reader or compatibility
path remains. Profile rendering, host-audit protocol, and fleet audit all use
the selected host binding as the sole repo-placement authority.
