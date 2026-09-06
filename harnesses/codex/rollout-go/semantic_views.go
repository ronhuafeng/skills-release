package rollout

import (
	"bytes"
	"encoding/json"
	"fmt"
)

type ToolRecord struct {
	Type   string
	CallID string
}

type TurnRecord struct {
	Type   string
	TurnID string
}

func decodeToolRecord(
	raw json.RawMessage,
) (kind string, callID string, recognized bool, err error) {
	var object map[string]json.RawMessage
	if err := json.Unmarshal(raw, &object); err != nil || object == nil {
		return "", "", false, fmt.Errorf("response_item payload must be an object")
	}
	kind, err = decodeRequiredString(object, "type")
	if err != nil {
		return "", "", false, fmt.Errorf("tool record type: %w", err)
	}
	switch kind {
	case "function_call",
		"custom_tool_call",
		"function_call_output",
		"custom_tool_call_output":
	default:
		return kind, "", false, nil
	}
	callID, err = decodeRequiredString(object, "call_id")
	if err != nil {
		return "", "", true, fmt.Errorf("tool record call_id: %w", err)
	}
	return kind, callID, true, nil
}

// ToolRecord returns one recognized tool call/output fact, or nil for other
// record variants.
func (record Record) ToolRecord() (*ToolRecord, error) {
	if record.Err != nil {
		return nil, record.Err
	}
	if record.Envelope == nil || record.Envelope.Type != "response_item" {
		return nil, nil
	}
	kind, callID, recognized, err := decodeToolRecord(record.Envelope.Payload)
	if err != nil {
		return nil, err
	}
	if !recognized {
		return nil, nil
	}
	return &ToolRecord{Type: kind, CallID: callID}, nil
}

// TurnRecord returns one recognized persisted turn lifecycle fact, or nil for
// other record variants. user_message carries no turn id.
func (record Record) TurnRecord() (*TurnRecord, error) {
	if record.Err != nil {
		return nil, record.Err
	}
	if record.Envelope == nil || record.Envelope.Type != "event_msg" {
		return nil, nil
	}
	kind, err := record.EventType()
	if err != nil {
		return nil, err
	}
	switch kind {
	case "user_message":
		return &TurnRecord{Type: kind}, nil
	case "task_started", "task_complete":
		var payload struct {
			TurnID *string `json:"turn_id"`
		}
		if err := json.Unmarshal(record.Envelope.Payload, &payload); err != nil {
			return nil, err
		}
		if payload.TurnID == nil || *payload.TurnID == "" {
			return nil, fmt.Errorf("%s turn_id is required", kind)
		}
		return &TurnRecord{Type: kind, TurnID: *payload.TurnID}, nil
	case "turn_aborted":
		var payload struct {
			TurnID *string `json:"turn_id"`
		}
		if err := json.Unmarshal(record.Envelope.Payload, &payload); err != nil {
			return nil, err
		}
		if payload.TurnID == nil {
			return &TurnRecord{Type: kind}, nil
		}
		return &TurnRecord{Type: kind, TurnID: *payload.TurnID}, nil
	default:
		return nil, nil
	}
}

