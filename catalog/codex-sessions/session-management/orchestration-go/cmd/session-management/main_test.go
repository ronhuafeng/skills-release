package main

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"os"
	"path/filepath"
	"strconv"
	"strings"
	"testing"

	sessionmanagement "github.com/ronhuafeng/skills/catalog/codex-sessions/session-management/orchestration-go"
)

func TestRehomeInputFailureUsesInvalidExit(t *testing.T) {
	var stdout, stderr bytes.Buffer
	exit := run(context.Background(), []string{"rehome", "establish"}, strings.NewReader(`{"thread_id":"unexpected"}`), &stdout, &stderr)
	if exit != exitInvalid || stdout.Len() != 0 || !strings.Contains(stderr.String(), "thread_id must be a canonical UUID") {
		t.Fatalf("exit = %d, stdout = %q, stderr = %q", exit, stdout.String(), stderr.String())
	}

	stdout.Reset()
	stderr.Reset()
	exit = run(context.Background(), []string{"rehome", "establish"}, strings.NewReader(`{"unknown":true}`), &stdout, &stderr)
	if exit != exitInvalid || stdout.Len() != 0 || !strings.Contains(stderr.String(), "unknown field") {
		t.Fatalf("exit = %d, stdout = %q, stderr = %q", exit, stdout.String(), stderr.String())
	}
}

func TestRehomeBlockedExitPreservesPostInstallEvidence(t *testing.T) {
	input := `{"thread_id":"019f73d3-8f35-7173-b637-8255f0b3d992","host":"remote-host","cwd":"/target/workspace"}`
	want := sessionmanagement.RehomeResult{
		ThreadID:          "019f73d3-8f35-7173-b637-8255f0b3d992",
		Host:              "remote-host",
		CWD:               "/target/workspace",
		SourceRolloutPath: "/local/.codex/sessions/source.jsonl",
		RolloutPath:       "/remote/.codex/sessions/destination.jsonl",
		SourceSHA256:      strings.Repeat("a", 64),
		DestinationSHA256: strings.Repeat("b", 64),
	}
	var stdout, stderr bytes.Buffer
	exit := runRehomeEstablishWith(context.Background(), strings.NewReader(input), &stdout, &stderr, func(context.Context, sessionmanagement.RehomeRequest) (sessionmanagement.RehomeResult, error) {
		return want, errors.New("source rollout changed during remote install")
	})
	if exit != exitBlocked || !strings.Contains(stderr.String(), "source rollout changed during remote install") {
		t.Fatalf("exit=%d stderr=%q", exit, stderr.String())
	}
	var got sessionmanagement.RehomeResult
	if err := json.Unmarshal(stdout.Bytes(), &got); err != nil {
		t.Fatal(err)
	}
	if got != want {
		t.Fatalf("result=%#v want=%#v", got, want)
	}
}

