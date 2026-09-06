package sessionmanagement

import (
	"context"
	"errors"
	"os"
	"path/filepath"
	"reflect"
	"strings"
	"testing"

	"github.com/ronhuafeng/llm-go/codexsdk/protocolv2"
)

type fakeSplitInstallProjects struct {
	projects []protocolv2.Project
	events   *[]string
}

func (fake *fakeSplitInstallProjects) List(context.Context, protocolv2.ProjectListParams) (protocolv2.ProjectListResponse, error) {
	*fake.events = append(*fake.events, "project-list")
	return protocolv2.ProjectListResponse{Data: fake.projects}, nil
}

type fakeSplitInstallThreads struct {
	t            *testing.T
	cwd          string
	paths        map[string]string
	visible      map[string]bool
	projects     map[string]string
	resumeErrors map[string]error
	events       *[]string
	provider     string
	defaultModel string
}

func (fake *fakeSplitInstallThreads) Read(_ context.Context, params protocolv2.ThreadReadParams) (protocolv2.ThreadReadResponse, error) {
	if !fake.visible[params.ThreadID] {
		thread := fake.thread(params.ThreadID)
		thread.Status = protocolv2.NewThreadStatusNotLoaded()
		return protocolv2.ThreadReadResponse{Thread: thread}, nil
	}
	return protocolv2.ThreadReadResponse{Thread: fake.thread(params.ThreadID)}, nil
}

func (fake *fakeSplitInstallThreads) Resume(_ context.Context, params protocolv2.ThreadResumeParams) (protocolv2.ThreadResumeResponse, error) {
	*fake.events = append(*fake.events, "resume:"+params.ThreadID)
	fake.visible[params.ThreadID] = true
	if err := fake.resumeErrors[params.ThreadID]; err != nil {
		delete(fake.resumeErrors, params.ThreadID)
		return protocolv2.ThreadResumeResponse{}, err
	}
	return protocolv2.ThreadResumeResponse{
		Thread: fake.thread(params.ThreadID), CWD: fake.cwd,
		ModelProvider: fake.provider, Model: fake.defaultModel,
	}, nil
}

func (fake *fakeSplitInstallThreads) SettingsUpdate(context.Context, protocolv2.ThreadSettingsUpdateParams) (protocolv2.ThreadSettingsUpdateResponse, error) {
	fake.t.Fatal("unexpected thread settings update")
	return protocolv2.ThreadSettingsUpdateResponse{}, nil
}

func (fake *fakeSplitInstallThreads) MetadataUpdate(_ context.Context, params protocolv2.ThreadMetadataUpdateParams) (protocolv2.ThreadMetadataUpdateResponse, error) {
	projectID, present := nullableValue(params.ProjectID)
	if !present {
		fake.t.Fatal("project update has no project id")
	}
	*fake.events = append(*fake.events, "project:"+params.ThreadID)
	fake.projects[params.ThreadID] = projectID
	return protocolv2.ThreadMetadataUpdateResponse{Thread: fake.thread(params.ThreadID)}, nil
}

func (fake *fakeSplitInstallThreads) thread(id string) protocolv2.Thread {
	thread := protocolv2.Thread{
		ID: id, SessionID: id, CWD: fake.cwd, ModelProvider: fake.provider,
		Path: protocolv2.Value(fake.paths[id]), Status: protocolv2.NewThreadStatusIdle(),
		Turns: []protocolv2.Turn{{ID: "turn-1", Items: []protocolv2.ThreadItem{}}},
	}
	if projectID := fake.projects[id]; projectID != "" {
		thread.ProjectID = *protocolv2.Value(projectID)
	}
	return thread
}

