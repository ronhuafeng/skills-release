package sessionmanagement

import (
	"context"
	"fmt"
	"os"
	"time"

	"github.com/ronhuafeng/llm-go/codexsdk"
	"github.com/ronhuafeng/llm-go/codexsdk/protocolv2"
)

const rehomeSettingsNotificationTimeout = 15 * time.Second

type rehomeActivationResult struct {
	Status                   string
	RolloutPath              string
	DestinationModelProvider string
	DestinationDefaultModel  string
	FinalModel               string
	ProviderRebound          bool
}

type destinationConfig interface {
	Read(context.Context, protocolv2.ConfigReadParams) (protocolv2.ConfigReadResponse, error)
}

type destinationModels interface {
	List(context.Context, protocolv2.ModelListParams) (protocolv2.ModelListResponse, error)
}

type destinationProjects interface {
	List(context.Context, protocolv2.ProjectListParams) (protocolv2.ProjectListResponse, error)
}

type destinationThreads interface {
	Read(context.Context, protocolv2.ThreadReadParams) (protocolv2.ThreadReadResponse, error)
	Resume(context.Context, protocolv2.ThreadResumeParams) (protocolv2.ThreadResumeResponse, error)
	SettingsUpdate(context.Context, protocolv2.ThreadSettingsUpdateParams) (protocolv2.ThreadSettingsUpdateResponse, error)
	MetadataUpdate(context.Context, protocolv2.ThreadMetadataUpdateParams) (protocolv2.ThreadMetadataUpdateResponse, error)
}

type destinationAppServerConnection struct {
	config       destinationConfig
	models       destinationModels
	projects     destinationProjects
	threads      destinationThreads
	waitSettings func(context.Context, string, string, string, string) error
	close        func() error
}

type rehomeDestinationDependencies struct {
	connect func(rolloutInstallDestination, string) (destinationAppServerConnection, error)
}

func activateRehomeDestination(ctx context.Context, request RehomeResult) (rehomeActivationResult, error) {
	return activateRehomeDestinationWith(ctx, request, rehomeDestinationDependencies{connect: connectDestinationAppServer})
}

func activateRehomeDestinationWith(ctx context.Context, request RehomeResult, dependencies rehomeDestinationDependencies) (rehomeActivationResult, error) {
	if err := ctx.Err(); err != nil {
		return rehomeActivationResult{}, err
	}

	destination := rolloutInstallDestination{Kind: rolloutInstallSSH, Host: request.Host}
	connection, err := dependencies.connect(destination, request.CWD)
	if err != nil {
		return rehomeActivationResult{}, fmt.Errorf("connect remote app-server over SSH: %w", err)
	}
	closeConnection := guardedClose(connection.close)
	defer func() { _ = closeConnection() }()

	result, err := activateInstalledRollout(ctx, request, connection)
	if err != nil {
		return result, err
	}
	if closeErr := closeConnection(); closeErr != nil {
		return result, fmt.Errorf("close remote app-server after verified resume: %w", closeErr)
	}
	return result, nil
}

