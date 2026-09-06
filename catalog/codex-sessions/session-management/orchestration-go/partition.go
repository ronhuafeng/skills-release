package sessionmanagement

import (
	"bytes"
	"context"
	"crypto/sha256"
	"encoding/base64"
	"encoding/json"
	"fmt"
	"io"
	"os"
	"strings"
	"unicode/utf8"

	rollout "github.com/ronhuafeng/skills/harnesses/codex/rollout-go"
)

const (
	defaultPartitionWindowBytes = 64 * 1024
	maxPartitionWindowBytes     = 1024 * 1024
	partitionCursorVersion      = 3
)

type PartitionInspectRequest struct {
	CodexHome       string
	SessionID       string
	IncludeArchived bool
	WindowBytes     int
	Continuation    string
}

type PartitionCutCandidate struct {
	SourceLine            int    `json:"source_line"`
	Timestamp             string `json:"timestamp"`
	TurnID                string `json:"turn_id"`
	AnchorUserMessageLine int    `json:"anchor_user_message_line"`
}

type PartitionWindow struct {
	Source          SelectedRollout         `json:"source"`
	Sequence        int                     `json:"sequence"`
	StartSourceLine int                     `json:"start_source_line"`
	EndSourceLine   int                     `json:"end_source_line"`
	SemanticBytes   int                     `json:"semantic_bytes"`
	Records         []ContentRecord         `json:"records"`
	CutCandidates   []PartitionCutCandidate `json:"cut_candidates"`
	Oversized       bool                    `json:"oversized"`
	Continuation    string                  `json:"continuation,omitempty"`
	Receipt         *PartitionScanReceipt   `json:"receipt,omitempty"`
}

type PartitionScanReceipt struct {
	Source              SelectedRollout `json:"source"`
	FirstSourceLine     int             `json:"first_source_line"`
	LastSourceLine      int             `json:"last_source_line"`
	RawRecordCount      int             `json:"raw_record_count"`
	SemanticRecordCount int             `json:"semantic_record_count"`
	CutCandidateCount   int             `json:"cut_candidate_count"`
	TailOpen            bool            `json:"tail_open"`
}

type PartitionIntentPart struct {
	Title                 string `json:"title"`
	AnchorUserMessageLine int    `json:"anchor_user_message_line"`
}

type PartitionPlanRequest struct {
	Receipt PartitionScanReceipt  `json:"receipt"`
	Parts   []PartitionIntentPart `json:"parts"`
}

type PartitionPlanPart struct {
	PartID                string `json:"part_id"`
	Title                 string `json:"title"`
	AnchorUserMessageLine int    `json:"anchor_user_message_line"`
	StartSourceLine       int    `json:"start_source_line"`
	EndSourceLine         int    `json:"end_source_line"`
}

type PartitionPlan struct {
	Receipt PartitionScanReceipt `json:"receipt"`
	Parts   []PartitionPlanPart  `json:"parts"`
}

type partitionContinuation struct {
	Version       int                `json:"version"`
	Preflight     partitionPreflight `json:"preflight"`
	Position      rollout.ScanCursor `json:"position"`
	Sequence      int                `json:"sequence"`
	WindowBytes   int                `json:"window_bytes"`
	RawSeen       int                `json:"raw_seen"`
	SemanticSeen  int                `json:"semantic_seen"`
	CandidateSeen int                `json:"candidate_seen"`
	State         partitionScanState `json:"state"`
}

type partitionContinuationEnvelope struct {
	Payload string `json:"payload"`
	SHA256  string `json:"sha256"`
}

type partitionActiveTurn struct {
	TurnID          string `json:"turn_id"`
	StartSourceLine int    `json:"start_source_line"`
	StartTimestamp  string `json:"start_timestamp"`
	BeforeStartLine int    `json:"before_start_line"`
	FirstUserLine   int    `json:"first_user_line"`
	CrossesTool     bool   `json:"crosses_tool"`
}