func TestInstallSplitConvergesInManifestOrder(t *testing.T) {
	root := t.TempDir()
	repo := t.TempDir()
	sourceHome := t.TempDir()
	sourceID := "019f5eb8-06b5-7813-84a2-f5ec6b85a473"
	writeSplitSource(t, sourceHome, repo, sourceID)
	_, receipt, err := inspectAll(t, PartitionInspectRequest{CodexHome: sourceHome, SessionID: sourceID})
	if err != nil {
		t.Fatal(err)
	}
	plan, err := PlanPartition(context.Background(), PartitionPlanRequest{Receipt: receipt, Parts: standardSplitIntent()})
	if err != nil {
		t.Fatal(err)
	}
	executed, err := ExecuteSplit(context.Background(), SplitExecuteRequest{
		Plan: plan, OutputCodexHome: filepath.Join(root, "staging"),
	})
	if err != nil {
		t.Fatal(err)
	}
	manifest, err := validatePublishedSplitManifest(executed.ManifestPath)
	if err != nil {
		t.Fatal(err)
	}

	projectID := "project-1"
	events := []string{}
	installCalls := map[string]int{}
	paths := map[string]string{}
	threads := &fakeSplitInstallThreads{
		t: t, cwd: repo, paths: paths, visible: map[string]bool{}, projects: map[string]string{},
		resumeErrors: map[string]error{manifest.Parts[0].SessionID: errors.New("response lost")},
		events:       &events, provider: "target", defaultModel: "target-model",
	}
	dependencies := splitInstallDependencies{
		install: func(_ context.Context, request rolloutInstallRequest) (string, error) {
			*threads.events = append(*threads.events, "install:"+request.ThreadID)
			installCalls[request.ThreadID]++
			path := filepath.Join("/destination/.codex", filepath.FromSlash(request.RelativePath))
			paths[request.ThreadID] = path
			if installCalls[request.ThreadID] > 1 {
				return path, errors.New("no-clobber collision")
			}
			return path, nil
		},
		verifyInstall: func(context.Context, rolloutInstallDestination, string, string) error { return nil },
		connect: func(rolloutInstallDestination, string) (destinationAppServerConnection, error) {
			return destinationAppServerConnection{
				projects: &fakeSplitInstallProjects{
					projects: []protocolv2.Project{{ID: projectID, Metadata: map[string]string{}, Roots: []protocolv2.ProjectRoot{{Path: repo}}}},
					events:   &events,
				},
				threads: threads,
				waitSettings: func(context.Context, string, string, string, string) error {
					t.Fatal("unexpected settings wait")
					return nil
				},
				close: func() error { return nil },
			}, nil
		},
	}
	request := SplitInstallRequest{
		SplitManifestPath: executed.ManifestPath, Host: "local", CWD: repo,
	}
	result, err := installSplitWith(context.Background(), request, dependencies)
	if err != nil {
		t.Fatal(err)
	}
	if result.NativeProjectID != projectID {
		t.Fatalf("native_project_id=%q, want %q", result.NativeProjectID, projectID)
	}
	wantEvents := []string{"project-list"}
	for _, part := range manifest.Parts {
		wantEvents = append(wantEvents, "install:"+part.SessionID, "resume:"+part.SessionID, "project:"+part.SessionID)
	}
	if !reflect.DeepEqual(events, wantEvents) {
		t.Fatalf("events=%v, want %v", events, wantEvents)
	}
	for _, part := range result.Parts {
		if part.State != splitInstallReady {
			t.Fatalf("part=%#v", part)
		}
	}

	events = nil
	threads.visible = map[string]bool{}
	result, err = installSplitWith(context.Background(), request, dependencies)
	if err != nil {
		t.Fatal(err)
	}
	wantEvents = []string{"project-list"}
	for _, part := range manifest.Parts {
		wantEvents = append(wantEvents, "install:"+part.SessionID)
	}
	if !reflect.DeepEqual(events, wantEvents) {
		t.Fatalf("rerun events=%v, want %v", events, wantEvents)
	}
	for _, part := range result.Parts {
		if part.State != splitInstallReady {
			t.Fatalf("rerun part=%#v", part)
		}
	}
}

func TestVerifiedSplitInstallContentRejectsStagingDrift(t *testing.T) {
	root := t.TempDir()
	repo := t.TempDir()
	sourceHome := t.TempDir()
	sourceID := "019f5eb8-06b5-7813-84a2-f5ec6b85a473"
	writeSplitSource(t, sourceHome, repo, sourceID)
	_, receipt, err := inspectAll(t, PartitionInspectRequest{CodexHome: sourceHome, SessionID: sourceID})
	if err != nil {
		t.Fatal(err)
	}
	plan, err := PlanPartition(context.Background(), PartitionPlanRequest{Receipt: receipt, Parts: standardSplitIntent()})
	if err != nil {
		t.Fatal(err)
	}
	executed, err := ExecuteSplit(context.Background(), SplitExecuteRequest{
		Plan: plan, OutputCodexHome: filepath.Join(root, "staging"),
	})
	if err != nil {
		t.Fatal(err)
	}
	manifest, err := validatePublishedSplitManifest(executed.ManifestPath)
	if err != nil {
		t.Fatal(err)
	}
	part := manifest.Parts[0]
	file, err := os.OpenFile(part.RolloutPath, os.O_APPEND|os.O_WRONLY, 0)
	if err != nil {
		t.Fatal(err)
	}
	if _, err := file.WriteString("\n"); err != nil {
		_ = file.Close()
		t.Fatal(err)
	}
	if err := file.Close(); err != nil {
		t.Fatal(err)
	}
	if _, err := verifiedSplitInstallContent(part, repo); err == nil || !strings.Contains(err.Error(), "digest") {
		t.Fatalf("error=%v", err)
	}
}

func TestInstallLocalRolloutRejectsSymlinkParent(t *testing.T) {
	codexHome := t.TempDir()
	outside := t.TempDir()
	cwd := t.TempDir()
	t.Setenv("CODEX_HOME", codexHome)
	if err := os.Symlink(outside, filepath.Join(codexHome, "sessions")); err != nil {
		t.Fatal(err)
	}
	threadID := "019f5eb8-06b5-7813-84a2-f5ec6b85a474"
	relative := filepath.ToSlash(filepath.Join("sessions", "2026", "09", "01", "rollout-2026-09-01T00-00-00-"+threadID+".jsonl"))
	_, err := installRollout(context.Background(), rolloutInstallRequest{
		ThreadID: threadID, Destination: rolloutInstallDestination{Kind: rolloutInstallLocal},
		CWD: cwd, RelativePath: relative, Content: []byte("{}\n"),
	})
	if err == nil || !strings.Contains(err.Error(), "symlink") {
		t.Fatalf("error=%v", err)
	}
	if _, err := os.Stat(filepath.Join(outside, "2026")); !os.IsNotExist(err) {
		t.Fatalf("symlink target was modified: %v", err)
	}
}
