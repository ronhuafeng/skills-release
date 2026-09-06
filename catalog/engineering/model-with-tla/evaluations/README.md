# Maintainer evaluations

These documents define manual behavior evaluations for `model-with-tla`. They
are not runtime references, automated tests, or evidence that an agent executed
the cases.

- [Cases](cases.md) contains prompts without expected answers.
- [Oracles](oracles.md) contains maintainer review criteria.

An evaluation run gives an agent only the selected case. A maintainer compares
the response with the matching oracle afterward and records the model, harness,
date, and observed deviations outside these canonical case files.
