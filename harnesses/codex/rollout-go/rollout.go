package rollout

import (
	"bufio"
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"io/fs"
	"os"
	"path/filepath"
	"reflect"
	"regexp"
	"sort"
	"strings"
	"time"

	jsonl "github.com/ronhuafeng/skills/harnesses/codex/jsonl-go"
)

var rolloutFilenamePattern = regexp.MustCompile(`^rollout-([0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}-[0-9]{2}-[0-9]{2})-([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})\.jsonl$`)

// Record is one full-fidelity Raw Rollout Line plus optional decoded evidence.
type Record struct {
	Line     int
	Raw      json.RawMessage
	Envelope *Envelope
	Err      error
}

type ScanCursor = jsonl.Cursor

// Envelope is the observed common shape shared by rollout records.
type Envelope struct {
	Timestamp string
	Type      string
	Payload   json.RawMessage
}

// Filter is a recursive partial JSON object matched against a raw record.
type Filter map[string]any

// SessionMetaLine is the compatibility projection used by this repository.
// Complex values remain raw JSON so unrelated upstream additions stay harmless.
type SessionMetaLine struct {
	SessionID               string          `json:"session_id"`
	ID                      string          `json:"id"`
	ForkedFromID            *string         `json:"forked_from_id,omitempty"`
	ForkedFromOrdinal       *uint64         `json:"forked_from_ordinal_exclusive,omitempty"`
	ParentThreadID          *string         `json:"parent_thread_id,omitempty"`
	Timestamp               string          `json:"timestamp"`
	CWD                     string          `json:"cwd"`
	Originator              string          `json:"originator"`
	CLIVersion              string          `json:"cli_version"`
	Source                  json.RawMessage `json:"source"`
	ThreadSource            *string         `json:"thread_source,omitempty"`
	AgentNickname           *string         `json:"agent_nickname,omitempty"`
	AgentRole               *string         `json:"agent_role,omitempty"`
	AgentPath               *string         `json:"agent_path,omitempty"`
	ModelProvider           *string         `json:"model_provider,omitempty"`
	BaseInstructions        json.RawMessage `json:"base_instructions,omitempty"`
	DynamicTools            json.RawMessage `json:"dynamic_tools,omitempty"`
	SelectedCapabilityRoots json.RawMessage `json:"selected_capability_roots"`
	MemoryMode              *string         `json:"memory_mode,omitempty"`
	HistoryMode             string          `json:"history_mode"`
	HistoryBase             json.RawMessage `json:"history_base,omitempty"`
	SubagentHistoryStart    *uint64         `json:"subagent_history_start_ordinal,omitempty"`
	MultiAgentVersion       json.RawMessage `json:"multi_agent_version,omitempty"`
	ContextWindow           json.RawMessage `json:"context_window,omitempty"`
	Git                     json.RawMessage `json:"git,omitempty"`
}

// Ordinal returns the optional paginated-rollout ordinal on this record.
func (record Record) Ordinal() (uint64, bool, error) {
	if record.Err != nil {
		return 0, false, record.Err
	}
	var object map[string]json.RawMessage
	if err := json.Unmarshal(record.Raw, &object); err != nil || object == nil {
		return 0, false, fmt.Errorf("record must be a JSON object")
	}
	raw, present := object["ordinal"]
	if !present || bytes.Equal(bytes.TrimSpace(raw), []byte("null")) {
		return 0, false, nil
	}
	var ordinal uint64
	if err := json.Unmarshal(raw, &ordinal); err != nil {
		return 0, false, fmt.Errorf("ordinal must be a non-negative integer")
	}
	return ordinal, true, nil
}

// CurrentExecutionSettings is the latest persisted model and model-provider
// projection, with the source line that supplied each independent field.
type CurrentExecutionSettings struct {
	Model                   string
	ModelSourceLine         int
	ModelProvider           string
	ModelProviderSourceLine int
}

// VisibleMessage is one persisted human-facing event message.
type VisibleMessage struct {
	SourceLine        int             `json:"source_line"`
	Timestamp         string          `json:"timestamp"`
	Type              string          `json:"type"`
	ClientID          *string         `json:"client_id,omitempty"`
	Message           string          `json:"message"`
	Images            json.RawMessage `json:"images,omitempty"`
	ImageDetails      json.RawMessage `json:"image_details,omitempty"`
	LocalImages       json.RawMessage `json:"local_images,omitempty"`
	LocalImageDetails json.RawMessage `json:"local_image_details,omitempty"`
	TextElements      json.RawMessage `json:"text_elements,omitempty"`
	Phase             *string         `json:"phase,omitempty"`
	MemoryCitation    json.RawMessage `json:"memory_citation,omitempty"`
}

// ContentKind identifies one persisted record that carries task semantics.
type ContentKind string

const (
	ContentUser       ContentKind = "user"
	ContentCommentary ContentKind = "commentary"
	ContentFinal      ContentKind = "final"
	ContentGoal       ContentKind = "goal"
)

// GoalContent retains the semantic fields of one persisted Goal update.
type GoalContent struct {
	Objective       string `json:"objective"`
	Status          string `json:"status"`
	TokenBudget     *int64 `json:"token_budget,omitempty"`
	TokensUsed      *int64 `json:"tokens_used,omitempty"`
	TimeUsedSeconds *int64 `json:"time_used_seconds,omitempty"`
	CreatedAt       *int64 `json:"created_at,omitempty"`
	UpdatedAt       *int64 `json:"updated_at,omitempty"`
}

