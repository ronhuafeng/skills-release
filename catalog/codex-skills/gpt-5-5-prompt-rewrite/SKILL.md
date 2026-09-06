---
name: gpt-5-5-prompt-rewrite
description: Manually rewrite an existing prompt into a concise, goal-first GPT-5.5 prompt. Use only when the user explicitly names gpt-5-5-prompt-rewrite or asks to rewrite a prompt specifically for GPT-5.5.
user-invocable: true
disable-model-invocation: true
---

# GPT-5.5 Prompt Rewrite

Rewrite the supplied prompt; do not execute it. Lead with the observable goal
and leave GPT-5.5 room to reason and choose tools.

1. Identify the outcome and evidence that proves it.
2. Preserve user intent, consequential constraints, required validation, side
   effect boundaries, compatibility requirements, and stopping conditions.
3. Remove duplicated constraints and implementation steps that are only one
   possible route. Keep exact names, APIs, schemas, commands, and formats only
   when correctness depends on them.
4. Do not invent requirements or factual claims. Ask for the smallest
   clarification only when a real conflict would change the task.
5. Return a self-contained rewrite directly. Use only the sections the prompt
   needs, and explain a change only when it may surprise the user.

Before returning, verify that the rewrite is shorter when practical, leads
with the result rather than procedure, preserves every consequential
requirement, exposes completion and validation, and needs no hidden context
from the original conversation.
