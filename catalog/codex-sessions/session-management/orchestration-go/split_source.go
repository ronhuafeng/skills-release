package sessionmanagement

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"

	rollout "github.com/ronhuafeng/skills/harnesses/codex/rollout-go"
)

type splitSourceFormat struct {
	UsesOrdinals bool
}

type splitSourceValidator struct {
	sessionID    string
	recordCount  int
	usesOrdinals bool
}

func validateSplitSource(
	ctx context.Context,
	selected SelectedRollout,
) (splitSourceFormat, error) {
	validator := splitSourceValidator{sessionID: selected.SessionID}
	_, err := rollout.ScanRange(
		selected.Path,
		rollout.ScanCursor{NextLine: 1},
		selected.ThroughSourceOffset,
		func(record rollout.Record, _ rollout.ScanCursor) (bool, error) {
			if err := ctx.Err(); err != nil {
				return false, err
			}
			if err := validator.consume(selected.Path, record); err != nil {
				return false, err
			}
			return true, nil
		},
	)
	if err != nil {
		return splitSourceFormat{}, err
	}
	if validator.recordCount == 0 {
		return splitSourceFormat{}, fmt.Errorf("split source is empty")
	}
	return splitSourceFormat{UsesOrdinals: validator.usesOrdinals}, nil
}

func (validator *splitSourceValidator) consume(path string, record rollout.Record) error {
	ordinal, present, err := record.Ordinal()
	if err != nil {
		return fmt.Errorf("%s:%d: %w", path, record.Line, err)
	}
	if validator.recordCount == 0 {
		meta, err := rollout.DecodeSessionMeta(record)
		if err != nil {
			return fmt.Errorf("%s:%d: %w", path, record.Line, err)
		}
		if err := validateSplitRootMeta(meta, validator.sessionID); err != nil {
			return fmt.Errorf("%s:%d: %w", path, record.Line, err)
		}
		validator.usesOrdinals = present
		if meta.HistoryMode == "paginated" && !present {
			return fmt.Errorf("%s:%d: paginated source requires ordinals", path, record.Line)
		}
	} else {
		if record.Envelope != nil && record.Envelope.Type == "session_meta" {
			return fmt.Errorf("%s:%d: session_meta is only valid as the first record", path, record.Line)
		}
		if present != validator.usesOrdinals {
			return fmt.Errorf("%s:%d: source mixes records with and without ordinals", path, record.Line)
		}
	}
	if present && ordinal != uint64(validator.recordCount) {
		return fmt.Errorf(
			"%s:%d: source ordinal %d is not the expected %d",
			path,
			record.Line,
			ordinal,
			validator.recordCount,
		)
	}
	validator.recordCount++
	return nil
}

func validateSplitRootMeta(meta rollout.SessionMetaLine, sessionID string) error {
	if meta.ID != sessionID || meta.SessionID != sessionID {
		return fmt.Errorf("source filename, id, and session_id must identify the same session")
	}
	if meta.ForkedFromID != nil {
		return fmt.Errorf("split does not support forked_from_id lineage")
	}
	if meta.ForkedFromOrdinal != nil {
		return fmt.Errorf("split does not support forked_from_ordinal_exclusive lineage")
	}
	if meta.ParentThreadID != nil {
		return fmt.Errorf("split does not support parent_thread_id lineage")
	}
	if hasJSONValue(meta.HistoryBase) {
		return fmt.Errorf("split does not support history_base lineage")
	}
	if meta.SubagentHistoryStart != nil {
		return fmt.Errorf("split does not support subagent_history_start_ordinal lineage")
	}
	if meta.AgentNickname != nil || meta.AgentRole != nil || meta.AgentPath != nil {
		return fmt.Errorf("split does not support agent lineage metadata")
	}
	if meta.ThreadSource != nil && *meta.ThreadSource == "subagent" {
		return fmt.Errorf("split does not support subagent thread_source lineage")
	}
	if isSubagentSessionSource(meta.Source) {
		return fmt.Errorf("split does not support subagent source lineage")
	}
	return nil
}

func hasJSONValue(raw json.RawMessage) bool {
	return len(raw) > 0 && !bytes.Equal(bytes.TrimSpace(raw), []byte("null"))
}

func isSubagentSessionSource(raw json.RawMessage) bool {
	var object map[string]json.RawMessage
	return json.Unmarshal(raw, &object) == nil && object["subagent"] != nil
}