type partitionScanState struct {
	ActiveTurn         *partitionActiveTurn `json:"active_turn,omitempty"`
	OpenCalls          map[string]string    `json:"open_calls"`
	SawTurn            bool                 `json:"saw_turn"`
	FirstUserLine      int                  `json:"first_user_line"`
	EligibleCandidates int                  `json:"eligible_candidates"`
	LastRecordLine     int                  `json:"last_record_line"`
}

type partitionCandidateFact struct {
	Candidate       PartitionCutCandidate
	BeforeStartLine int
}

func newPartitionScanState() partitionScanState {
	return partitionScanState{OpenCalls: map[string]string{}}
}

func InspectPartition(ctx context.Context, req PartitionInspectRequest) (PartitionWindow, error) {
	var cursor partitionContinuation
	if req.Continuation == "" {
		if req.WindowBytes == 0 {
			req.WindowBytes = defaultPartitionWindowBytes
		}
		if req.WindowBytes < 1 || req.WindowBytes > maxPartitionWindowBytes {
			return PartitionWindow{}, fmt.Errorf("window_bytes must be within 1..%d", maxPartitionWindowBytes)
		}
		preflight, err := preflightPartitionSource(ctx, contentSourceRequest{
			CodexHome: req.CodexHome, SessionID: req.SessionID,
			IncludeArchived: req.IncludeArchived,
		})
		if err != nil {
			return PartitionWindow{}, err
		}
		cursor = partitionContinuation{
			Version: partitionCursorVersion, Preflight: preflight,
			Position: rollout.ScanCursor{NextLine: 1}, Sequence: 1,
			WindowBytes: req.WindowBytes, State: newPartitionScanState(),
		}
	} else {
		if req.CodexHome != "" || req.SessionID != "" || req.IncludeArchived || req.WindowBytes != 0 {
			return PartitionWindow{}, fmt.Errorf("continuation cannot be combined with source selection or window_bytes")
		}
		decoded, err := decodePartitionContinuation(req.Continuation)
		if err != nil {
			return PartitionWindow{}, err
		}
		cursor = decoded
	}
	if err := validateContinuationSource(cursor); err != nil {
		return PartitionWindow{}, err
	}
	return readPartitionWindow(ctx, cursor)
}