func activateInstalledRollout(
	ctx context.Context,
	request RehomeResult,
	connection destinationAppServerConnection,
) (rehomeActivationResult, error) {
	configResponse, err := connection.config.Read(ctx, protocolv2.ConfigReadParams{CWD: protocolv2.Value(request.CWD)})
	if err != nil {
		return rehomeActivationResult{}, fmt.Errorf("read destination effective config for cwd: %w", err)
	}
	destinationProvider, ok := nullableValue(configResponse.Config.ModelProvider)
	if !ok || destinationProvider == "" {
		return rehomeActivationResult{}, fmt.Errorf("destination effective config has no model_provider")
	}
	destinationModel, ok := nullableValue(configResponse.Config.Model)
	if !ok || destinationModel == "" {
		return rehomeActivationResult{}, fmt.Errorf("destination effective config has no model")
	}
	result := rehomeActivationResult{
		RolloutPath:              request.RolloutPath,
		DestinationModelProvider: destinationProvider,
		DestinationDefaultModel:  destinationModel,
		FinalModel:               request.currentModel,
	}

	includeTurns := false
	read, readErr := connection.threads.Read(ctx, protocolv2.ThreadReadParams{
		ThreadID: request.ThreadID, IncludeTurns: &includeTurns,
	})
	if readErr != nil {
		return result, fmt.Errorf("read installed destination thread: %w", readErr)
	}
	if err := validateInstalledThread(read.Thread, request, request.indexedModelProvider); err != nil {
		return result, fmt.Errorf("destination preflight: %w", err)
	}
	switch read.Thread.Status.Kind() {
	case protocolv2.ThreadStatusKindIdle:
		return result, fmt.Errorf("destination task is already loaded; current execution provider and model cannot be proven")
	case protocolv2.ThreadStatusKindNotLoaded:
	default:
		return result, fmt.Errorf("destination preflight status=%s, want notLoaded", read.Thread.Status.Kind())
	}

	excludeTurns := true
	resume := protocolv2.ThreadResumeParams{ThreadID: request.ThreadID, ExcludeTurns: &excludeTurns}
	if request.indexedModelProvider != destinationProvider {
		bridgeModel, bridgeErr := chooseRehomeBridgeModel(ctx, connection.models, destinationModel, request.currentModel)
		if bridgeErr != nil {
			return result, bridgeErr
		}
		resume.ModelProvider = protocolv2.Value(destinationProvider)
		resume.Model = protocolv2.Value(bridgeModel)
		result.ProviderRebound = true
	}

	response, err := connection.threads.Resume(ctx, resume)
	if err != nil {
		return result, fmt.Errorf("resume destination thread through app-server: %w", err)
	}
	if err := validateRehomeResume(response, request, destinationProvider, request.currentModel, result.ProviderRebound); err != nil {
		return result, err
	}
	result.Status = string(response.Thread.Status.Kind())
	if path, present := nullableValue(response.Thread.Path); present {
		result.RolloutPath = path
	}

	if result.ProviderRebound {
		if _, err := connection.threads.SettingsUpdate(ctx, protocolv2.ThreadSettingsUpdateParams{
			ThreadID: request.ThreadID,
			Model:    protocolv2.Value(request.currentModel),
		}); err != nil {
			return result, fmt.Errorf("restore original model %q after provider rebind (model may be incompatible with destination provider %q): %w", request.currentModel, destinationProvider, err)
		}
		waitCtx, cancel := context.WithTimeout(ctx, rehomeSettingsNotificationTimeout)
		err = connection.waitSettings(waitCtx, request.ThreadID, request.currentModel, destinationProvider, request.CWD)
		cancel()
		if err != nil {
			return result, fmt.Errorf("verify persisted provider/model settings: %w", err)
		}
	}

	return result, nil
}

func validateInstalledThread(thread protocolv2.Thread, request RehomeResult, provider string) error {
	if thread.ID != request.ThreadID || thread.SessionID != request.ThreadID {
		return fmt.Errorf("thread_id=%s session_id=%s, want %s", thread.ID, thread.SessionID, request.ThreadID)
	}
	if thread.CWD != request.CWD {
		return fmt.Errorf("cwd=%s, want %s", thread.CWD, request.CWD)
	}
	if provider != "" && thread.ModelProvider != provider {
		return fmt.Errorf("model_provider=%s, want %s", thread.ModelProvider, provider)
	}
	path, present := nullableValue(thread.Path)
	if !present || path != request.RolloutPath {
		return fmt.Errorf("rollout_path=%s, want %s", path, request.RolloutPath)
	}
	return nil
}

