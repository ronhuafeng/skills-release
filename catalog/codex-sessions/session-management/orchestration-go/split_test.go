package sessionmanagement

import (
	"bytes"
	"context"
	"encoding/json"
	"os"
	"path/filepath"
	"reflect"
	"strconv"
	"strings"
	"testing"

	"github.com/google/uuid"
	rollout "github.com/ronhuafeng/skills/harnesses/codex/rollout-go"
)

func TestInspectAndExecuteSplit(t *testing.T) {
	repo := t.TempDir()
	codexHome := t.TempDir()
	sourceID := "019f5eb8-06b5-7813-84a2-f5ec6b85a473"
	sourcePath := writeSplitSource(t, codexHome, repo, sourceID)
	sourceBefore, err := os.ReadFile(sourcePath)
	if err != nil {
		t.Fatal(err)
	}

	windows, receipt, err := inspectAll(t, PartitionInspectRequest{
		CodexHome: codexHome, SessionID: sourceID,
	})
	if err != nil {
		t.Fatal(err)
	}
	var candidates []PartitionCutCandidate
	for _, window := range windows {
		candidates = append(candidates, window.CutCandidates...)
	}
	if receipt.Source.ThroughSourceLine != 13 || len(candidates) != 2 {
		t.Fatalf("windows = %#v, receipt = %#v", windows, receipt)
	}
	if candidates[0].AnchorUserMessageLine != 3 || candidates[1].AnchorUserMessageLine != 10 {
		t.Fatalf("cut candidates = %#v", candidates)
	}

	partition, err := PlanPartition(context.Background(), PartitionPlanRequest{
		Receipt: receipt, Parts: standardSplitIntent(),
	})
	if err != nil {
		t.Fatal(err)
	}
	if partition.Receipt != receipt ||
		len(partition.Parts) != 2 ||
		partition.Parts[0].AnchorUserMessageLine != 3 ||
		partition.Parts[0].StartSourceLine != 2 ||
		partition.Parts[0].EndSourceLine != 8 ||
		partition.Parts[1].AnchorUserMessageLine != 10 ||
		partition.Parts[1].StartSourceLine != 9 ||
		partition.Parts[1].EndSourceLine != 13 {
		t.Fatalf("partition = %#v", partition)
	}

	tampered := partition
	tampered.Parts = append([]PartitionPlanPart(nil), partition.Parts...)
	tampered.Parts[0].EndSourceLine--
	_, err = ExecuteSplit(context.Background(), SplitExecuteRequest{
		Plan:            tampered,
		OutputCodexHome: filepath.Join(t.TempDir(), "tampered-output"),
	})
	if err == nil || !strings.Contains(err.Error(), "partition plan does not match") {
		t.Fatalf("tampered plan error = %v", err)
	}

	outputHome := filepath.Join(t.TempDir(), "split-codex-home")
	result, err := ExecuteSplit(context.Background(), SplitExecuteRequest{
		Plan:            partition,
		OutputCodexHome: outputHome,
	})
	if err != nil {
		t.Fatal(err)
	}
	if result.OutputCodexHome != outputHome ||
		result.ManifestPath != filepath.Join(outputHome, "split-manifest-"+sourceID+".json") {
		t.Fatalf("execute result = %#v", result)
	}
	sourceAfter, err := os.ReadFile(sourcePath)
	if err != nil {
		t.Fatal(err)
	}
	if !bytes.Equal(sourceBefore, sourceAfter) {
		t.Fatal("source rollout changed")
	}

	manifest, err := validatePublishedSplitManifest(result.ManifestPath)
	if err != nil {
		t.Fatalf("published manifest validation failed: %v", err)
	}
	if manifest.SourceSessionID != sourceID || manifest.ThroughSourceLine != 13 ||
		len(manifest.Parts) != 2 {
		t.Fatalf("manifest = %#v", manifest)
	}
	for index, part := range manifest.Parts {
		if part.PartID != "P00"+strconv.Itoa(index+1) ||
			part.Title != standardSplitIntent()[index].Title {
			t.Fatalf("manifest part %d = %#v", index, part)
		}
		id, err := uuid.Parse(part.SessionID)
		if err != nil || id.Version() != 7 || id.String() == sourceID {
			t.Fatalf("generated session id = %q, %v", part.SessionID, err)
		}
		if part.SourceRecordCount < 1 || part.SourceRecordsSHA256 == "" || part.OutputSHA256 == "" {
			t.Fatalf("manifest proof for %s is incomplete", part.PartID)
		}
		assertCanonicalSplitPart(t, part)
	}
}