func readPartitionWindow(ctx context.Context, cursor partitionContinuation) (PartitionWindow, error) {
	window := PartitionWindow{
		Source:   cursor.Preflight.Selected,
		Sequence: cursor.Sequence, StartSourceLine: cursor.Position.NextLine,
		Records: []ContentRecord{}, CutCandidates: []PartitionCutCandidate{},
	}
	usedBytes := 0
	lastLine := cursor.State.LastRecordLine

	next := cursor.Position
	var err error
	var deferredAt *rollout.ScanCursor
	next, err = rollout.ScanRange(
		cursor.Preflight.Selected.Path,
		cursor.Position,
		cursor.Preflight.Selected.ThroughSourceOffset,
		func(record rollout.Record, current rollout.ScanCursor) (bool, error) {
			if err := ctx.Err(); err != nil {
				return false, err
			}
			projected, err := record.Content()
			if err != nil {
				return false, fmt.Errorf("%s:%d: %w", cursor.Preflight.Selected.Path, record.Line, err)
			}
			var encoded []byte
			if projected != nil {
				encoded, err = json.Marshal(projected)
				if err != nil {
					return false, err
				}
				if len(window.Records) > 0 && usedBytes+len(encoded) > cursor.WindowBytes {
					deferred := current
					deferredAt = &deferred
					return false, nil
				}
			}
			cursor.RawSeen++
			fact, content, err := cursor.State.consume(cursor.Preflight.Selected.Path, record)
			if err != nil {
				return false, err
			}
			if content == nil {
				lastLine = record.Line
				if fact != nil {
					window.CutCandidates = append(window.CutCandidates, fact.Candidate)
					cursor.CandidateSeen++
				}
				return true, nil
			}
			cursor.SemanticSeen++
			if fact != nil {
				cursor.CandidateSeen++
			}
			lastLine = record.Line
			window.Records = append(window.Records, *content)
			if fact != nil {
				window.CutCandidates = append(window.CutCandidates, fact.Candidate)
			}
			usedBytes += len(encoded)
			if len(window.Records) == 1 && usedBytes > cursor.WindowBytes {
				window.Oversized = true
			}
			return usedBytes < cursor.WindowBytes, nil
		},
	)
	if err != nil {
		return PartitionWindow{}, err
	}
	if deferredAt != nil {
		next = *deferredAt
	}
	window.EndSourceLine = lastLine
	window.SemanticBytes = usedBytes
	cursor.Position = next
	if next.Offset == cursor.Preflight.Selected.ThroughSourceOffset {
		if err := cursor.State.validateSnapshot(cursor.Preflight.Selected.Path); err != nil {
			return PartitionWindow{}, err
		}
		if cursor.RawSeen != cursor.Preflight.RawRecordCount ||
			cursor.SemanticSeen != cursor.Preflight.SemanticCount ||
			cursor.CandidateSeen != cursor.Preflight.CandidateCount ||
			cursor.State.tailOpen() != cursor.Preflight.TailOpen {
			return PartitionWindow{}, fmt.Errorf("partition window coverage does not match preflight")
		}
		window.Receipt = &PartitionScanReceipt{
			Source:              cursor.Preflight.Selected,
			FirstSourceLine:     1,
			LastSourceLine:      cursor.Preflight.Selected.ThroughSourceLine,
			RawRecordCount:      cursor.RawSeen,
			SemanticRecordCount: cursor.SemanticSeen,
			CutCandidateCount:   cursor.CandidateSeen,
			TailOpen:            cursor.Preflight.TailOpen,
		}
	} else {
		cursor.Sequence++
		encoded, err := encodePartitionContinuation(cursor)
		if err != nil {
			return PartitionWindow{}, err
		}
		window.Continuation = encoded
	}
	if err := validateContinuationSource(cursor); err != nil {
		return PartitionWindow{}, err
	}
	return window, nil
}

func validateContinuationSource(cursor partitionContinuation) error {
	if cursor.Version != partitionCursorVersion || cursor.Sequence < 1 ||
		cursor.WindowBytes < 1 || cursor.WindowBytes > maxPartitionWindowBytes ||
		cursor.Position.Offset < 0 || cursor.Position.NextLine < 1 ||
		cursor.Position.Offset > cursor.Preflight.Selected.ThroughSourceOffset {
		return fmt.Errorf("partition continuation is invalid or incompatible")
	}
	info, err := os.Stat(cursor.Preflight.Selected.Path)
	if err != nil {
		return err
	}
	if !info.Mode().IsRegular() || info.Size() < cursor.Preflight.Selected.ThroughSourceOffset {
		return sourceChanged()
	}
	return nil
}

func encodePartitionContinuation(cursor partitionContinuation) (string, error) {
	payload, err := json.Marshal(cursor)
	if err != nil {
		return "", err
	}
	digest := sha256.Sum256(payload)
	raw, err := json.Marshal(partitionContinuationEnvelope{
		Payload: base64.RawURLEncoding.EncodeToString(payload),
		SHA256:  fmt.Sprintf("%x", digest[:]),
	})
	if err != nil {
		return "", err
	}
	return base64.RawURLEncoding.EncodeToString(raw), nil
}