func validateRehomeResume(response protocolv2.ThreadResumeResponse, request RehomeResult, provider string, originalModel string, rebound bool) error {
	rolloutPath, _ := nullableValue(response.Thread.Path)
	if response.Thread.ID != request.ThreadID || response.Thread.SessionID != request.ThreadID {
		return fmt.Errorf("remote app-server resumed thread_id=%s session_id=%s, want %s", response.Thread.ID, response.Thread.SessionID, request.ThreadID)
	}
	if response.CWD != request.CWD || response.Thread.CWD != request.CWD {
		return fmt.Errorf("remote app-server resumed cwd=%s thread_cwd=%s, want %s", response.CWD, response.Thread.CWD, request.CWD)
	}
	if response.Thread.Status.Kind() != protocolv2.ThreadStatusKindIdle {
		return fmt.Errorf("remote app-server resumed status=%s, want idle", response.Thread.Status.Kind())
	}
	if rolloutPath != request.RolloutPath {
		return fmt.Errorf("remote app-server resumed rollout_path=%s, want %s", rolloutPath, request.RolloutPath)
	}
	if response.ModelProvider != provider {
		return fmt.Errorf("remote app-server resumed current model_provider=%s, want %s", response.ModelProvider, provider)
	}
	if request.historicalModelProvider != "" && response.Thread.ModelProvider != request.historicalModelProvider {
		return fmt.Errorf("remote app-server resumed historical thread model_provider=%s, want %s", response.Thread.ModelProvider, request.historicalModelProvider)
	}
	if !rebound && response.Model != originalModel {
		return fmt.Errorf("remote app-server resumed model=%s, want preserved model %s", response.Model, originalModel)
	}
	return nil
}

func chooseRehomeBridgeModel(ctx context.Context, models destinationModels, destinationDefault string, originalModel string) (string, error) {
	if destinationDefault != originalModel {
		return destinationDefault, nil
	}
	limit := uint32(100)
	includeHidden := true
	var cursor *protocolv2.Nullable[string]
	for {
		page, err := models.List(ctx, protocolv2.ModelListParams{
			Cursor: cursor, IncludeHidden: protocolv2.Value(includeHidden), Limit: protocolv2.Value(limit),
		})
		if err != nil {
			return "", fmt.Errorf("list destination models for provider-rebind bridge: %w", err)
		}
		for _, model := range page.Data {
			if model.Model != "" && model.Model != originalModel {
				return model.Model, nil
			}
		}
		next, present := nullableValue(page.NextCursor)
		if !present || next == "" {
			break
		}
		cursor = protocolv2.Value(next)
	}
	return "", fmt.Errorf("destination has no alternate model needed to persist a provider rebind while preserving original model %q", originalModel)
}

func connectDestinationAppServer(
	destination rolloutInstallDestination,
	cwd string,
) (destinationAppServerConnection, error) {
	clientCWD := cwd
	command := []string{"codex", "app-server", "--stdio"}
	if destination.Kind == rolloutInstallSSH {
		var err error
		clientCWD, err = os.Getwd()
		if err != nil {
			return destinationAppServerConnection{}, fmt.Errorf("resolve local directory for SSH app-server client: %w", err)
		}
		command = []string{
			"ssh", "-o", "BatchMode=yes", destination.Host,
			"bash -lic 'exec codex app-server --stdio'",
		}
	} else if destination.Kind != rolloutInstallLocal {
		return destinationAppServerConnection{}, fmt.Errorf("unsupported app-server destination %q", destination.Kind)
	}
	settings := make(chan protocolv2.ThreadSettingsUpdatedNotification, 16)
	var handler codexsdk.ServerNotificationHandler = func(ctx context.Context, notification protocolv2.ServerNotification) error {
		wrapped, ok := notification.AsThreadSettingsUpdated()
		if !ok {
			return nil
		}
		select {
		case settings <- wrapped.Params:
			return nil
		case <-ctx.Done():
			return ctx.Err()
		}
	}
	client, err := newAppServerClientForCommandWithNotifications(
		clientCWD,
		"session-management-destination",
		"Session Management Destination",
		command,
		handler,
	)
	if err != nil {
		return destinationAppServerConnection{}, err
	}
	waitSettings := func(ctx context.Context, threadID string, model string, provider string, cwd string) error {
		for {
			select {
			case update := <-settings:
				if update.ThreadID == threadID && update.ThreadSettings.Model == model &&
					update.ThreadSettings.ModelProvider == provider && update.ThreadSettings.CWD == cwd {
					return nil
				}
			case <-ctx.Done():
				return ctx.Err()
			}
		}
	}
	return destinationAppServerConnection{
		config: client.Config(), models: client.Models(), projects: client.Project(), threads: client.Threads(),
		waitSettings: waitSettings, close: client.Close,
	}, nil
}