func assertCanonicalSplitPart(t *testing.T, part splitManifestPart) {
	t.Helper()
	recordCount := 0
	if err := rollout.Scan(part.RolloutPath, func(record rollout.Record) error {
		ordinal, present, err := record.Ordinal()
		if err != nil {
			return err
		}
		if !present || ordinal != uint64(recordCount) {
			t.Fatalf("%s line %d ordinal = %d, %t", part.PartID, record.Line, ordinal, present)
		}
		if recordCount == 0 {
			meta, err := rollout.DecodeSessionMeta(record)
			if err != nil {
				return err
			}
			var window struct {
				WindowID string `json:"window_id"`
			}
			if err := json.Unmarshal(meta.ContextWindow, &window); err != nil {
				return err
			}
			if meta.ID != part.SessionID || meta.SessionID != part.SessionID ||
				meta.HistoryMode != "paginated" || window.WindowID != part.SessionID {
				t.Fatalf("%s metadata = %#v, window = %#v", part.PartID, meta, window)
			}
		}
		recordCount++
		return nil
	}); err != nil {
		t.Fatal(err)
	}
	if recordCount != part.SourceRecordCount+1 {
		t.Fatalf("%s record count = %d", part.PartID, recordCount)
	}
}

func TestExecuteSplitRejectsExternalHistoryLineage(t *testing.T) {
	repo := t.TempDir()
	codexHome := t.TempDir()
	sourceID := "019f5eb8-06b5-7813-84a2-f5ec6b85a473"
	sourcePath := writeSplitSource(t, codexHome, repo, sourceID)
	raw, err := os.ReadFile(sourcePath)
	if err != nil {
		t.Fatal(err)
	}
	raw = bytes.Replace(
		raw,
		[]byte(`"history_mode":"paginated"`),
		[]byte(`"history_mode":"paginated","history_base":{"session_id":"019f68b8-f505-78b2-9be4-2722630ce29d","ordinal":1,"byte_offset":1}`),
		1,
	)
	if err := os.WriteFile(sourcePath, raw, 0o600); err != nil {
		t.Fatal(err)
	}
	_, receipt, err := inspectAll(t, PartitionInspectRequest{CodexHome: codexHome, SessionID: sourceID})
	if err != nil {
		t.Fatal(err)
	}
	plan, err := PlanPartition(context.Background(), PartitionPlanRequest{
		Receipt: receipt,
		Parts:   standardSplitIntent(),
	})
	if err != nil {
		t.Fatal(err)
	}
	_, err = ExecuteSplit(context.Background(), SplitExecuteRequest{
		Plan: plan, OutputCodexHome: filepath.Join(t.TempDir(), "lineage-output"),
	})
	if err == nil || !strings.Contains(err.Error(), "history_base") {
		t.Fatalf("split error = %v", err)
	}
}