func decodePartitionContinuation(value string) (partitionContinuation, error) {
	raw, err := base64.RawURLEncoding.DecodeString(value)
	if err != nil {
		return partitionContinuation{}, fmt.Errorf("partition continuation is invalid")
	}
	decoder := json.NewDecoder(bytes.NewReader(raw))
	decoder.DisallowUnknownFields()
	var envelope partitionContinuationEnvelope
	if err := decoder.Decode(&envelope); err != nil || !decoderAtEOF(decoder) || !validSHA256(envelope.SHA256) {
		return partitionContinuation{}, fmt.Errorf("partition continuation is invalid")
	}
	payload, err := base64.RawURLEncoding.DecodeString(envelope.Payload)
	if err != nil {
		return partitionContinuation{}, fmt.Errorf("partition continuation is invalid")
	}
	digest := sha256.Sum256(payload)
	if fmt.Sprintf("%x", digest[:]) != envelope.SHA256 {
		return partitionContinuation{}, fmt.Errorf("partition continuation is invalid")
	}
	decoder = json.NewDecoder(bytes.NewReader(payload))
	decoder.DisallowUnknownFields()
	var cursor partitionContinuation
	if err := decoder.Decode(&cursor); err != nil {
		return partitionContinuation{}, fmt.Errorf("partition continuation is invalid: %w", err)
	}
	if !decoderAtEOF(decoder) {
		return partitionContinuation{}, fmt.Errorf("partition continuation is invalid")
	}
	if cursor.State.OpenCalls == nil {
		cursor.State.OpenCalls = map[string]string{}
	}
	return cursor, nil
}

func decoderAtEOF(decoder *json.Decoder) bool {
	var trailing any
	return decoder.Decode(&trailing) == io.EOF
}

func PlanPartition(ctx context.Context, req PartitionPlanRequest) (PartitionPlan, error) {
	_, plan, err := planPartition(ctx, req)
	return plan, err
}

func planPartition(ctx context.Context, req PartitionPlanRequest) (partitionPreflight, PartitionPlan, error) {
	source, err := revalidatePartitionSource(ctx, req.Receipt.Source)
	if err != nil {
		return partitionPreflight{}, PartitionPlan{}, err
	}
	if req.Receipt.RawRecordCount != source.RawRecordCount ||
		req.Receipt.SemanticRecordCount != source.SemanticCount ||
		req.Receipt.CutCandidateCount != source.CandidateCount ||
		req.Receipt.TailOpen != source.TailOpen ||
		req.Receipt.FirstSourceLine != 1 ||
		req.Receipt.LastSourceLine != source.Selected.ThroughSourceLine {
		return partitionPreflight{}, PartitionPlan{}, fmt.Errorf("partition receipt does not match the current source")
	}
	parts, err := derivePartitionIntentParts(ctx, source, req.Parts)
	if err != nil {
		return partitionPreflight{}, PartitionPlan{}, err
	}
	return source, PartitionPlan{Receipt: req.Receipt, Parts: parts}, nil
}

func revalidatePartitionPlan(ctx context.Context, supplied PartitionPlan) (partitionPreflight, PartitionPlan, error) {
	intent := make([]PartitionIntentPart, 0, len(supplied.Parts))
	for _, part := range supplied.Parts {
		intent = append(intent, PartitionIntentPart{Title: part.Title, AnchorUserMessageLine: part.AnchorUserMessageLine})
	}
	source, current, err := planPartition(ctx, PartitionPlanRequest{Receipt: supplied.Receipt, Parts: intent})
	if err != nil {
		return partitionPreflight{}, PartitionPlan{}, err
	}
	suppliedJSON, err := json.Marshal(supplied)
	if err != nil {
		return partitionPreflight{}, PartitionPlan{}, err
	}
	currentJSON, err := json.Marshal(current)
	if err != nil {
		return partitionPreflight{}, PartitionPlan{}, err
	}
	if !bytes.Equal(suppliedJSON, currentJSON) {
		return partitionPreflight{}, PartitionPlan{}, fmt.Errorf("partition plan does not match the current source")
	}
	return source, current, nil
}