// ContentRecord is one source-located semantic record for journaling and
// objective segmentation. Storage and thread identity metadata are excluded.
type ContentRecord struct {
	SourceLine        int             `json:"source_line"`
	Timestamp         string          `json:"timestamp"`
	Kind              ContentKind     `json:"kind"`
	Text              string          `json:"text,omitempty"`
	Images            json.RawMessage `json:"images,omitempty"`
	ImageDetails      json.RawMessage `json:"image_details,omitempty"`
	LocalImages       json.RawMessage `json:"local_images,omitempty"`
	LocalImageDetails json.RawMessage `json:"local_image_details,omitempty"`
	TextElements      json.RawMessage `json:"text_elements,omitempty"`
	MemoryCitation    json.RawMessage `json:"memory_citation,omitempty"`
	Goal              *GoalContent    `json:"goal,omitempty"`
}

// ThreadGoal is the native persisted goal object.
type ThreadGoal struct {
	ThreadID        string `json:"threadId"`
	Objective       string `json:"objective"`
	Status          string `json:"status"`
	TokenBudget     *int64 `json:"tokenBudget,omitempty"`
	TokensUsed      int64  `json:"tokensUsed"`
	TimeUsedSeconds int64  `json:"timeUsedSeconds"`
	CreatedAt       int64  `json:"createdAt"`
	UpdatedAt       int64  `json:"updatedAt"`
}

// GoalUpdate is one persisted thread_goal_updated event with source evidence.
type GoalUpdate struct {
	SourceLine int        `json:"source_line"`
	Timestamp  string     `json:"timestamp"`
	Type       string     `json:"type"`
	ThreadID   string     `json:"threadId"`
	TurnID     *string    `json:"turnId,omitempty"`
	Goal       ThreadGoal `json:"goal"`
}

// RecordVariant counts one observed top-level and direct payload type pair.
type RecordVariant struct {
	Type        string
	PayloadType string
	Count       int
}

// FieldKind counts one normalized raw JSON path and value kind.
type FieldKind struct {
	Path  string
	Kind  string
	Count int
}

// SourceError identifies structural evidence that coverage could not inspect.
type SourceError struct {
	Line int
	Err  string
}

// Coverage is a structural view over every retained raw record.
type Coverage struct {
	Records    int
	Variants   []RecordVariant
	FieldKinds []FieldKind
	Errors     []SourceError
}

// StructuralError identifies the first row that prevents complete selection.
type StructuralError struct {
	Path string
	Line int
}

func (e *StructuralError) Error() string {
	return fmt.Sprintf("%s:%d: rollout row is not a JSON object", e.Path, e.Line)
}

// Scan visits every Raw Rollout Line in source order without retaining the
// complete file.
func Scan(path string, visit func(Record) error) error {
	return jsonl.Scan(path, func(line jsonl.Line) error {
		return visit(recordFromLine(line))
	})
}

func scanBytes(path string, content []byte, visit func(Record) error) error {
	reader := bufio.NewReader(bytes.NewReader(content))
	for lineNumber := 1; ; lineNumber++ {
		raw, readErr := reader.ReadBytes('\n')
		if len(raw) > 0 {
			if raw[len(raw)-1] == '\n' {
				raw = raw[:len(raw)-1]
			}
			if len(bytes.TrimSpace(raw)) > 0 {
				if err := visit(recordFromLine(jsonl.Line{
					Path: path, Number: lineNumber, Raw: raw,
				})); err != nil {
					return err
				}
			}
		}
		if readErr == nil {
			continue
		}
		if readErr == io.EOF {
			return nil
		}
		return readErr
	}
}

// ScanRange resumes one rollout scan through a fixed source byte boundary.
func ScanRange(
	path string,
	start ScanCursor,
	throughOffset int64,
	visit func(Record, ScanCursor) (bool, error),
) (ScanCursor, error) {
	return jsonl.ScanRange(path, start, throughOffset, func(line jsonl.Line, current jsonl.Cursor) (bool, error) {
		return visit(recordFromLine(line), current)
	})
}

func recordFromLine(line jsonl.Line) Record {
	record := Record{
		Line: line.Number,
		Raw:  json.RawMessage(bytes.Clone(line.Raw)),
	}
	record.Envelope, record.Err = decodeEnvelope(line.Raw)
	return record
}

func decodeEnvelope(raw []byte) (*Envelope, error) {
	var object map[string]json.RawMessage
	if err := json.Unmarshal(raw, &object); err != nil {
		return nil, err
	}
	if object == nil {
		return nil, fmt.Errorf("JSON value is not an object")
	}
	payload, present := object["payload"]
	if !present || bytes.Equal(bytes.TrimSpace(payload), []byte("null")) {
		return nil, fmt.Errorf("payload is required")
	}
	var payloadObject map[string]json.RawMessage
	if err := json.Unmarshal(payload, &payloadObject); err != nil || payloadObject == nil {
		return nil, fmt.Errorf("payload must be a JSON object")
	}
	envelope := &Envelope{Payload: bytes.Clone(payload)}
	var err error
	if envelope.Timestamp, err = decodeRequiredString(object, "timestamp"); err != nil {
		return nil, err
	}
	if envelope.Type, err = decodeRequiredString(object, "type"); err != nil {
		return nil, err
	}
	return envelope, nil
}

func decodeRequiredString(object map[string]json.RawMessage, field string) (string, error) {
	raw, present := object[field]
	if !present {
		return "", fmt.Errorf("%s is required", field)
	}
	var value string
	if err := json.Unmarshal(raw, &value); err != nil || bytes.Equal(bytes.TrimSpace(raw), []byte("null")) {
		return "", fmt.Errorf("%s must be a JSON string", field)
	}
	if value == "" {
		return "", fmt.Errorf("%s must be non-empty", field)
	}
	return value, nil
}