func TestPartitionWindowsAreBoundedReplayableAndComplete(t *testing.T) {
	home := t.TempDir()
	id := "019f5eb8-06b5-7813-84a2-f5ec6b85a473"
	path := writeSplitSource(t, home, t.TempDir(), id)
	raw, err := os.ReadFile(path)
	if err != nil {
		t.Fatal(err)
	}
	raw = bytes.Replace(raw, []byte("done one"), bytes.Repeat([]byte("x"), 16*1024), 1)
	if err := os.WriteFile(path, raw, 0o600); err != nil {
		t.Fatal(err)
	}
	first, err := InspectPartition(context.Background(), PartitionInspectRequest{
		CodexHome: home, SessionID: id, WindowBytes: 1,
	})
	if err != nil {
		t.Fatal(err)
	}
	if first.Sequence != 1 || len(first.Records) != 1 || !first.Oversized || first.Continuation == "" || first.Receipt != nil {
		t.Fatalf("first window = %#v", first)
	}
	second, err := InspectPartition(context.Background(), PartitionInspectRequest{Continuation: first.Continuation})
	if err != nil {
		t.Fatal(err)
	}
	replayed, err := InspectPartition(context.Background(), PartitionInspectRequest{Continuation: first.Continuation})
	if err != nil || !reflect.DeepEqual(second, replayed) {
		t.Fatalf("replay = %#v, error = %v; want %#v", replayed, err, second)
	}
	tampered := first.Continuation[:len(first.Continuation)-1] + "A"
	if tampered == first.Continuation {
		tampered = first.Continuation[:len(first.Continuation)-1] + "B"
	}
	if _, err := InspectPartition(context.Background(), PartitionInspectRequest{Continuation: tampered}); err == nil {
		t.Fatal("tampered continuation was accepted")
	}

	windows, receipt, err := inspectAll(t, PartitionInspectRequest{CodexHome: home, SessionID: id, WindowBytes: 1})
	if err != nil {
		t.Fatal(err)
	}
	lines := []int{}
	for index, window := range windows {
		if window.Sequence != index+1 || window.Source != receipt.Source {
			t.Fatalf("window %d = %#v", index, window)
		}
		for _, record := range window.Records {
			lines = append(lines, record.SourceLine)
		}
	}
	if !reflect.DeepEqual(lines, []int{3, 6, 10, 11, 12}) ||
		receipt.FirstSourceLine != 1 || receipt.LastSourceLine != 13 ||
		receipt.RawRecordCount != 13 || receipt.SemanticRecordCount != 5 || receipt.CutCandidateCount != 2 {
		t.Fatalf("lines = %v, receipt = %#v", lines, receipt)
	}
	bounded, _, err := inspectAll(t, PartitionInspectRequest{CodexHome: home, SessionID: id, WindowBytes: 200})
	if err != nil {
		t.Fatal(err)
	}
	if bounded[0].Continuation == "" || len(bounded[0].Continuation) > 4096 {
		t.Fatalf("continuation carries semantic content: %d bytes", len(bounded[0].Continuation))
	}
	for _, window := range bounded {
		if window.SemanticBytes > 200 && (!window.Oversized || len(window.Records) != 1) {
			t.Fatalf("window exceeds semantic budget without one oversized record: %#v", window)
		}
	}
}

func TestExecuteSplitUsesFrozenPrefixAfterAppend(t *testing.T) {
	repo := t.TempDir()
	codexHome := t.TempDir()
	sourceID := "019f5eb8-06b5-7813-84a2-f5ec6b85a473"
	sourcePath := writeSplitSource(t, codexHome, repo, sourceID)
	_, receipt, err := inspectAll(t, PartitionInspectRequest{
		CodexHome: codexHome, SessionID: sourceID,
	})
	if err != nil {
		t.Fatal(err)
	}
	partition, err := PlanPartition(context.Background(), PartitionPlanRequest{
		Receipt: receipt, Parts: standardSplitIntent(),
	})
	if err != nil {
		t.Fatal(err)
	}
	file, err := os.OpenFile(sourcePath, os.O_APPEND|os.O_WRONLY, 0)
	if err != nil {
		t.Fatal(err)
	}
	if _, err := file.WriteString(`{"timestamp":"2026-01-01T00:00:13Z","type":"event_msg","payload":{"type":"user_message","message":"new work"}}` + "\n"); err != nil {
		_ = file.Close()
		t.Fatal(err)
	}
	if err := file.Close(); err != nil {
		t.Fatal(err)
	}

	result, err := ExecuteSplit(context.Background(), SplitExecuteRequest{
		Plan:            partition,
		OutputCodexHome: filepath.Join(t.TempDir(), "changed-source-output"),
	})
	if err != nil {
		t.Fatal(err)
	}
	manifest, err := validatePublishedSplitManifest(result.ManifestPath)
	if err != nil {
		t.Fatal(err)
	}
	if manifest.ThroughSourceLine != receipt.LastSourceLine || manifest.Parts[len(manifest.Parts)-1].EndSourceLine != receipt.LastSourceLine {
		t.Fatalf("manifest = %#v, receipt = %#v", manifest, receipt)
	}
}