func derivePartitionIntentParts(
	ctx context.Context,
	source partitionPreflight,
	intent []PartitionIntentPart,
) ([]PartitionPlanPart, error) {
	if len(intent) == 0 {
		return nil, fmt.Errorf("partition requires at least one part")
	}
	anchors := make(map[int]int, len(intent))
	previousAnchor := 0
	for index, part := range intent {
		partID := fmt.Sprintf("P%03d", index+1)
		if strings.TrimSpace(part.Title) == "" || utf8.RuneCountInString(part.Title) > 120 || strings.ContainsAny(part.Title, "\r\n") {
			return nil, fmt.Errorf("%s title must be one line with 1..120 characters", partID)
		}
		if part.AnchorUserMessageLine <= previousAnchor {
			return nil, fmt.Errorf("part anchors must be unique and strictly increasing")
		}
		previousAnchor = part.AnchorUserMessageLine
		anchors[part.AnchorUserMessageLine] = index
	}

	state := newPartitionScanState()
	starts := make([]int, len(intent))
	ends := make([]int, len(intent))
	found := make([]bool, len(intent))
	firstBodyLine := 0
	lastBodyLine := 0
	recordIndex := 0
	_, err := rollout.ScanRange(source.Selected.Path, rollout.ScanCursor{NextLine: 1}, source.Selected.ThroughSourceOffset, func(record rollout.Record, _ rollout.ScanCursor) (bool, error) {
		if err := ctx.Err(); err != nil {
			return false, err
		}
		recordIndex++
		if recordIndex > 1 {
			if firstBodyLine == 0 {
				firstBodyLine = record.Line
			}
			lastBodyLine = record.Line
		}
		fact, _, err := state.consume(source.Selected.Path, record)
		if err != nil {
			return false, err
		}
		if fact == nil {
			return true, nil
		}
		index, selected := anchors[fact.Candidate.AnchorUserMessageLine]
		if !selected {
			return true, nil
		}
		found[index] = true
		if index == 0 {
			starts[index] = firstBodyLine
		} else {
			starts[index] = fact.Candidate.SourceLine
			ends[index-1] = fact.BeforeStartLine
		}
		return true, nil
	})
	if err != nil {
		return nil, err
	}
	if err := state.validateSnapshot(source.Selected.Path); err != nil {
		return nil, err
	}
	if firstBodyLine == 0 {
		return nil, fmt.Errorf("partition requires at least one source body record")
	}
	if intent[0].AnchorUserMessageLine != state.FirstUserLine {
		return nil, fmt.Errorf("P001 must anchor the first persisted user_message")
	}
	for index := range found {
		if !found[index] {
			return nil, fmt.Errorf("P%03d anchor must be the first persisted user_message in an eligible task_started turn", index+1)
		}
	}
	ends[len(ends)-1] = lastBodyLine
	parts := make([]PartitionPlanPart, 0, len(intent))
	for index, part := range intent {
		if starts[index] == 0 || ends[index] < starts[index] {
			return nil, fmt.Errorf("P%03d source range is invalid", index+1)
		}
		parts = append(parts, PartitionPlanPart{
			PartID: fmt.Sprintf("P%03d", index+1), Title: part.Title,
			AnchorUserMessageLine: part.AnchorUserMessageLine,
			StartSourceLine:       starts[index], EndSourceLine: ends[index],
		})
	}
	return parts, nil
}

