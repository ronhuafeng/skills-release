package sessionmanagement

import (
	"context"
	"crypto/sha256"
	"encoding/json"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

const rehomeSessionID = "019f0000-1111-7777-8888-999999999999"

func rehomeDependenciesForTest(install func(context.Context, rolloutInstallRequest) (string, error)) rehomeDependencies {
	return rehomeDependencies{
		install: install,
		activate: func(_ context.Context, request RehomeResult) (rehomeActivationResult, error) {
			return rehomeActivationResult{
				Status: "idle", RolloutPath: request.RolloutPath,
				DestinationModelProvider: request.indexedModelProvider,
				FinalModel:               request.currentModel,
			}, nil
		},
	}
}

func TestRehomeInstallsSameIDWithMinimalWorkspaceRebinding(t *testing.T) {
	home := t.TempDir()
	t.Setenv("CODEX_HOME", home)
	sourcePath := writeRehomeSource(t, home)
	var installed rolloutInstallRequest

	result, err := rehomeSession(context.Background(), RehomeRequest{
		ThreadID: rehomeSessionID,
		Host:     "remote-host",
		CWD:      "/target/workspace",
	}, rehomeDependenciesForTest(func(_ context.Context, request rolloutInstallRequest) (string, error) {
		installed = request
		return "/remote/home/.codex/" + request.RelativePath, nil
	}))
	if err != nil {
		t.Fatal(err)
	}
	if result.ThreadID != rehomeSessionID || result.Host != "remote-host" || result.SourceRolloutPath != sourcePath ||
		result.RolloutPath != "/remote/home/.codex/"+installed.RelativePath {
		t.Fatalf("result=%#v", result)
	}
	if result.historicalModelProvider != "historical" || result.indexedModelProvider != "indexed" ||
		result.currentModel != "test" || result.DestinationStatus != "idle" {
		t.Fatalf("execution settings=%#v", result)
	}
	sourceContent, err := os.ReadFile(sourcePath)
	if err != nil {
		t.Fatal(err)
	}
	if result.SourceSHA256 != hashBytes(sourceContent) || result.DestinationSHA256 != hashBytes(installed.Content) {
		t.Fatalf("result digests=%#v", result)
	}
	if installed.ThreadID != rehomeSessionID || installed.Destination.Kind != rolloutInstallSSH ||
		installed.Destination.Host != "remote-host" || installed.CWD != result.CWD {
		t.Fatalf("install request=%#v", installed)
	}

	rows := decodeJSONL(t, installed.Content)
	if got := nestedString(t, rows[0], "payload", "cwd"); got != result.CWD {
		t.Fatalf("session_meta cwd=%q", got)
	}
	if got := nestedString(t, rows[2], "payload", "thread_settings", "cwd"); got != result.CWD {
		t.Fatalf("applied settings cwd=%q", got)
	}
	for _, index := range []int{1, 3} {
		if got := nestedString(t, rows[index], rehomeHistoricalCWDPath(index)...); got != "/source/repo" {
			t.Fatalf("historical cwd at row %d changed to %q", index, got)
		}
	}
}

func TestRehomeStopsAfterInstallWhenSourceChanges(t *testing.T) {
	home := t.TempDir()
	t.Setenv("CODEX_HOME", home)
	sourcePath := writeRehomeSource(t, home)
	result, err := rehomeSession(context.Background(), RehomeRequest{
		ThreadID: rehomeSessionID,
		Host:     "remote-host",
		CWD:      "/target/workspace",
	}, rehomeDependenciesForTest(func(_ context.Context, _ rolloutInstallRequest) (string, error) {
		file, readErr := os.OpenFile(sourcePath, os.O_APPEND|os.O_WRONLY, 0)
		if readErr != nil {
			return "", readErr
		}
		if _, writeErr := file.WriteString(`{"timestamp":"2026-07-15T23:52:34Z","type":"event_msg","payload":{"type":"user_message","message":"late"}}` + "\n"); writeErr != nil {
			_ = file.Close()
			return "", writeErr
		}
		if closeErr := file.Close(); closeErr != nil {
			return "", closeErr
		}
		return "/remote/home/.codex/sessions/destination.jsonl", nil
	}))
	if err == nil || !strings.Contains(err.Error(), "active source rollout digest changed") ||
		!strings.Contains(err.Error(), "destination_rollout_path=/remote/home/.codex/sessions/destination.jsonl") {
		t.Fatalf("result=%#v error=%v", result, err)
	}
	if result.ThreadID != rehomeSessionID || result.Host != "remote-host" || result.CWD != "/target/workspace" ||
		result.SourceRolloutPath != sourcePath || result.RolloutPath != "/remote/home/.codex/sessions/destination.jsonl" ||
		result.SourceSHA256 == "" || result.DestinationSHA256 == "" {
		t.Fatalf("partial result=%#v", result)
	}
}

func TestRehomeRejectsInvalidInputBeforeInstall(t *testing.T) {
	home := t.TempDir()
	t.Setenv("CODEX_HOME", home)
	writeRehomeSource(t, home)
	installed := false
	dependencies := rehomeDependenciesForTest(func(context.Context, rolloutInstallRequest) (string, error) {
		installed = true
		return "", nil
	})
	for name, request := range map[string]RehomeRequest{
		"thread": {ThreadID: "not-a-uuid", Host: "remote-host", CWD: "/target"},
		"host":   {ThreadID: rehomeSessionID, Host: "-unsafe", CWD: "/target"},
		"cwd":    {ThreadID: rehomeSessionID, Host: "remote-host", CWD: "relative"},
	} {
		t.Run(name, func(t *testing.T) {
			if _, err := rehomeSession(context.Background(), request, dependencies); err == nil || !IsInvalidRehomeRequest(err) {
				t.Fatalf("error=%v", err)
			}
		})
	}
	if installed {
		t.Fatal("invalid input reached destination installer")
	}
}

func TestRehomeRemoteInstallIsAtomicAndRejectsSameIDCollision(t *testing.T) {
	sourceHome := t.TempDir()
	remoteHome := t.TempDir()
	targetCWD := t.TempDir()
	if err := os.Mkdir(filepath.Join(remoteHome, ".codex"), 0o700); err != nil {
		t.Fatal(err)
	}
	t.Setenv("CODEX_HOME", sourceHome)
	t.Setenv("FAKE_REMOTE_HOME", remoteHome)
	writeRehomeSource(t, sourceHome)
	bin := t.TempDir()
	ssh := filepath.Join(bin, "ssh")
	script := `#!/bin/sh
for argument do command=$argument; done
case "$command" in
bash\ -lic*)
  printf '%s' "$FAKE_REMOTE_HOME/.codex"
  exit 0
  ;;
esac
HOME="$FAKE_REMOTE_HOME" /bin/sh -c "$command"
`
	if err := os.WriteFile(ssh, []byte(script), 0o700); err != nil {
		t.Fatal(err)
	}
	t.Setenv("PATH", bin+string(os.PathListSeparator)+os.Getenv("PATH"))
	request := RehomeRequest{ThreadID: rehomeSessionID, Host: "remote-host", CWD: targetCWD}

	dependencies := rehomeDependenciesForTest(installRollout)
	result, err := rehomeSession(context.Background(), request, dependencies)
	if err != nil {
		t.Fatal(err)
	}
	installed, err := os.ReadFile(result.RolloutPath)
	if err != nil {
		t.Fatal(err)
	}
	wantHash := sha256.Sum256(installed)
	if _, err := rehomeSession(context.Background(), request, dependencies); err == nil || !strings.Contains(err.Error(), "destination already contains thread id") {
		t.Fatalf("collision error=%v", err)
	}
	after, err := os.ReadFile(result.RolloutPath)
	if err != nil {
		t.Fatal(err)
	}
	if sha256.Sum256(after) != wantHash {
		t.Fatal("collision changed the installed rollout")
	}
}

func writeRehomeSource(t *testing.T, home string) string {
	t.Helper()
	path := filepath.Join(home, "sessions", "2026", "07", "15", "rollout-2026-07-15T23-52-29-"+rehomeSessionID+".jsonl")
	if err := os.MkdirAll(filepath.Dir(path), 0o700); err != nil {
		t.Fatal(err)
	}
	rows := []string{
		`{"timestamp":"2026-07-15T23:52:29Z","type":"session_meta","payload":{"id":"` + rehomeSessionID + `","session_id":"` + rehomeSessionID + `","timestamp":"2026-07-15T23:52:29Z","cwd":"/source/repo","originator":"test","cli_version":"1","source":"cli","model_provider":"historical"}}`,
		`{"timestamp":"2026-07-15T23:52:30Z","type":"turn_context","payload":{"cwd":"/source/repo","model":"test"}}`,
		`{"timestamp":"2026-07-15T23:52:31Z","type":"event_msg","payload":{"type":"thread_settings_applied","thread_settings":{"cwd":"/source/repo","model":"test","model_provider_id":"indexed"}}}`,
		`{"timestamp":"2026-07-15T23:52:32Z","type":"world_state","payload":{"state":{"environments":{"environments":{"local":{"cwd":"/source/repo"}}}}}}`,
		`{"timestamp":"2026-07-15T23:52:33Z","type":"event_msg","payload":{"type":"user_message","message":"keep me"}}`,
	}
	if err := os.WriteFile(path, []byte(strings.Join(rows, "\n")+"\n"), 0o600); err != nil {
		t.Fatal(err)
	}
	return path
}

func decodeJSONL(t *testing.T, content []byte) []map[string]any {
	t.Helper()
	lines := strings.Split(strings.TrimSpace(string(content)), "\n")
	rows := make([]map[string]any, 0, len(lines))
	for _, line := range lines {
		var row map[string]any
		if err := json.Unmarshal([]byte(line), &row); err != nil {
			t.Fatal(err)
		}
		rows = append(rows, row)
	}
	return rows
}

func nestedString(t *testing.T, row map[string]any, path ...string) string {
	t.Helper()
	var current any = row
	for _, field := range path {
		object, ok := current.(map[string]any)
		if !ok {
			t.Fatalf("%v is not an object at %s", current, field)
		}
		current = object[field]
	}
	value, ok := current.(string)
	if !ok {
		t.Fatalf("%v is not a string", current)
	}
	return value
}

func rehomeHistoricalCWDPath(index int) []string {
	if index == 1 {
		return []string{"payload", "cwd"}
	}
	return []string{"payload", "state", "environments", "environments", "local", "cwd"}
}