func TestInspectPartitionRejectsRolloutSymlinkEscapingCodexHome(t *testing.T) {
	repo := t.TempDir()
	codexHome := t.TempDir()
	externalHome := t.TempDir()
	sourceID := "019f5eb8-06b5-7813-84a2-f5ec6b85a473"
	externalPath := writeSplitSource(t, externalHome, repo, sourceID)
	linkPath := filepath.Join(codexHome, "sessions", "2026", "01", "01", filepath.Base(externalPath))
	if err := os.MkdirAll(filepath.Dir(linkPath), 0o700); err != nil {
		t.Fatal(err)
	}
	if err := os.Symlink(externalPath, linkPath); err != nil {
		t.Fatal(err)
	}
	_, err := InspectPartition(context.Background(), PartitionInspectRequest{
		CodexHome: codexHome, SessionID: sourceID,
	})
	if err == nil || !strings.Contains(err.Error(), "escapes its Codex home storage root") {
		t.Fatalf("error = %v", err)
	}
}

func TestExecuteSplitRejectsOutputInsideSourceHomeThroughSymlink(t *testing.T) {
	repo := t.TempDir()
	sourceHome := t.TempDir()
	sourceID := "019f5eb8-06b5-7813-84a2-f5ec6b85a473"
	writeSplitSource(t, sourceHome, repo, sourceID)
	_, receipt, err := inspectAll(t, PartitionInspectRequest{
		CodexHome: sourceHome, SessionID: sourceID,
	})
	if err != nil {
		t.Fatal(err)
	}
	partition, err := PlanPartition(context.Background(), PartitionPlanRequest{
		Receipt: receipt, Parts: standardSplitIntent(),
	})
	if err != nil {
		t.Fatal(err)
	}
	insideParent := filepath.Join(sourceHome, "staging-parent")
	if err := os.Mkdir(insideParent, 0o700); err != nil {
		t.Fatal(err)
	}
	aliasRoot := t.TempDir()
	alias := filepath.Join(aliasRoot, "source-alias")
	if err := os.Symlink(sourceHome, alias); err != nil {
		t.Fatal(err)
	}
	_, err = ExecuteSplit(context.Background(), SplitExecuteRequest{
		Plan:            partition,
		OutputCodexHome: filepath.Join(alias, "staging-parent", "codex-home"),
	})
	if err == nil || !strings.Contains(err.Error(), "outside the source Codex home") {
		t.Fatalf("error = %v", err)
	}
}

func standardSplitIntent() []PartitionIntentPart {
	return []PartitionIntentPart{
		{Title: "First objective", AnchorUserMessageLine: 3},
		{Title: "Second objective", AnchorUserMessageLine: 10},
	}
}

func inspectAll(t *testing.T, request PartitionInspectRequest) ([]PartitionWindow, PartitionScanReceipt, error) {
	t.Helper()
	windows := []PartitionWindow{}
	for {
		window, err := InspectPartition(context.Background(), request)
		if err != nil {
			return nil, PartitionScanReceipt{}, err
		}
		windows = append(windows, window)
		if window.Receipt != nil {
			return windows, *window.Receipt, nil
		}
		request = PartitionInspectRequest{Continuation: window.Continuation}
	}
}

