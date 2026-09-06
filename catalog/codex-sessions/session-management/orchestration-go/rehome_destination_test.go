package sessionmanagement

import (
	"context"
	"errors"
	"strings"
	"testing"

	"github.com/ronhuafeng/llm-go/codexsdk/protocolv2"
)

const rehomeRemotePath = "/remote/.codex/sessions/rollout.jsonl"

type fakeRehomeDestinationConfig struct {
	provider string
	model    string
	params   protocolv2.ConfigReadParams
}

func (fake *fakeRehomeDestinationConfig) Read(_ context.Context, params protocolv2.ConfigReadParams) (protocolv2.ConfigReadResponse, error) {
	fake.params = params
	return protocolv2.ConfigReadResponse{Config: protocolv2.Config{
		ModelProvider: protocolv2.Value(fake.provider), Model: protocolv2.Value(fake.model),
	}}, nil
}

type fakeRehomeDestinationModels struct {
	models []protocolv2.Model
	calls  int
}

func (fake *fakeRehomeDestinationModels) List(context.Context, protocolv2.ModelListParams) (protocolv2.ModelListResponse, error) {
	fake.calls++
	return protocolv2.ModelListResponse{Data: fake.models}, nil
}

type fakeRehomeDestinationThreads struct {
	currentProvider string
	currentModel    string
	idle            bool
	resumeParams    protocolv2.ThreadResumeParams
	settingsParams  protocolv2.ThreadSettingsUpdateParams
	settingsErr     error
}

func (fake *fakeRehomeDestinationThreads) Read(context.Context, protocolv2.ThreadReadParams) (protocolv2.ThreadReadResponse, error) {
	thread := successfulRehomeThread(fake.currentProvider)
	if !fake.idle {
		thread.Status = protocolv2.NewThreadStatusNotLoaded()
	}
	return protocolv2.ThreadReadResponse{Thread: thread}, nil
}

func (fake *fakeRehomeDestinationThreads) Resume(_ context.Context, params protocolv2.ThreadResumeParams) (protocolv2.ThreadResumeResponse, error) {
	fake.resumeParams = params
	provider := fake.currentProvider
	model := fake.currentModel
	if value, present := nullableValue(params.ModelProvider); present {
		provider = value
	}
	if value, present := nullableValue(params.Model); present {
		model = value
	}
	response := successfulRehomeResumeResponse(provider, model)
	return response, nil
}

func (fake *fakeRehomeDestinationThreads) SettingsUpdate(_ context.Context, params protocolv2.ThreadSettingsUpdateParams) (protocolv2.ThreadSettingsUpdateResponse, error) {
	fake.settingsParams = params
	if fake.settingsErr != nil {
		return protocolv2.ThreadSettingsUpdateResponse{}, fake.settingsErr
	}
	if model, present := nullableValue(params.Model); present {
		fake.currentModel = model
	}
	return protocolv2.ThreadSettingsUpdateResponse{}, nil
}

func (fake *fakeRehomeDestinationThreads) MetadataUpdate(context.Context, protocolv2.ThreadMetadataUpdateParams) (protocolv2.ThreadMetadataUpdateResponse, error) {
	return protocolv2.ThreadMetadataUpdateResponse{}, nil
}

func successfulRehomeThread(provider string) protocolv2.Thread {
	return protocolv2.Thread{
		ID: rehomeSessionID, SessionID: rehomeSessionID, CWD: "/target/workspace",
		ModelProvider: provider, Path: protocolv2.Value(rehomeRemotePath),
		Status: protocolv2.NewThreadStatusIdle(), Turns: []protocolv2.Turn{},
	}
}

func successfulRehomeResumeResponse(provider string, model string) protocolv2.ThreadResumeResponse {
	thread := successfulRehomeThread("historical")
	return protocolv2.ThreadResumeResponse{
		Thread: thread, CWD: "/target/workspace",
		ModelProvider: provider, Model: model,
	}
}

func rehomeActivationRequest(provider string, model string) RehomeResult {
	return RehomeResult{
		ThreadID: rehomeSessionID, Host: "remote-host", CWD: "/target/workspace",
		RolloutPath: rehomeRemotePath, historicalModelProvider: "historical",
		indexedModelProvider: provider, currentModel: model,
	}
}