// ParseFilter decodes one JSON object used for recursive partial matching.
func ParseFilter(raw string) (Filter, error) {
	value, err := decodeJSON(strings.NewReader(raw))
	if err != nil {
		return nil, err
	}
	object, ok := value.(map[string]any)
	if !ok || object == nil {
		return nil, fmt.Errorf("filter root must be a JSON object")
	}
	return Filter(object), nil
}

// Select visits source-ordered records matching any filter. Filtered selection
// validates every row before it emits the first match, so callers never receive
// partial filtered output.
func Select(path string, filters []Filter, visit func(Record) error) error {
	if len(filters) > 0 {
		if err := Scan(path, func(record Record) error {
			value, err := decodeJSON(bytes.NewReader(record.Raw))
			if err != nil {
				return &StructuralError{Path: path, Line: record.Line}
			}
			object, ok := value.(map[string]any)
			if !ok || object == nil {
				return &StructuralError{Path: path, Line: record.Line}
			}
			return nil
		}); err != nil {
			return err
		}
	}
	return Scan(path, func(record Record) error {
		if len(filters) == 0 {
			return visit(record)
		}
		value, _ := decodeJSON(bytes.NewReader(record.Raw))
		object := value.(map[string]any)
		for _, filter := range filters {
			if partialMatch(object, map[string]any(filter)) {
				return visit(record)
			}
		}
		return nil
	})
}

// SessionMeta returns the complete initial persisted session_meta payload.
func SessionMeta(path string) (SessionMetaLine, error) {
	var metadata SessionMetaLine
	found := false
	err := Scan(path, func(record Record) error {
		if found {
			return nil
		}
		found = true
		decoded, err := DecodeSessionMeta(record)
		if err != nil {
			return fmt.Errorf("%s:%d: %w", path, record.Line, err)
		}
		metadata = decoded
		return nil
	})
	if err != nil {
		return SessionMetaLine{}, err
	}
	if !found {
		return SessionMetaLine{}, fmt.Errorf("%s: rollout is empty", path)
	}
	return metadata, nil
}

// DecodeSessionMeta decodes one canonical initial session_meta record.
func DecodeSessionMeta(record Record) (SessionMetaLine, error) {
	if record.Err != nil {
		return SessionMetaLine{}, record.Err
	}
	if record.Envelope.Type != "session_meta" {
		return SessionMetaLine{}, fmt.Errorf("first rollout record must be session_meta")
	}
	var object map[string]json.RawMessage
	if err := json.Unmarshal(record.Envelope.Payload, &object); err != nil || object == nil {
		return SessionMetaLine{}, fmt.Errorf("decode session_meta: payload must be an object")
	}
	if _, ok := object["session_id"]; !ok {
		id, ok := object["id"]
		if !ok {
			return SessionMetaLine{}, fmt.Errorf("decode session_meta: id is required")
		}
		object["session_id"] = bytes.Clone(id)
	}
	if _, ok := object["history_mode"]; !ok {
		object["history_mode"] = json.RawMessage(`"legacy"`)
	}
	if _, ok := object["source"]; !ok {
		object["source"] = json.RawMessage(`"vscode"`)
	}
	if _, ok := object["selected_capability_roots"]; !ok {
		object["selected_capability_roots"] = json.RawMessage(`[]`)
	}
	if _, ok := object["agent_role"]; !ok {
		if legacy, exists := object["agent_type"]; exists {
			object["agent_role"] = bytes.Clone(legacy)
		}
	}
	normalized, err := json.Marshal(object)
	if err != nil {
		return SessionMetaLine{}, fmt.Errorf("decode session_meta: %w", err)
	}
	var metadata SessionMetaLine
	if err := json.Unmarshal(normalized, &metadata); err != nil {
		return SessionMetaLine{}, fmt.Errorf("decode session_meta: %w", err)
	}
	for name, value := range map[string]string{
		"id": metadata.ID, "session_id": metadata.SessionID, "timestamp": metadata.Timestamp,
		"cwd": metadata.CWD, "originator": metadata.Originator, "cli_version": metadata.CLIVersion,
	} {
		if value == "" {
			return SessionMetaLine{}, fmt.Errorf("decode session_meta: %s is required", name)
		}
	}
	return metadata, nil
}

// CurrentExecutionSettings applies the same rollout-order authorities used by
// Codex thread metadata: session_meta and thread_settings_applied can update
// model provider, while turn_context and thread_settings_applied can update
// model. The two fields advance independently.
func ExecutionSettings(path string) (CurrentExecutionSettings, error) {
	var settings CurrentExecutionSettings
	canonicalID := ""
	err := Scan(path, func(record Record) error {
		if record.Err != nil {
			return fmt.Errorf("%s:%d: %w", path, record.Line, record.Err)
		}
		var payload map[string]json.RawMessage
		if err := json.Unmarshal(record.Envelope.Payload, &payload); err != nil || payload == nil {
			return fmt.Errorf("%s:%d: execution settings payload must be an object", path, record.Line)
		}
		switch record.Envelope.Type {
		case "session_meta":
			id, err := decodeRequiredString(payload, "id")
			if err != nil {
				return fmt.Errorf("%s:%d: session_meta id: %w", path, record.Line, err)
			}
			if canonicalID == "" {
				canonicalID = id
			}
			if id != canonicalID {
				return nil
			}
			provider, present, err := decodeOptionalString(payload, "model_provider")
			if err != nil {
				return fmt.Errorf("%s:%d: session_meta model_provider: %w", path, record.Line, err)
			}
			if present && provider != "" {
				settings.ModelProvider = provider
				settings.ModelProviderSourceLine = record.Line
			}
		case "turn_context":
			model, present, err := decodeOptionalString(payload, "model")
			if err != nil {
				return fmt.Errorf("%s:%d: turn_context model: %w", path, record.Line, err)
			}
			if present && model != "" {
				settings.Model = model
				settings.ModelSourceLine = record.Line
			}
		case "event_msg":
			eventType, present, err := decodeOptionalString(payload, "type")
			if err != nil {
				return fmt.Errorf("%s:%d: event_msg type: %w", path, record.Line, err)
			}
			if !present || eventType != "thread_settings_applied" {
				return nil
			}
			var applied map[string]json.RawMessage
			if err := json.Unmarshal(payload["thread_settings"], &applied); err != nil || applied == nil {
				return fmt.Errorf("%s:%d: thread_settings_applied thread_settings must be an object", path, record.Line)
			}
			model, present, err := decodeOptionalString(applied, "model")
			if err != nil {
				return fmt.Errorf("%s:%d: thread_settings_applied model: %w", path, record.Line, err)
			}
			if present && model != "" {
				settings.Model = model
				settings.ModelSourceLine = record.Line
			}
			provider, present, err := decodeOptionalString(applied, "model_provider_id")
			if err != nil {
				return fmt.Errorf("%s:%d: thread_settings_applied model_provider_id: %w", path, record.Line, err)
			}
			if present && provider != "" {
				settings.ModelProvider = provider
				settings.ModelProviderSourceLine = record.Line
			}
		}
		return nil
	})
	if err != nil {
		return CurrentExecutionSettings{}, err
	}
	return settings, nil
}

