---
status: accepted
---

# Require complete decodability for filtered rollout output

An unfiltered `session-management rollout` invocation writes every non-empty
source line unchanged because raw reading requires no structural interpretation.
A filtered invocation validates that every non-empty line is a JSON object
before writing stdout; any malformed or non-object line yields no output and
exit `3`. Invalid filter JSON yields exit `2`. Unknown fields and tagged variants
remain valid match candidates. Eager single-file reading provides this
all-or-nothing filtered-output behavior without another buffering abstraction.