func TestInspectPartitionExcludesCutCrossingToolCall(t *testing.T) {
	home := t.TempDir()
	repo := t.TempDir()
	sessionID := "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
	path := filepath.Join(
		home,
		"sessions",
		"2026",
		"01",
		"01",
		"rollout-2026-01-01T00-00-00-"+sessionID+".jsonl",
	)
	if err := os.MkdirAll(filepath.Dir(path), 0o700); err != nil {
		t.Fatal(err)
	}
	rows := []string{
		`{"timestamp":"2026-01-01T00:00:00Z","type":"session_meta","payload":{"id":"` + sessionID + `","timestamp":"2026-01-01T00:00:00Z","cwd":` + strconv.Quote(repo) + `,"originator":"codex_cli_rs","cli_version":"0.1.0"}}`,
		`{"timestamp":"2026-01-01T00:00:01Z","type":"event_msg","payload":{"type":"task_started","turn_id":"turn-1"}}`,
		`{"timestamp":"2026-01-01T00:00:02Z","type":"event_msg","payload":{"type":"user_message","message":"first"}}`,
		`{"timestamp":"2026-01-01T00:00:03Z","type":"response_item","payload":{"type":"custom_tool_call","call_id":"call-1"}}`,
		`{"timestamp":"2026-01-01T00:00:04Z","type":"event_msg","payload":{"type":"task_complete","turn_id":"turn-1"}}`,
		`{"timestamp":"2026-01-01T00:00:05Z","type":"event_msg","payload":{"type":"task_started","turn_id":"turn-2"}}`,
		`{"timestamp":"2026-01-01T00:00:06Z","type":"event_msg","payload":{"type":"user_message","message":"second"}}`,
		`{"timestamp":"2026-01-01T00:00:07Z","type":"response_item","payload":{"type":"custom_tool_call_output","call_id":"call-1"}}`,
		`{"timestamp":"2026-01-01T00:00:08Z","type":"event_msg","payload":{"type":"task_complete","turn_id":"turn-2"}}`,
	}
	if err := os.WriteFile(
		path,
		[]byte(strings.Join(rows, "\n")+"\n"),
		0o600,
	); err != nil {
		t.Fatal(err)
	}

	inspection, err := InspectPartition(context.Background(), PartitionInspectRequest{
		CodexHome: home,
		SessionID: sessionID,
	})
	if err != nil {
		t.Fatal(err)
	}
	if len(inspection.CutCandidates) != 1 ||
		inspection.CutCandidates[0].AnchorUserMessageLine != 3 {
		t.Fatalf("cut candidates = %#v", inspection.CutCandidates)
	}
}