func decodeOptionalString(object map[string]json.RawMessage, field string) (string, bool, error) {
	raw, present := object[field]
	if !present || bytes.Equal(bytes.TrimSpace(raw), []byte("null")) {
		return "", false, nil
	}
	var value string
	if err := json.Unmarshal(raw, &value); err != nil {
		return "", true, fmt.Errorf("must be a JSON string")
	}
	return value, true, nil
}

// RebindResumeAndIndexedCWD reads one rollout snapshot and returns its rebound
// transport projection.
func RebindResumeAndIndexedCWD(path string, cwd string) ([]byte, error) {
	content, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	return RebindResumeAndIndexedCWDBytes(path, content, cwd)
}

// RebindResumeAndIndexedCWDBytes returns a JSONL transport projection whose
// Default Resume CWD and Indexed Thread CWD resolve to cwd. Intermediate
// settings plus historical turn and world-state context remain raw.
func RebindResumeAndIndexedCWDBytes(path string, content []byte, cwd string) ([]byte, error) {
	if cwd == "" {
		return nil, fmt.Errorf("destination cwd must be non-empty")
	}
	scan := func(visit func(Record) error) error {
		return scanBytes(path, content, visit)
	}
	firstSessionMetaLine := 0
	lastIndexedCWDWriterLine := 0
	canonicalID := ""
	err := scan(func(record Record) error {
		if record.Err != nil {
			return fmt.Errorf("%s:%d: %w", path, record.Line, record.Err)
		}
		location, present, err := locateIndexedCWDWriter(path, record)
		if err != nil {
			return err
		}
		if record.Envelope.Type == "session_meta" && firstSessionMetaLine == 0 && !present {
			return fmt.Errorf("%s:%d: initial session_meta cwd must be non-empty", path, record.Line)
		}
		if !present {
			return nil
		}
		if record.Envelope.Type == "session_meta" {
			id, err := decodeRequiredString(location.payload, "id")
			if err != nil {
				return fmt.Errorf("%s:%d: session_meta id: %w", path, record.Line, err)
			}
			if firstSessionMetaLine == 0 {
				firstSessionMetaLine = record.Line
				canonicalID = id
			}
			if id != canonicalID {
				return nil
			}
		}
		lastIndexedCWDWriterLine = record.Line
		return nil
	})
	if err != nil {
		return nil, err
	}
	if firstSessionMetaLine == 0 {
		return nil, fmt.Errorf("%s: rollout has no session_meta", path)
	}

	var output bytes.Buffer
	err = scan(func(record Record) error {
		if record.Line != firstSessionMetaLine && record.Line != lastIndexedCWDWriterLine {
			_, _ = output.Write(record.Raw)
			_ = output.WriteByte('\n')
			return nil
		}
		location, present, err := locateIndexedCWDWriter(path, record)
		if err != nil {
			return err
		}
		if !present {
			_, _ = output.Write(record.Raw)
			_ = output.WriteByte('\n')
			return nil
		}
		var current string
		if err := json.Unmarshal(location.target["cwd"], &current); err != nil {
			return fmt.Errorf("%s:%d: indexed cwd must be a string", path, record.Line)
		}
		if current == cwd {
			_, _ = output.Write(record.Raw)
			_ = output.WriteByte('\n')
			return nil
		}
		location.target["cwd"] = jsonString(cwd)
		if err := location.rebuild(); err != nil {
			return fmt.Errorf("%s:%d: encode indexed cwd nesting: %w", path, record.Line, err)
		}
		payloadRaw, err := json.Marshal(location.payload)
		if err != nil {
			return fmt.Errorf("%s:%d: encode indexed cwd payload: %w", path, record.Line, err)
		}
		location.object["payload"] = payloadRaw
		rewritten, err := json.Marshal(location.object)
		if err != nil {
			return fmt.Errorf("%s:%d: encode indexed cwd record: %w", path, record.Line, err)
		}
		_, _ = output.Write(rewritten)
		_ = output.WriteByte('\n')
		return nil
	})
	if err != nil {
		return nil, err
	}
	return output.Bytes(), nil
}

type indexedCWDWriter struct {
	object  map[string]json.RawMessage
	payload map[string]json.RawMessage
	target  map[string]json.RawMessage
	rebuild func() error
}