func TestRolloutCommand(t *testing.T) {
	ctx := context.Background()
	t.Run("raw pass-through preserves non-empty lines", func(t *testing.T) {
		path := filepath.Join(t.TempDir(), "raw.jsonl")
		content := "\n  {not json} \r\n{\"type\":\"future\"}"
		if err := os.WriteFile(path, []byte(content), 0o600); err != nil {
			t.Fatal(err)
		}
		var stdout, stderr bytes.Buffer
		exit := run(ctx, []string{"rollout", path}, strings.NewReader(""), &stdout, &stderr)
		if exit != exitSuccess || stdout.String() != "  {not json} \r\n{\"type\":\"future\"}\n" || stderr.Len() != 0 {
			t.Fatalf("exit = %d, stdout = %q, stderr = %q", exit, stdout.String(), stderr.String())
		}
	})

	t.Run("filters use raw field names and OR semantics", func(t *testing.T) {
		home := t.TempDir()
		t.Setenv("CODEX_HOME", home)
		sessionID := "019f5950-4bc7-78a1-9992-25a7b4979503"
		path := filepath.Join(home, "archived_sessions", "rollout-2026-01-01T00-00-00-"+sessionID+".jsonl")
		if err := os.MkdirAll(filepath.Dir(path), 0o700); err != nil {
			t.Fatal(err)
		}
		user := `{"type":"event_msg","payload":{"type":"user_message","message":"u"}}`
		commentary := `{"type":"event_msg","payload":{"type":"agent_message","phase":"commentary","message":"c"}}`
		final := `{"type":"event_msg","payload":{"type":"agent_message","phase":"final_answer","message":"f"}}`
		if err := os.WriteFile(path, []byte(strings.Join([]string{user, commentary, final}, "\n")), 0o600); err != nil {
			t.Fatal(err)
		}
		var stdout, stderr bytes.Buffer
		exit := run(ctx, []string{
			"rollout", sessionID, "--include-archived",
			"--filter", `{"type":"event_msg","payload":{"type":"user_message"}}`,
			"--filter", `{"type":"event_msg","payload":{"type":"agent_message","phase":"final_answer"}}`,
		}, strings.NewReader(""), &stdout, &stderr)
		if exit != exitSuccess || stdout.String() != user+"\n"+final+"\n" || stderr.Len() != 0 {
			t.Fatalf("exit = %d, stdout = %q, stderr = %q", exit, stdout.String(), stderr.String())
		}
	})

	t.Run("invalid filter and incomplete structure write no records", func(t *testing.T) {
		path := filepath.Join(t.TempDir(), "bad.jsonl")
		if err := os.WriteFile(path, []byte("{}\nnot json\n{}\n"), 0o600); err != nil {
			t.Fatal(err)
		}
		for _, test := range []struct {
			name       string
			filter     string
			wantExit   int
			wantStderr string
		}{
			{name: "invalid filter", filter: `[]`, wantExit: exitInvalid},
			{name: "malformed record", filter: `{}`, wantExit: exitBlocked, wantStderr: path + ":2\n"},
		} {
			t.Run(test.name, func(t *testing.T) {
				var stdout, stderr bytes.Buffer
				exit := run(ctx, []string{"rollout", path, "--filter", test.filter}, strings.NewReader(""), &stdout, &stderr)
				if exit != test.wantExit || stdout.Len() != 0 {
					t.Fatalf("exit = %d, stdout = %q, stderr = %q", exit, stdout.String(), stderr.String())
				}
				if test.wantStderr != "" && stderr.String() != test.wantStderr {
					t.Fatalf("stderr = %q, want %q", stderr.String(), test.wantStderr)
				}
			})
		}
	})
}

