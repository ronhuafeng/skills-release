package rollout

import (
	"bytes"
	"errors"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func TestSelectFilteredOutputIsAllOrNothing(t *testing.T) {
	path := filepath.Join(t.TempDir(), "rows.jsonl")
	if err := os.WriteFile(path, []byte("{\"type\":\"a\",\"payload\":{}}\nnot-json\n"), 0o600); err != nil {
		t.Fatal(err)
	}
	filter, err := ParseFilter(`{"type":"a"}`)
	if err != nil {
		t.Fatal(err)
	}
	visited := 0
	err = Select(path, []Filter{filter}, func(Record) error {
		visited++
		return nil
	})
	var structural *StructuralError
	if !errors.As(err, &structural) || structural.Line != 2 || visited != 0 {
		t.Fatalf("error = %#v, visited = %d", err, visited)
	}
	if err := Select(path, nil, func(Record) error {
		visited++
		return nil
	}); err != nil || visited != 2 {
		t.Fatalf("raw selection error = %v, visited = %d", err, visited)
	}
}

func TestStreamingProjectionsAndCWDRebind(t *testing.T) {
	id := "019f5eb8-06b5-7813-84a2-f5ec6b85a473"
	path := nativeTestPath(t, id)
	rows := []string{
		`{"timestamp":"2026-01-01T00:00:00Z","type":"session_meta","payload":{"id":"` + id + `","session_id":"` + id + `","timestamp":"2026-01-01T00:00:00Z","cwd":"/old","originator":"codex_cli_rs","cli_version":"1","model_provider":"provider-a"}}`,
		`{"timestamp":"2026-01-01T00:00:01Z","type":"turn_context","payload":{"model":"model-a"}}`,
		`{"timestamp":"2026-01-01T00:00:02Z","type":"event_msg","payload":{"type":"thread_settings_applied","thread_settings":{"cwd":"/later","model":"model-b","model_provider_id":"provider-b"}}}`,
		`{"timestamp":"2026-01-01T00:00:03Z","type":"event_msg","payload":{"type":"thread_goal_updated","threadId":"` + id + `","goal":{"threadId":"` + id + `","objective":"ship","status":"active","tokensUsed":1,"timeUsedSeconds":2,"createdAt":3,"updatedAt":4}}}`,
	}
	if err := os.WriteFile(path, []byte(strings.Join(rows, "\n")+"\n"), 0o600); err != nil {
		t.Fatal(err)
	}
	meta, err := SessionMeta(path)
	if err != nil || meta.ID != id || meta.CWD != "/old" {
		t.Fatalf("meta = %#v, error = %v", meta, err)
	}
	settings, err := ExecutionSettings(path)
	if err != nil || settings.Model != "model-b" || settings.ModelProvider != "provider-b" {
		t.Fatalf("settings = %#v, error = %v", settings, err)
	}
	if err := ValidateThreadIdentity(path, id); err != nil {
		t.Fatal(err)
	}
	rebound, err := RebindResumeAndIndexedCWD(path, "/new")
	if err != nil {
		t.Fatal(err)
	}
	if bytes.Count(rebound, []byte(`"cwd":"/new"`)) != 2 || bytes.Contains(rebound, []byte(`"cwd":"/later"`)) {
		t.Fatalf("rebound rollout = %s", rebound)
	}
}

func TestContentProjectionExcludesToolPayloadsAndReasoning(t *testing.T) {
	path := filepath.Join(t.TempDir(), "rollout-2026-01-01T00-00-00-019f5eb8-06b5-7813-84a2-f5ec6b85a473.jsonl")
	rows := []string{
		`{"timestamp":"2026-01-01T00:00:00Z","type":"event_msg","payload":{"type":"user_message","message":"ship it"}}`,
		`{"timestamp":"2026-01-01T00:00:01Z","type":"response_item","payload":{"type":"reasoning","encrypted_content":"opaque-secret"}}`,
		`{"timestamp":"2026-01-01T00:00:02Z","type":"response_item","payload":{"type":"function_call","name":"expensive_tool","arguments":"large-input","call_id":"call-1"}}`,
		`{"timestamp":"2026-01-01T00:00:03Z","type":"response_item","payload":{"type":"function_call_output","output":"large-output","call_id":"call-1"}}`,
	}
	if err := os.WriteFile(path, []byte(strings.Join(rows, "\n")+"\n"), 0o600); err != nil {
		t.Fatal(err)
	}
	content := []ContentRecord{}
	err := Scan(path, func(record Record) error {
		projected, err := record.Content()
		if err != nil {
			return err
		}
		if projected != nil {
			content = append(content, *projected)
		}
		return nil
	})
	if err != nil {
		t.Fatal(err)
	}
	if len(content) != 1 || content[0].Kind != ContentUser || content[0].Text != "ship it" {
		t.Fatalf("content = %#v", content)
	}
}

func nativeTestPath(t *testing.T, id string) string {
	t.Helper()
	path := filepath.Join(t.TempDir(), "rollout-2026-01-01T00-00-00-"+id+".jsonl")
	return path
}