func locateIndexedCWDWriter(path string, record Record) (indexedCWDWriter, bool, error) {
	switch record.Envelope.Type {
	case "session_meta", "event_msg":
	default:
		return indexedCWDWriter{}, false, nil
	}
	var object map[string]json.RawMessage
	if err := json.Unmarshal(record.Raw, &object); err != nil || object == nil {
		return indexedCWDWriter{}, false, fmt.Errorf("%s:%d: indexed cwd record must be an object", path, record.Line)
	}
	var payload map[string]json.RawMessage
	if err := json.Unmarshal(record.Envelope.Payload, &payload); err != nil || payload == nil {
		return indexedCWDWriter{}, false, fmt.Errorf("%s:%d: indexed cwd payload must be an object", path, record.Line)
	}
	direct := indexedCWDWriter{object: object, payload: payload, target: payload, rebuild: func() error { return nil }}
	switch record.Envelope.Type {
	case "session_meta":
		var cwd string
		if err := json.Unmarshal(payload["cwd"], &cwd); err != nil {
			return indexedCWDWriter{}, false, fmt.Errorf("%s:%d: session_meta cwd must be a string", path, record.Line)
		}
		if cwd == "" {
			return indexedCWDWriter{}, false, nil
		}
		return direct, true, nil
	case "event_msg":
		var kind string
		if err := json.Unmarshal(payload["type"], &kind); err != nil || kind != "thread_settings_applied" {
			return indexedCWDWriter{}, false, nil
		}
		settings, present, err := nestedJSONObject(payload, "thread_settings")
		if err != nil {
			return indexedCWDWriter{}, false, fmt.Errorf("%s:%d: thread_settings_applied: %w", path, record.Line, err)
		}
		if !present || settings["cwd"] == nil {
			return indexedCWDWriter{}, false, nil
		}
		return indexedCWDWriter{
			object: object, payload: payload, target: settings,
			rebuild: func() error {
				raw, err := json.Marshal(settings)
				if err == nil {
					payload["thread_settings"] = raw
				}
				return err
			},
		}, true, nil
	}
	return indexedCWDWriter{}, false, nil
}

func nestedJSONObject(parent map[string]json.RawMessage, field string) (map[string]json.RawMessage, bool, error) {
	raw, present := parent[field]
	if !present {
		return nil, false, nil
	}
	var object map[string]json.RawMessage
	if err := json.Unmarshal(raw, &object); err != nil || object == nil {
		return nil, false, fmt.Errorf("%s must be an object", field)
	}
	return object, true, nil
}

func jsonString(value string) json.RawMessage {
	encoded, _ := json.Marshal(value)
	return encoded
}

func validateEnvelope(path string, record Record) error {
	if record.Err != nil {
		return fmt.Errorf("%s:%d: %w", path, record.Line, record.Err)
	}
	if record.Envelope.Timestamp != "" {
		if _, ok := ParseTimestamp(record.Envelope.Timestamp); !ok {
			return fmt.Errorf("%s:%d: timestamp must be RFC3339", path, record.Line)
		}
	}
	return nil
}

// VisibleMessages projects only authoritative event_msg user/agent messages.
func VisibleMessages(path string) ([]VisibleMessage, error) {
	messages := []VisibleMessage{}
	err := Scan(path, func(record Record) error {
		if err := validateEnvelope(path, record); err != nil {
			return err
		}
		if record.Envelope == nil || record.Envelope.Type != "event_msg" {
			return nil
		}
		kind, err := eventType(path, record)
		if err != nil {
			return err
		}
		if kind != "user_message" && kind != "agent_message" {
			return nil
		}
		var payload struct {
			ClientID          *string         `json:"client_id"`
			Message           *string         `json:"message"`
			Images            json.RawMessage `json:"images"`
			ImageDetails      json.RawMessage `json:"image_details"`
			LocalImages       json.RawMessage `json:"local_images"`
			LocalImageDetails json.RawMessage `json:"local_image_details"`
			TextElements      json.RawMessage `json:"text_elements"`
			Phase             *string         `json:"phase"`
			MemoryCitation    json.RawMessage `json:"memory_citation"`
		}
		if err := json.Unmarshal(record.Envelope.Payload, &payload); err != nil {
			return fmt.Errorf("%s:%d: decode event_msg.%s: %w", path, record.Line, kind, err)
		}
		if payload.Message == nil {
			return fmt.Errorf("%s:%d: decode event_msg.%s: message must be a string", path, record.Line, kind)
		}
		if record.Envelope.Timestamp == "" {
			return fmt.Errorf("%s:%d: decode event_msg.%s: timestamp is required", path, record.Line, kind)
		}
		message := VisibleMessage{
			SourceLine: record.Line,
			Timestamp:  record.Envelope.Timestamp,
			Type:       kind,
			Message:    *payload.Message,
		}
		if kind == "user_message" {
			message.ClientID = payload.ClientID
			message.Images = payload.Images
			message.ImageDetails = payload.ImageDetails
			message.LocalImages = payload.LocalImages
			message.LocalImageDetails = payload.LocalImageDetails
			message.TextElements = payload.TextElements
		} else {
			message.Phase = payload.Phase
			message.MemoryCitation = payload.MemoryCitation
		}
		messages = append(messages, message)
		return nil
	})
	if err != nil {
		return nil, err
	}
	return messages, nil
}