func TestPartitionPlanAndSplitExecute(t *testing.T) {
	repo := t.TempDir()
	home := t.TempDir()
	t.Setenv("CODEX_HOME", home)
	sessionID := "019f5eb8-06b5-7813-84a2-f5ec6b85a473"
	path := filepath.Join(home, "sessions", "2026", "01", "01", "rollout-2026-01-01T00-00-00-"+sessionID+".jsonl")
	if err := os.MkdirAll(filepath.Dir(path), 0o700); err != nil {
		t.Fatal(err)
	}
	rows := []string{
		`{"timestamp":"2026-01-01T00:00:00Z","type":"session_meta","payload":{"id":"` + sessionID + `","session_id":"` + sessionID + `","timestamp":"2026-01-01T00:00:00Z","cwd":` + strconv.Quote(repo) + `,"source":"cli","originator":"codex_cli_rs","cli_version":"0.144.1"}}`,
		`{"timestamp":"2026-01-01T00:00:01Z","type":"event_msg","payload":{"type":"task_started","turn_id":"turn-1"}}`,
		`{"timestamp":"2026-01-01T00:00:02Z","type":"event_msg","payload":{"type":"user_message","message":"first"}}`,
		`{"timestamp":"2026-01-01T00:00:03Z","type":"event_msg","payload":{"type":"agent_message","message":"one","phase":"final_answer"}}`,
		`{"timestamp":"2026-01-01T00:00:04Z","type":"event_msg","payload":{"type":"task_complete","turn_id":"turn-1"}}`,
	}
	if err := os.WriteFile(path, []byte(strings.Join(rows, "\n")+"\n"), 0o600); err != nil {
		t.Fatal(err)
	}

	var inspected, stderr bytes.Buffer
	exit := run(context.Background(), []string{"partition", "inspect", sessionID}, strings.NewReader(""), &inspected, &stderr)
	if exit != exitSuccess || stderr.Len() != 0 {
		t.Fatalf("inspect exit = %d, stderr = %q", exit, stderr.String())
	}
	var inspection sessionmanagement.PartitionWindow
	if err := json.Unmarshal(inspected.Bytes(), &inspection); err != nil {
		t.Fatal(err)
	}
	if len(inspection.CutCandidates) != 1 || inspection.Receipt == nil || inspection.Receipt.Source.ThroughSourceLine != 5 {
		t.Fatalf("inspection = %#v", inspection)
	}

	intent, err := json.Marshal(sessionmanagement.PartitionPlanRequest{
		Receipt: *inspection.Receipt,
		Parts: []sessionmanagement.PartitionIntentPart{
			{Title: "First", AnchorUserMessageLine: 3},
		},
	})
	if err != nil {
		t.Fatal(err)
	}
	var planned bytes.Buffer
	stderr.Reset()
	exit = run(context.Background(), []string{"partition", "plan"}, bytes.NewReader(intent), &planned, &stderr)
	if exit != exitSuccess || stderr.Len() != 0 {
		t.Fatalf("plan exit = %d, stderr = %q", exit, stderr.String())
	}
	var plan sessionmanagement.PartitionPlan
	if err := json.Unmarshal(planned.Bytes(), &plan); err != nil ||
		len(plan.Parts) != 1 ||
		plan.Parts[0].AnchorUserMessageLine != 3 {
		t.Fatalf("plan = %#v, %v", plan, err)
	}

	outputHome := filepath.Join(t.TempDir(), "split-output")
	var written bytes.Buffer
	stderr.Reset()
	exit = run(context.Background(), []string{"split", "execute", "--output-codex-home", outputHome}, bytes.NewReader(planned.Bytes()), &written, &stderr)
	if exit != exitSuccess || stderr.Len() != 0 {
		t.Fatalf("execute exit = %d, output = %q, stderr = %q", exit, written.String(), stderr.String())
	}
	var result sessionmanagement.SplitExecuteResult
	if err := json.Unmarshal(written.Bytes(), &result); err != nil ||
		result.ManifestPath != filepath.Join(outputHome, "split-manifest-"+sessionID+".json") {
		t.Fatalf("execute result = %#v, %v", result, err)
	}
	manifestRaw, err := os.ReadFile(result.ManifestPath)
	if err != nil {
		t.Fatal(err)
	}
	var manifest struct {
		Parts []struct {
			PartID      string `json:"part_id"`
			SessionID   string `json:"session_id"`
			RolloutPath string `json:"rollout_path"`
		} `json:"parts"`
	}
	if err := json.Unmarshal(manifestRaw, &manifest); err != nil {
		t.Fatal(err)
	}
	if len(manifest.Parts) != 1 ||
		manifest.Parts[0].PartID != "P001" ||
		manifest.Parts[0].SessionID == "" ||
		manifest.Parts[0].RolloutPath == "" {
		t.Fatalf("manifest = %#v", manifest)
	}
	written.Reset()
	stderr.Reset()
	exit = run(context.Background(), []string{"split", "execute", "--output-codex-home", outputHome}, bytes.NewReader(planned.Bytes()), &written, &stderr)
	if exit != exitBlocked || written.Len() != 0 || !strings.Contains(stderr.String(), "must not already exist") {
		t.Fatalf("repeat execute exit = %d, stdout = %q, stderr = %q", exit, written.String(), stderr.String())
	}
}