func TestActivateRehomeDestinationKeepsMatchingProvider(t *testing.T) {
	config := &fakeRehomeDestinationConfig{provider: "target", model: "target-default"}
	models := &fakeRehomeDestinationModels{}
	threads := &fakeRehomeDestinationThreads{currentProvider: "target", currentModel: "original"}
	closeCount := 0
	result, err := activateRehomeDestinationWith(context.Background(), rehomeActivationRequest("target", "original"), rehomeDestinationDependencies{
		connect: func(rolloutInstallDestination, string) (destinationAppServerConnection, error) {
			return destinationAppServerConnection{config: config, models: models, threads: threads,
				waitSettings: func(context.Context, string, string, string, string) error {
					t.Fatal("unexpected settings wait")
					return nil
				},
				close: func() error { closeCount++; return nil }}, nil
		},
	})
	if err != nil {
		t.Fatal(err)
	}
	if threads.resumeParams.ModelProvider != nil || threads.resumeParams.Model != nil || models.calls != 0 {
		t.Fatalf("resume=%#v model_calls=%d", threads.resumeParams, models.calls)
	}
	if result.ProviderRebound || result.DestinationModelProvider != "target" ||
		result.FinalModel != "original" || closeCount != 1 {
		t.Fatalf("result=%#v close=%d", result, closeCount)
	}
}

func TestActivateRehomeDestinationRebindsOnlyMismatchedProviderAndRestoresModel(t *testing.T) {
	config := &fakeRehomeDestinationConfig{provider: "target", model: "bridge"}
	models := &fakeRehomeDestinationModels{}
	threads := &fakeRehomeDestinationThreads{currentProvider: "source", currentModel: "original"}
	waited := false
	result, err := activateRehomeDestinationWith(context.Background(), rehomeActivationRequest("source", "original"), rehomeDestinationDependencies{
		connect: func(rolloutInstallDestination, string) (destinationAppServerConnection, error) {
			return destinationAppServerConnection{config: config, models: models, threads: threads,
				waitSettings: func(_ context.Context, id, model, provider, cwd string) error {
					waited = id == rehomeSessionID && model == "original" && provider == "target" && cwd == "/target/workspace"
					return nil
				}, close: func() error { return nil }}, nil
		},
	})
	if err != nil {
		t.Fatal(err)
	}
	resumeProvider, _ := nullableValue(threads.resumeParams.ModelProvider)
	resumeModel, _ := nullableValue(threads.resumeParams.Model)
	restoredModel, _ := nullableValue(threads.settingsParams.Model)
	if resumeProvider != "target" || resumeModel != "bridge" || restoredModel != "original" || !waited {
		t.Fatalf("resume=%#v settings=%#v waited=%v", threads.resumeParams, threads.settingsParams, waited)
	}
	if !result.ProviderRebound || result.FinalModel != "original" {
		t.Fatalf("result=%#v", result)
	}
}

func TestActivateRehomeDestinationStopsWhenOriginalModelIsIncompatible(t *testing.T) {
	config := &fakeRehomeDestinationConfig{provider: "target", model: "bridge"}
	threads := &fakeRehomeDestinationThreads{
		currentProvider: "source", currentModel: "original",
		settingsErr: errors.New("model is not supported"),
	}
	result, err := activateRehomeDestinationWith(context.Background(), rehomeActivationRequest("source", "original"), rehomeDestinationDependencies{
		connect: func(rolloutInstallDestination, string) (destinationAppServerConnection, error) {
			return destinationAppServerConnection{config: config, models: &fakeRehomeDestinationModels{}, threads: threads,
				waitSettings: func(context.Context, string, string, string, string) error { t.Fatal("unexpected wait"); return nil },
				close:        func() error { return nil }}, nil
		},
	})
	if err == nil || !strings.Contains(err.Error(), "incompatible") || !result.ProviderRebound {
		t.Fatalf("result=%#v error=%v", result, err)
	}
}

func TestActivateRehomeDestinationDoesNotInferExecutionSettingsFromIdleThread(t *testing.T) {
	threads := &fakeRehomeDestinationThreads{
		currentProvider: "source", currentModel: "original", idle: true,
	}
	_, err := activateRehomeDestinationWith(context.Background(), rehomeActivationRequest("source", "original"), rehomeDestinationDependencies{
		connect: func(rolloutInstallDestination, string) (destinationAppServerConnection, error) {
			return destinationAppServerConnection{
				config: &fakeRehomeDestinationConfig{provider: "target", model: "bridge"},
				models: &fakeRehomeDestinationModels{}, threads: threads,
				waitSettings: func(context.Context, string, string, string, string) error { return nil },
				close:        func() error { return nil },
			}, nil
		},
	})
	if err == nil || !strings.Contains(err.Error(), "already loaded") {
		t.Fatalf("error=%v", err)
	}
	if threads.resumeParams.ThreadID != "" || threads.settingsParams.ThreadID != "" {
		t.Fatalf("unexpected mutation: resume=%#v settings=%#v", threads.resumeParams, threads.settingsParams)
	}
}

func TestChooseRehomeBridgeModelUsesAlternateWhenDefaultEqualsOriginal(t *testing.T) {
	models := &fakeRehomeDestinationModels{models: []protocolv2.Model{{Model: "original"}, {Model: "alternate"}}}
	got, err := chooseRehomeBridgeModel(context.Background(), models, "original", "original")
	if err != nil || got != "alternate" || models.calls != 1 {
		t.Fatalf("model=%q calls=%d error=%v", got, models.calls, err)
	}
}