// Content returns this record's task-semantic projection, or nil when the
// record is not user, commentary, final, or Goal content.
func (record Record) Content() (*ContentRecord, error) {
	if record.Err != nil {
		return nil, record.Err
	}
	if record.Envelope == nil || record.Envelope.Type != "event_msg" {
		return nil, nil
	}
	kind, err := record.EventType()
	if err != nil {
		return nil, fmt.Errorf("decode event_msg: %w", err)
	}
	if kind != "user_message" && kind != "agent_message" && kind != "thread_goal_updated" {
		return nil, nil
	}
	if _, ok := ParseTimestamp(record.Envelope.Timestamp); !ok {
		return nil, fmt.Errorf("decode event_msg.%s: timestamp must be RFC3339", kind)
	}
	switch kind {
	case "user_message":
		content, err := decodeContentMessage(record, ContentUser)
		if err != nil {
			return nil, fmt.Errorf("decode event_msg.%s: %w", kind, err)
		}
		return &content, nil
	case "agent_message":
		var phase struct {
			Phase *string `json:"phase"`
		}
		if err := json.Unmarshal(record.Envelope.Payload, &phase); err != nil {
			return nil, fmt.Errorf("decode event_msg.%s: %w", kind, err)
		}
		contentKind := ContentKind("")
		if phase.Phase != nil {
			switch *phase.Phase {
			case "commentary":
				contentKind = ContentCommentary
			case "final_answer":
				contentKind = ContentFinal
			}
		}
		if contentKind == "" {
			return nil, nil
		}
		content, err := decodeContentMessage(record, contentKind)
		if err != nil {
			return nil, fmt.Errorf("decode event_msg.%s: %w", kind, err)
		}
		return &content, nil
	case "thread_goal_updated":
		var payload struct {
			Goal *struct {
				Objective       string `json:"objective"`
				Status          string `json:"status"`
				TokenBudget     *int64 `json:"tokenBudget"`
				TokensUsed      *int64 `json:"tokensUsed"`
				TimeUsedSeconds *int64 `json:"timeUsedSeconds"`
				CreatedAt       *int64 `json:"createdAt"`
				UpdatedAt       *int64 `json:"updatedAt"`
			} `json:"goal"`
		}
		if err := json.Unmarshal(record.Envelope.Payload, &payload); err != nil {
			return nil, fmt.Errorf("decode event_msg.%s: %w", kind, err)
		}
		if payload.Goal == nil || strings.TrimSpace(payload.Goal.Objective) == "" || strings.TrimSpace(payload.Goal.Status) == "" {
			return nil, fmt.Errorf("decode event_msg.%s: goal objective and status are required", kind)
		}
		return &ContentRecord{
			SourceLine: record.Line, Timestamp: record.Envelope.Timestamp,
			Kind: ContentGoal,
			Goal: &GoalContent{
				Objective: payload.Goal.Objective, Status: payload.Goal.Status,
				TokenBudget: payload.Goal.TokenBudget, TokensUsed: payload.Goal.TokensUsed,
				TimeUsedSeconds: payload.Goal.TimeUsedSeconds,
				CreatedAt:       payload.Goal.CreatedAt, UpdatedAt: payload.Goal.UpdatedAt,
			},
		}, nil
	}
	return nil, nil
}

func decodeContentMessage(record Record, kind ContentKind) (ContentRecord, error) {
	var payload struct {
		Message           *string         `json:"message"`
		Images            json.RawMessage `json:"images"`
		ImageDetails      json.RawMessage `json:"image_details"`
		LocalImages       json.RawMessage `json:"local_images"`
		LocalImageDetails json.RawMessage `json:"local_image_details"`
		TextElements      json.RawMessage `json:"text_elements"`
		MemoryCitation    json.RawMessage `json:"memory_citation"`
	}
	if err := json.Unmarshal(record.Envelope.Payload, &payload); err != nil {
		return ContentRecord{}, err
	}
	if payload.Message == nil {
		return ContentRecord{}, fmt.Errorf("message must be a string")
	}
	return ContentRecord{
		SourceLine: record.Line, Timestamp: record.Envelope.Timestamp, Kind: kind, Text: *payload.Message,
		Images: payload.Images, ImageDetails: payload.ImageDetails,
		LocalImages: payload.LocalImages, LocalImageDetails: payload.LocalImageDetails,
		TextElements: payload.TextElements, MemoryCitation: payload.MemoryCitation,
	}, nil
}

func eventType(path string, record Record) (string, error) {
	kind, err := record.EventType()
	if err != nil {
		return "", fmt.Errorf("%s:%d: decode event_msg: %w", path, record.Line, err)
	}
	return kind, nil
}

// EventType returns the native event_msg payload type.
func (record Record) EventType() (string, error) {
	if record.Err != nil {
		return "", record.Err
	}
	if record.Envelope == nil || record.Envelope.Type != "event_msg" {
		return "", fmt.Errorf("record is not event_msg")
	}
	return eventTypeFromPayload(record.Envelope.Payload)
}

// GoalUpdates selects only persisted thread_goal_updated facts.
func GoalUpdates(path string) ([]GoalUpdate, error) {
	updates := []GoalUpdate{}
	err := Scan(path, func(record Record) error {
		if err := validateEnvelope(path, record); err != nil {
			return err
		}
		if record.Envelope.Type != "event_msg" {
			return nil
		}
		kind, err := eventType(path, record)
		if err != nil {
			return err
		}
		if kind != "thread_goal_updated" {
			return nil
		}
		var payload struct {
			ThreadID *string         `json:"threadId"`
			TurnID   *string         `json:"turnId"`
			Goal     json.RawMessage `json:"goal"`
		}
		if err := json.Unmarshal(record.Envelope.Payload, &payload); err != nil {
			return fmt.Errorf("%s:%d: decode event_msg.%s: %w", path, record.Line, kind, err)
		}
		if payload.ThreadID == nil || *payload.ThreadID == "" || len(payload.Goal) == 0 || bytes.Equal(bytes.TrimSpace(payload.Goal), []byte("null")) {
			return fmt.Errorf("%s:%d: decode event_msg.%s: threadId and goal are required", path, record.Line, kind)
		}
		goal, err := decodeThreadGoal(payload.Goal)
		if err != nil {
			return fmt.Errorf("%s:%d: decode event_msg.%s: %w", path, record.Line, kind, err)
		}
		updates = append(updates, GoalUpdate{
			SourceLine: record.Line, Timestamp: record.Envelope.Timestamp, Type: kind,
			ThreadID: *payload.ThreadID, TurnID: payload.TurnID, Goal: goal,
		})
		return nil
	})
	if err != nil {
		return nil, err
	}
	return updates, nil
}