func TestInspectPartitionHandlesPersistedTurnDiscontinuity(t *testing.T) {
	t.Run("a new turn closes the prior projection and blocks an unresolved call boundary", func(t *testing.T) {
		home := t.TempDir()
		sessionID := "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
		path := filepath.Join(home, "sessions", "2026", "01", "01", "rollout-2026-01-01T00-00-00-"+sessionID+".jsonl")
		if err := os.MkdirAll(filepath.Dir(path), 0o700); err != nil {
			t.Fatal(err)
		}
		rows := []string{
			`{"timestamp":"2026-01-01T00:00:00Z","type":"session_meta","payload":{"id":"` + sessionID + `","timestamp":"2026-01-01T00:00:00Z","cwd":"/workspace","originator":"codex_cli_rs","cli_version":"0.1.0"}}`,
			`{"timestamp":"2026-01-01T00:00:01Z","type":"event_msg","payload":{"type":"task_started","turn_id":"turn-1"}}`,
			`{"timestamp":"2026-01-01T00:00:02Z","type":"event_msg","payload":{"type":"user_message","message":"first"}}`,
			`{"timestamp":"2026-01-01T00:00:03Z","type":"event_msg","payload":{"type":"task_started","turn_id":"turn-2"}}`,
			`{"timestamp":"2026-01-01T00:00:04Z","type":"event_msg","payload":{"type":"user_message","message":"second"}}`,
			`{"timestamp":"2026-01-01T00:00:05Z","type":"event_msg","payload":{"type":"turn_aborted","reason":"replaced"}}`,
			`{"timestamp":"2026-01-01T00:00:06Z","type":"event_msg","payload":{"type":"task_started","turn_id":"turn-3"}}`,
			`{"timestamp":"2026-01-01T00:00:07Z","type":"event_msg","payload":{"type":"user_message","message":"third"}}`,
			`{"timestamp":"2026-01-01T00:00:08Z","type":"response_item","payload":{"type":"custom_tool_call","call_id":"call-1"}}`,
			`{"timestamp":"2026-01-01T00:00:09Z","type":"event_msg","payload":{"type":"task_started","turn_id":"turn-4"}}`,
			`{"timestamp":"2026-01-01T00:00:10Z","type":"event_msg","payload":{"type":"user_message","message":"fourth"}}`,
			`{"timestamp":"2026-01-01T00:00:11Z","type":"response_item","payload":{"type":"custom_tool_call_output","call_id":"call-1"}}`,
			`{"timestamp":"2026-01-01T00:00:12Z","type":"response_item","payload":{"type":"custom_tool_call_output","call_id":"call-1"}}`,
			`{"timestamp":"2026-01-01T00:00:13Z","type":"event_msg","payload":{"type":"turn_aborted","turn_id":"turn-3","reason":"replaced"}}`,
			`{"timestamp":"2026-01-01T00:00:14Z","type":"event_msg","payload":{"type":"task_complete","turn_id":"turn-4"}}`,
		}
		if err := os.WriteFile(path, []byte(strings.Join(rows, "\n")+"\n"), 0o600); err != nil {
			t.Fatal(err)
		}

		window, err := InspectPartition(context.Background(), PartitionInspectRequest{CodexHome: home, SessionID: sessionID})
		if err != nil {
			t.Fatal(err)
		}
		if window.Receipt == nil || len(window.CutCandidates) != 3 {
			t.Fatalf("window = %#v", window)
		}
		got := []int{
			window.CutCandidates[0].AnchorUserMessageLine,
			window.CutCandidates[1].AnchorUserMessageLine,
			window.CutCandidates[2].AnchorUserMessageLine,
		}
		if !reflect.DeepEqual(got, []int{3, 5, 8}) {
			t.Fatalf("candidate anchors = %v", got)
		}
	})

	t.Run("an active tail is journalable and append does not invalidate its snapshot", func(t *testing.T) {
		home := t.TempDir()
		sessionID := "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"
		path := filepath.Join(home, "sessions", "2026", "01", "01", "rollout-2026-01-01T00-00-00-"+sessionID+".jsonl")
		if err := os.MkdirAll(filepath.Dir(path), 0o700); err != nil {
			t.Fatal(err)
		}
		rows := []string{
			`{"timestamp":"2026-01-01T00:00:00Z","type":"session_meta","payload":{"id":"` + sessionID + `","timestamp":"2026-01-01T00:00:00Z","cwd":"/workspace","originator":"codex_cli_rs","cli_version":"0.1.0"}}`,
			`{"timestamp":"2026-01-01T00:00:01Z","type":"event_msg","payload":{"type":"task_started","turn_id":"turn-1"}}`,
			`{"timestamp":"2026-01-01T00:00:02Z","type":"event_msg","payload":{"type":"user_message","message":"unfinished"}}`,
			`{"timestamp":"2026-01-01T00:00:03Z","type":"event_msg","payload":{"type":"agent_message","message":"working","phase":"commentary"}}`,
		}
		if err := os.WriteFile(path, []byte(strings.Join(rows, "\n")+"\n"), 0o600); err != nil {
			t.Fatal(err)
		}

		first, err := InspectPartition(context.Background(), PartitionInspectRequest{CodexHome: home, SessionID: sessionID, WindowBytes: 1})
		if err != nil || first.Continuation == "" || first.Receipt != nil {
			t.Fatalf("first window = %#v, error = %v", first, err)
		}
		file, err := os.OpenFile(path, os.O_APPEND|os.O_WRONLY, 0)
		if err != nil {
			t.Fatal(err)
		}
		if _, err := file.WriteString(`{"timestamp":"2026-01-01T00:00:04Z","type":"event_msg","payload":{"type":"task_complete","turn_id":"turn-1"}}` + "\n"); err != nil {
			_ = file.Close()
			t.Fatal(err)
		}
		if err := file.Close(); err != nil {
			t.Fatal(err)
		}

		second, err := InspectPartition(context.Background(), PartitionInspectRequest{Continuation: first.Continuation})
		if err != nil || second.Receipt == nil || !second.Receipt.TailOpen || second.Receipt.LastSourceLine != 4 {
			t.Fatalf("second window = %#v, error = %v", second, err)
		}
		plan, err := PlanPartition(context.Background(), PartitionPlanRequest{
			Receipt: *second.Receipt,
			Parts:   []PartitionIntentPart{{Title: "Unfinished objective", AnchorUserMessageLine: 3}},
		})
		if err != nil {
			t.Fatal(err)
		}
		_, err = ExecuteSplit(context.Background(), SplitExecuteRequest{
			Plan: plan, OutputCodexHome: filepath.Join(t.TempDir(), "open-tail-output"),
		})
		if err == nil || !strings.Contains(err.Error(), "closed lifecycle tail") {
			t.Fatalf("split error = %v", err)
		}
	})
}

