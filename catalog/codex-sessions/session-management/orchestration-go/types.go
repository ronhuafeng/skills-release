package sessionmanagement

import rollout "github.com/ronhuafeng/skills/harnesses/codex/rollout-go"

type ContentKind = rollout.ContentKind
type ContentRecord = rollout.ContentRecord
type GoalContent = rollout.GoalContent

const (
	ContentUser       = rollout.ContentUser
	ContentCommentary = rollout.ContentCommentary
	ContentFinal      = rollout.ContentFinal
	ContentGoal       = rollout.ContentGoal
)

type SelectedRollout struct {
	SessionID           string `json:"session_id"`
	Timestamp           string `json:"timestamp"`
	CodexHome           string `json:"codex_home"`
	IncludeArchived     bool   `json:"include_archived"`
	Path                string `json:"path"`
	ThroughSourceLine   int    `json:"through_source_line"`
	ThroughSourceOffset int64  `json:"through_source_offset"`
	PrefixSHA256        string `json:"prefix_sha256"`
}