func decodeThreadGoal(raw json.RawMessage) (ThreadGoal, error) {
	var fields struct {
		ThreadID        *string `json:"threadId"`
		Objective       *string `json:"objective"`
		Status          *string `json:"status"`
		TokenBudget     *int64  `json:"tokenBudget"`
		TokensUsed      *int64  `json:"tokensUsed"`
		TimeUsedSeconds *int64  `json:"timeUsedSeconds"`
		CreatedAt       *int64  `json:"createdAt"`
		UpdatedAt       *int64  `json:"updatedAt"`
	}
	if err := json.Unmarshal(raw, &fields); err != nil {
		return ThreadGoal{}, err
	}
	if fields.ThreadID == nil || *fields.ThreadID == "" || fields.Objective == nil || *fields.Objective == "" {
		return ThreadGoal{}, fmt.Errorf("goal.threadId and goal.objective are required")
	}
	if fields.Status == nil || fields.TokensUsed == nil || fields.TimeUsedSeconds == nil || fields.CreatedAt == nil || fields.UpdatedAt == nil {
		return ThreadGoal{}, fmt.Errorf("goal.status, goal.tokensUsed, goal.timeUsedSeconds, goal.createdAt, and goal.updatedAt are required")
	}
	switch *fields.Status {
	case "active", "paused", "blocked", "usageLimited", "budgetLimited", "complete":
	default:
		return ThreadGoal{}, fmt.Errorf("goal.status is invalid")
	}
	return ThreadGoal{
		ThreadID: *fields.ThreadID, Objective: *fields.Objective, Status: *fields.Status,
		TokenBudget: fields.TokenBudget, TokensUsed: *fields.TokensUsed,
		TimeUsedSeconds: *fields.TimeUsedSeconds, CreatedAt: *fields.CreatedAt, UpdatedAt: *fields.UpdatedAt,
	}, nil
}

// Coverage inventories variants and normalized JSON field/value shapes.
func InspectCoverage(path string) (Coverage, error) {
	coverage := Coverage{}
	variantCounts := map[[2]string]int{}
	fieldCounts := map[[2]string]int{}
	err := Scan(path, func(record Record) error {
		coverage.Records++
		if record.Err != nil {
			coverage.Errors = append(coverage.Errors, SourceError{Line: record.Line, Err: record.Err.Error()})
		}
		value, err := decodeJSON(bytes.NewReader(record.Raw))
		if err != nil {
			if record.Err == nil {
				coverage.Errors = append(coverage.Errors, SourceError{Line: record.Line, Err: err.Error()})
			}
			return nil
		}
		object, ok := value.(map[string]any)
		if !ok {
			if record.Err == nil {
				coverage.Errors = append(coverage.Errors, SourceError{Line: record.Line, Err: "JSON value is not an object"})
			}
			return nil
		}
		recordType, _ := object["type"].(string)
		payloadType := ""
		if payload, ok := object["payload"].(map[string]any); ok {
			payloadType, _ = payload["type"].(string)
		}
		variantCounts[[2]string{recordType, payloadType}]++
		for key, child := range object {
			collectFieldKinds(child, key, fieldCounts)
		}
		return nil
	})
	if err != nil {
		return Coverage{}, err
	}
	for key, count := range variantCounts {
		coverage.Variants = append(coverage.Variants, RecordVariant{Type: key[0], PayloadType: key[1], Count: count})
	}
	sort.Slice(coverage.Variants, func(i, j int) bool {
		if coverage.Variants[i].Type == coverage.Variants[j].Type {
			return coverage.Variants[i].PayloadType < coverage.Variants[j].PayloadType
		}
		return coverage.Variants[i].Type < coverage.Variants[j].Type
	})
	for key, count := range fieldCounts {
		coverage.FieldKinds = append(coverage.FieldKinds, FieldKind{Path: key[0], Kind: key[1], Count: count})
	}
	sort.Slice(coverage.FieldKinds, func(i, j int) bool {
		if coverage.FieldKinds[i].Path == coverage.FieldKinds[j].Path {
			return coverage.FieldKinds[i].Kind < coverage.FieldKinds[j].Kind
		}
		return coverage.FieldKinds[i].Path < coverage.FieldKinds[j].Path
	})
	return coverage, nil
}

func collectFieldKinds(value any, path string, counts map[[2]string]int) {
	kind := jsonKind(value)
	counts[[2]string{path, kind}]++
	switch typed := value.(type) {
	case map[string]any:
		for key, child := range typed {
			collectFieldKinds(child, path+"."+key, counts)
		}
	case []any:
		for _, child := range typed {
			collectFieldKinds(child, path+".[]", counts)
		}
	}
}

func jsonKind(value any) string {
	switch value.(type) {
	case nil:
		return "null"
	case bool:
		return "boolean"
	case json.Number:
		return "number"
	case string:
		return "string"
	case []any:
		return "array"
	case map[string]any:
		return "object"
	default:
		return "unknown"
	}
}