func (state *partitionScanState) consume(
	path string,
	record rollout.Record,
) (*partitionCandidateFact, *ContentRecord, error) {
	if record.Err != nil {
		return nil, nil, fmt.Errorf("%s:%d: %w", path, record.Line, record.Err)
	}
	if record.Envelope != nil {
		if _, ok := rollout.ParseTimestamp(record.Envelope.Timestamp); !ok {
			return nil, nil, fmt.Errorf("%s:%d: timestamp must be RFC3339", path, record.Line)
		}
	}
	tool, err := record.ToolRecord()
	if err != nil {
		return nil, nil, fmt.Errorf("%s:%d: decode tool record: %w", path, record.Line, err)
	}
	if tool != nil {
		if strings.HasSuffix(tool.Type, "_output") {
			// Code-mode notify can persist multiple custom outputs for one call.
			// The first matching output closes the call; later custom outputs are
			// notifications and cannot establish a new open call by themselves.
			callType, exists := state.OpenCalls[tool.CallID]
			if !exists {
				if tool.Type != "custom_tool_call_output" {
					return nil, nil, fmt.Errorf("%s:%d: tool call %s has invalid source order or variant pairing", path, record.Line, tool.CallID)
				}
			} else if tool.Type != callType+"_output" {
				return nil, nil, fmt.Errorf("%s:%d: tool call %s has invalid source order or variant pairing", path, record.Line, tool.CallID)
			} else {
				delete(state.OpenCalls, tool.CallID)
			}
		} else {
			if _, exists := state.OpenCalls[tool.CallID]; exists {
				return nil, nil, fmt.Errorf("%s:%d: tool call_id has multiple call records", path, record.Line)
			}
			state.OpenCalls[tool.CallID] = tool.Type
		}
	}

	var fact *partitionCandidateFact
	turn, err := record.TurnRecord()
	if err != nil {
		return nil, nil, fmt.Errorf("%s:%d: decode turn lifecycle: %w", path, record.Line, err)
	}
	if turn != nil {
		switch turn.Type {
		case "task_started":
			// Codex history projection closes the current projected turn when a
			// later task_started arrives, even if no terminal event was persisted.
			// A still-open call blocks this boundary, then belongs to the closed
			// projection rather than poisoning every later boundary.
			crossesTool := len(state.OpenCalls) > 0
			clear(state.OpenCalls)
			state.SawTurn = true
			state.ActiveTurn = &partitionActiveTurn{
				TurnID: turn.TurnID, StartSourceLine: record.Line,
				StartTimestamp:  record.Envelope.Timestamp,
				BeforeStartLine: state.LastRecordLine, CrossesTool: crossesTool,
			}
		case "user_message":
			if state.ActiveTurn != nil && state.ActiveTurn.FirstUserLine == 0 {
				state.ActiveTurn.FirstUserLine = record.Line
				if state.FirstUserLine == 0 {
					state.FirstUserLine = record.Line
				}
				if record.Line == state.FirstUserLine || !state.ActiveTurn.CrossesTool {
					state.EligibleCandidates++
					fact = &partitionCandidateFact{
						Candidate: PartitionCutCandidate{
							SourceLine:            state.ActiveTurn.StartSourceLine,
							Timestamp:             state.ActiveTurn.StartTimestamp,
							TurnID:                state.ActiveTurn.TurnID,
							AnchorUserMessageLine: record.Line,
						},
						BeforeStartLine: state.ActiveTurn.BeforeStartLine,
					}
				}
			}
		case "task_complete":
			if state.ActiveTurn != nil && turn.TurnID == state.ActiveTurn.TurnID {
				state.ActiveTurn = nil
			}
		case "turn_aborted":
			if state.ActiveTurn != nil && (turn.TurnID == "" || turn.TurnID == state.ActiveTurn.TurnID) {
				state.ActiveTurn = nil
			}
		}
	}
	content, err := record.Content()
	if err != nil {
		return nil, nil, fmt.Errorf("%s:%d: %w", path, record.Line, err)
	}
	state.LastRecordLine = record.Line
	return fact, content, nil
}

func (state *partitionScanState) validateSnapshot(path string) error {
	if !state.SawTurn {
		return fmt.Errorf("%s: selected rollout prefix has no task_started lifecycle", path)
	}
	if state.FirstUserLine == 0 {
		return fmt.Errorf("partition requires at least one persisted user message")
	}
	if state.EligibleCandidates == 0 {
		return fmt.Errorf("partition requires at least one eligible part anchor")
	}
	return nil
}

func (state *partitionScanState) tailOpen() bool {
	return state.ActiveTurn != nil || len(state.OpenCalls) > 0
}
