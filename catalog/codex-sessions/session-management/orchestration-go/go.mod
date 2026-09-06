module github.com/ronhuafeng/skills/catalog/codex-sessions/session-management/orchestration-go

go 1.23.0

require (
	github.com/google/uuid v1.6.0
	github.com/ronhuafeng/llm-go/codexsdk v0.7.0
	github.com/ronhuafeng/skills/harnesses/codex/rollout-go v0.0.0
	golang.org/x/sys v0.34.0
)

require (
	github.com/google/jsonschema-go v0.4.3 // indirect
	github.com/ronhuafeng/skills/harnesses/codex/jsonl-go v0.0.0 // indirect
)

replace github.com/ronhuafeng/skills/harnesses/codex/jsonl-go => ../../../../harnesses/codex/jsonl-go

replace github.com/ronhuafeng/skills/harnesses/codex/rollout-go => ../../../../harnesses/codex/rollout-go
