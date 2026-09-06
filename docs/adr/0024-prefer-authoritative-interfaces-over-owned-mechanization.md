---
status: accepted
---

# Prefer authoritative interfaces over owned mechanization

Use the highest-level supported interface that owns the target state and can
prove the required post-condition. Add or retain a lower-level orchestration
command only when that interface lacks an explicit, verifiable, high-value
deterministic invariant; uniform entrypoints, hypothetical extensibility, and
testability alone do not justify duplicating the authority.