func writeSplitSource(t *testing.T, codexHome string, repo string, sourceID string) string {
	t.Helper()
	path := filepath.Join(codexHome, "sessions", "2026", "01", "01", "rollout-2026-01-01T00-00-00-"+sourceID+".jsonl")
	if err := os.MkdirAll(filepath.Dir(path), 0o700); err != nil {
		t.Fatal(err)
	}
	rows := []string{
		`{"timestamp":"2026-01-01T00:00:00Z","ordinal":0,"type":"session_meta","payload":{"id":"` + sourceID + `","session_id":"` + sourceID + `","timestamp":"2026-01-01T00:00:00Z","cwd":` + strconv.Quote(repo) + `,"source":"cli","originator":"codex_cli_rs","cli_version":"0.144.1","history_mode":"paginated","context_window":{"window_id":"` + sourceID + `"}}}`,
		`{"timestamp":"2026-01-01T00:00:01Z","ordinal":1,"type":"event_msg","payload":{"type":"task_started","turn_id":"turn-1"}}`,
		`{"timestamp":"2026-01-01T00:00:02Z","ordinal":2,"type":"event_msg","payload":{"type":"user_message","message":"first"}}`,
		`{"timestamp":"2026-01-01T00:00:03Z","ordinal":3,"type":"response_item","payload":{"type":"custom_tool_call","call_id":"call-1","name":"lookup","input":"{}"}}`,
		`{"timestamp":"2026-01-01T00:00:04Z","ordinal":4,"type":"response_item","payload":{"type":"custom_tool_call_output","call_id":"call-1","output":"ok"}}`,
		`{"timestamp":"2026-01-01T00:00:05Z","ordinal":5,"type":"event_msg","payload":{"type":"agent_message","message":"done one","phase":"final_answer"}}`,
		`{"timestamp":"2026-01-01T00:00:06Z","ordinal":6,"type":"event_msg","payload":{"type":"task_complete","turn_id":"turn-1"}}`,
		`{"timestamp":"2026-01-01T00:00:07Z","ordinal":7,"type":"turn_context","payload":{"model":"gpt-test"}}`,
		`{"timestamp":"2026-01-01T00:00:08Z","ordinal":8,"type":"event_msg","payload":{"type":"task_started","turn_id":"turn-2"}}`,
		`{"timestamp":"2026-01-01T00:00:09Z","ordinal":9,"type":"event_msg","payload":{"type":"user_message","message":"second"}}`,
		`{"timestamp":"2026-01-01T00:00:10Z","ordinal":10,"type":"event_msg","payload":{"type":"thread_goal_updated","threadId":"` + sourceID + `","goal":{"threadId":"` + sourceID + `","objective":"finish","status":"active","tokensUsed":1,"timeUsedSeconds":2,"createdAt":3,"updatedAt":4}}}`,
		`{"timestamp":"2026-01-01T00:00:11Z","ordinal":11,"type":"event_msg","payload":{"type":"agent_message","message":"done two","phase":"final_answer"}}`,
		`{"timestamp":"2026-01-01T00:00:12Z","ordinal":12,"type":"event_msg","payload":{"type":"task_complete","turn_id":"turn-2"}}`,
	}
	if err := os.WriteFile(path, []byte(strings.Join(rows, "\n")+"\n"), 0o600); err != nil {
		t.Fatal(err)
	}
	return path
}