// ProjectGeneratedSession returns one record for a standalone generated
// session. It rebinds thread identity, removes source lineage, and applies the
// generated rollout's optional dense ordinal.
func (record Record) ProjectGeneratedSession(
	targetID string,
	headerTimestamp string,
	ordinal *uint64,
) ([]byte, error) {
	if targetID == "" {
		return nil, fmt.Errorf("target thread id must be non-empty")
	}
	if record.Err != nil {
		return nil, record.Err
	}
	var envelope map[string]json.RawMessage
	if err := json.Unmarshal(record.Raw, &envelope); err != nil || envelope == nil {
		return nil, fmt.Errorf("record must be a JSON object")
	}
	var payload map[string]json.RawMessage
	if err := json.Unmarshal(record.Envelope.Payload, &payload); err != nil ||
		payload == nil {
		return nil, fmt.Errorf("payload must be an object")
	}
	changed := false
	if ordinal == nil {
		if _, present := envelope["ordinal"]; present {
			delete(envelope, "ordinal")
			changed = true
		}
	} else {
		envelope["ordinal"] = json.RawMessage(fmt.Sprintf("%d", *ordinal))
		changed = true
	}
	if record.Envelope.Type == "session_meta" {
		if err := replaceRequiredString(payload, "id", targetID); err != nil {
			return nil, err
		}
		if _, present := payload["session_id"]; present {
			if err := replaceRequiredString(payload, "session_id", targetID); err != nil {
				return nil, err
			}
		} else {
			payload["session_id"] = jsonString(targetID)
		}
		if headerTimestamp != "" {
			envelope["timestamp"] = jsonString(headerTimestamp)
			payload["timestamp"] = jsonString(headerTimestamp)
		}
		for _, field := range []string{
			"forked_from_id",
			"forked_from_ordinal_exclusive",
			"parent_thread_id",
			"history_base",
			"subagent_history_start_ordinal",
			"agent_nickname",
			"agent_role",
			"agent_type",
			"agent_path",
			"thread_source",
		} {
			delete(payload, field)
		}
		payload["source"] = json.RawMessage(`"mcp"`)
		if ordinal == nil {
			payload["history_mode"] = json.RawMessage(`"legacy"`)
		} else {
			payload["history_mode"] = json.RawMessage(`"paginated"`)
		}
		payload["context_window"] = json.RawMessage(
			fmt.Sprintf(`{"window_id":%q}`, targetID),
		)
		changed = true
	} else if record.Envelope.Type == "event_msg" {
		kind, err := eventTypeFromPayload(record.Envelope.Payload)
		if err != nil {
			return nil, fmt.Errorf("event_msg payload type is invalid: %w", err)
		}
		if kind == "thread_goal_updated" {
			if err := replaceRequiredString(payload, "threadId", targetID); err != nil {
				return nil, err
			}
			goal, present, err := nestedJSONObject(payload, "goal")
			if err != nil || !present {
				return nil, fmt.Errorf("thread_goal_updated goal must be an object")
			}
			if err := replaceRequiredString(goal, "threadId", targetID); err != nil {
				return nil, err
			}
			goalRaw, err := json.Marshal(goal)
			if err != nil {
				return nil, err
			}
			payload["goal"] = goalRaw
			changed = true
		}
	}
	if !changed {
		return bytes.Clone(record.Raw), nil
	}
	payloadRaw, err := json.Marshal(payload)
	if err != nil {
		return nil, err
	}
	envelope["payload"] = payloadRaw
	return json.Marshal(envelope)
}

func eventTypeFromPayload(raw json.RawMessage) (string, error) {
	var payload struct {
		Type *string `json:"type"`
	}
	if err := json.Unmarshal(raw, &payload); err != nil {
		return "", err
	}
	if payload.Type == nil || *payload.Type == "" {
		return "", fmt.Errorf("type must be a non-empty string")
	}
	return *payload.Type, nil
}

func replaceRequiredString(
	object map[string]json.RawMessage,
	key string,
	replacement string,
) error {
	raw, present := object[key]
	if !present {
		return fmt.Errorf("%s is required", key)
	}
	var value string
	if err := json.Unmarshal(raw, &value); err != nil || value == "" {
		return fmt.Errorf("%s must be a non-empty string", key)
	}
	object[key] = jsonString(replacement)
	return nil
}

// ValidateThreadIdentity verifies the filename, every session_meta, and every
// Goal identity against targetID.
func ValidateThreadIdentity(path string, targetID string) error {
	threadID, err := ThreadID(path)
	if err != nil {
		return err
	}
	if threadID != targetID {
		return fmt.Errorf("%s: rollout thread id %s does not match %s", path, threadID, targetID)
	}
	err = Scan(path, func(record Record) error {
		if record.Envelope == nil || record.Envelope.Type != "session_meta" {
			return nil
		}
		var payload struct {
			ID        *string `json:"id"`
			SessionID *string `json:"session_id"`
		}
		if err := json.Unmarshal(record.Envelope.Payload, &payload); err != nil ||
			payload.ID == nil || payload.SessionID == nil ||
			*payload.ID != targetID || *payload.SessionID != targetID {
			return fmt.Errorf("%s:%d: session_meta identity is inconsistent", path, record.Line)
		}
		return nil
	})
	if err != nil {
		return err
	}
	goals, err := GoalUpdates(path)
	if err != nil {
		return err
	}
	for _, goal := range goals {
		if goal.ThreadID != targetID || goal.Goal.ThreadID != targetID {
			return fmt.Errorf(
				"%s:%d: Goal identity is inconsistent",
				path,
				goal.SourceLine,
			)
		}
	}
	return nil
}