// ResolveSessionFile resolves an id from active sessions and then, when
// requested, archived sessions. Active always wins.
func ResolveSessionFile(codexHome string, sessionID string, includeArchived bool) (string, error) {
	if !filepath.IsAbs(codexHome) || codexHome != filepath.Clean(codexHome) {
		return "", fmt.Errorf("codex home must be an absolute clean path")
	}
	if sessionID == "" || sessionID != strings.TrimSpace(sessionID) {
		return "", fmt.Errorf("session id is required")
	}
	roots := []string{filepath.Join(codexHome, "sessions")}
	if includeArchived {
		roots = append(roots, filepath.Join(codexHome, "archived_sessions"))
	}
	for _, root := range roots {
		path, found, err := findSessionFile(root, sessionID)
		if err != nil {
			return "", err
		}
		if found {
			return path, nil
		}
	}
	return "", fmt.Errorf("rollout session not found: %s", sessionID)
}

func findSessionFile(root string, sessionID string) (string, bool, error) {
	if _, err := os.Stat(root); err != nil {
		if os.IsNotExist(err) {
			return "", false, nil
		}
		return "", false, err
	}
	matches := []string{}
	err := filepath.WalkDir(root, func(path string, entry fs.DirEntry, walkErr error) error {
		if walkErr != nil {
			return walkErr
		}
		if entry.IsDir() {
			return nil
		}
		if filepath.Ext(path) == ".jsonl" && filenameSessionID(path) == sessionID {
			matches = append(matches, path)
		}
		return nil
	})
	if err != nil {
		return "", false, err
	}
	if len(matches) == 0 {
		return "", false, nil
	}
	sort.Strings(matches)
	if len(matches) > 1 {
		return "", false, fmt.Errorf("session id %q is ambiguous", sessionID)
	}
	return matches[0], true, nil
}

// ThreadID returns the explicit current or pre-envelope rollout identity and
// verifies it against the native rollout filename.
func ThreadID(path string) (string, error) {
	filenameID := filenameSessionID(path)
	if filenameID == "" {
		return "", fmt.Errorf("%s: rollout filename has no thread id", path)
	}
	var first Record
	found := false
	if err := Scan(path, func(record Record) error {
		if !found {
			first = record
			found = true
		}
		return nil
	}); err != nil {
		return "", err
	}
	if !found {
		return "", fmt.Errorf("%s: rollout is empty", path)
	}
	if first.Envelope != nil {
		meta, err := SessionMeta(path)
		if err != nil {
			return "", err
		}
		if meta.ID != filenameID {
			return "", fmt.Errorf("%s:%d: session_meta id %s does not match filename id %s", path, first.Line, meta.ID, filenameID)
		}
		return meta.ID, nil
	}
	var legacy map[string]json.RawMessage
	if err := json.Unmarshal(first.Raw, &legacy); err != nil || legacy == nil {
		return "", fmt.Errorf("%s:%d: %w", path, first.Line, first.Err)
	}
	if _, hasType := legacy["type"]; hasType {
		return "", fmt.Errorf("%s:%d: %w", path, first.Line, first.Err)
	}
	if _, hasPayload := legacy["payload"]; hasPayload {
		return "", fmt.Errorf("%s:%d: %w", path, first.Line, first.Err)
	}
	id, err := decodeRequiredString(legacy, "id")
	if err != nil {
		return "", fmt.Errorf("%s:%d: first rollout record has no thread id", path, first.Line)
	}
	if id != filenameID {
		return "", fmt.Errorf("%s:%d: pre-envelope id %s does not match filename id %s", path, first.Line, id, filenameID)
	}
	return id, nil
}

func filenameSessionID(path string) string {
	match := rolloutFilenamePattern.FindStringSubmatch(filepath.Base(path))
	if len(match) != 3 {
		return ""
	}
	if _, err := time.Parse("2006-01-02T15-04-05", match[1]); err != nil {
		return ""
	}
	return match[2]
}

// SessionFileTimestamp returns the timestamp encoded by a native rollout
// filename without consulting session metadata.
func SessionFileTimestamp(path string) (string, error) {
	match := rolloutFilenamePattern.FindStringSubmatch(filepath.Base(path))
	if len(match) != 3 {
		return "", fmt.Errorf("rollout path has no native timestamp: %s", path)
	}
	parsed, err := time.Parse("2006-01-02T15-04-05", match[1])
	if err != nil {
		return "", fmt.Errorf("rollout path timestamp is invalid: %s", path)
	}
	return parsed.Format(time.RFC3339), nil
}

// EqualAbsolutePath compares two explicit absolute paths exactly.
func EqualAbsolutePath(left string, right string) (bool, error) {
	if !filepath.IsAbs(left) || !filepath.IsAbs(right) {
		return false, fmt.Errorf("both paths must be absolute")
	}
	return left == right, nil
}

// ParseTimestamp parses an RFC3339 timestamp without rewriting it.
func ParseTimestamp(value string) (time.Time, bool) {
	parsed, err := time.Parse(time.RFC3339Nano, value)
	if err != nil {
		return time.Time{}, false
	}
	return parsed, true
}

func decodeJSON(reader io.Reader) (any, error) {
	decoder := json.NewDecoder(reader)
	decoder.UseNumber()
	var value any
	if err := decoder.Decode(&value); err != nil {
		return nil, err
	}
	var trailing any
	if err := decoder.Decode(&trailing); err != io.EOF {
		if err == nil {
			return nil, fmt.Errorf("multiple JSON values")
		}
		return nil, err
	}
	return value, nil
}

func partialMatch(actual any, expected any) bool {
	expectedObject, isObject := expected.(map[string]any)
	if !isObject {
		return reflect.DeepEqual(actual, expected)
	}
	actualObject, ok := actual.(map[string]any)
	if !ok {
		return false
	}
	for key, expectedValue := range expectedObject {
		actualValue, exists := actualObject[key]
		if !exists || !partialMatch(actualValue, expectedValue) {
			return false
		}
	}
	return true
}
