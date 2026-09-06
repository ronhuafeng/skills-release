---
status: accepted
---

# Use event messages for the visible message projection

The human-facing Visible Message Projection uses persisted
`event_msg.user_message` and `event_msg.agent_message` records, matching Codex's
`ThreadHistoryBuilder`. Model-history `response_item.message` records remain
available through the full-fidelity Rollout Reader but are not merged into this
projection. A message's local evidence identity is its session ID and source
line number; repeated text is not deduplicated by content. Only an explicit
`final_answer` phase is final, and absent or unfamiliar phases remain unknown.
This keeps lossless rollout access separate from the visible message view.
