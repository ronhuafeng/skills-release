---
name: skill-detect
description: Analyze Codex session traces for reusable workflow patterns and evidence-backed skill improvements. Use when the user wants to detect candidate skills, diagnose an existing skill from execution history, or distinguish workflow design problems from one-off execution mistakes.
---

# Skill Detect

Use raw session messages and tool results to identify the narrowest reusable
Skill improvement. Summaries and memories are leads, not proof. This Skill is
read-only; artifact changes require a separate implementation request.

1. Fix the sessions, repository scope, and existing Skill artifacts. State when
   required raw evidence is unavailable.
2. Build a compact timeline of intent, Skill use, corrections, failures,
   retries, validation, and outcome. Merge repeated evidence.
3. Identify each candidate's trigger, responsibility, input, output, completion
   evidence, and stop condition.
4. Separate Skill design problems from model judgment, tool failures,
   repository defects, and one-off preferences. Bind every finding to an
   observed correction, repeated friction, unsafe effect, missing validation,
   or successful reuse.
5. Prefer, in order: narrow an existing contract or gate; add a small helper
   for repeated deterministic testable work; create a new Skill only for a
   distinct task with a stable trigger and completion gate. Otherwise keep the
   lesson local or gather more evidence.
6. Check relevant Skills, commands, helpers, tests, and current validation
   before claiming a gap. Give every recommendation a realistic forward test.

Report high-confidence findings first with evidence, cause, smallest change,
verification, and regression risk. Summarize remaining candidates and evidence
gaps without dumping the raw trace. Stop rather than promote a claim whose
identity, provenance, or important facts cannot be verified.
