package sessionmanagement

import (
	"context"
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"regexp"
	"strings"

	"github.com/google/uuid"
	rollout "github.com/ronhuafeng/skills/harnesses/codex/rollout-go"
)

var sshHostPattern = regexp.MustCompile(`^[A-Za-z0-9][A-Za-z0-9._@-]*$`)
var sha256Pattern = regexp.MustCompile(`^[0-9a-f]{64}$`)

type RehomeRequest struct {
	ThreadID string `json:"thread_id"`
	Host     string `json:"host"`
	CWD      string `json:"cwd"`
}

type RehomeResult struct {
	ThreadID                 string `json:"thread_id"`
	Host                     string `json:"host"`
	CWD                      string `json:"cwd"`
	SourceRolloutPath        string `json:"source_rollout_path"`
	RolloutPath              string `json:"rollout_path"`
	SourceSHA256             string `json:"source_sha256"`
	DestinationSHA256        string `json:"destination_sha256"`
	DestinationStatus        string `json:"destination_status,omitempty"`
	DestinationModelProvider string `json:"destination_model_provider,omitempty"`
	DestinationDefaultModel  string `json:"destination_default_model,omitempty"`
	FinalModel               string `json:"final_model,omitempty"`
	ProviderRebound          bool   `json:"provider_rebound"`
	historicalModelProvider  string
	indexedModelProvider     string
	currentModel             string
}

type invalidRehomeRequestError struct{ err error }

func (err *invalidRehomeRequestError) Error() string { return err.err.Error() }
func (err *invalidRehomeRequestError) Unwrap() error { return err.err }

func IsInvalidRehomeRequest(err error) bool {
	var invalid *invalidRehomeRequestError
	return errors.As(err, &invalid)
}

type rehomeDependencies struct {
	install  func(context.Context, rolloutInstallRequest) (string, error)
	activate func(context.Context, RehomeResult) (rehomeActivationResult, error)
}

func EstablishRehomeDestination(ctx context.Context, request RehomeRequest) (RehomeResult, error) {
	return rehomeSession(ctx, request, rehomeDependencies{
		install:  installRollout,
		activate: activateRehomeDestination,
	})
}

func rehomeSession(ctx context.Context, request RehomeRequest, dependencies rehomeDependencies) (RehomeResult, error) {
	if err := ctx.Err(); err != nil {
		return RehomeResult{}, err
	}
	if err := validateRehomeRequest(request); err != nil {
		return RehomeResult{}, err
	}

	codexHome, err := resolveRehomeCodexHome()
	if err != nil {
		return RehomeResult{}, &invalidRehomeRequestError{err: err}
	}
	sourcePath, err := rollout.ResolveSessionFile(codexHome, request.ThreadID, false)
	if err != nil {
		return RehomeResult{}, fmt.Errorf("resolve active source rollout: %w", err)
	}
	sourceContent, err := os.ReadFile(sourcePath)
	if err != nil {
		return RehomeResult{}, fmt.Errorf("read source rollout: %w", err)
	}
	sourceSHA256 := hashBytes(sourceContent)
	relativePath, err := filepath.Rel(codexHome, sourcePath)
	if err != nil || relativePath == "." || strings.HasPrefix(relativePath, ".."+string(filepath.Separator)) ||
		!strings.HasPrefix(relativePath, "sessions"+string(filepath.Separator)) {
		return RehomeResult{}, fmt.Errorf("source rollout is outside active sessions: %s", sourcePath)
	}
	meta, err := rollout.SessionMeta(sourcePath)
	if err != nil {
		return RehomeResult{}, err
	}
	if meta.ID != request.ThreadID || meta.SessionID != request.ThreadID {
		return RehomeResult{}, fmt.Errorf("source rollout identity does not match thread_id")
	}
	settings, err := rollout.ExecutionSettings(sourcePath)
	if err != nil {
		return RehomeResult{}, fmt.Errorf("project source model and provider: %w", err)
	}
	historicalProvider := ""
	if meta.ModelProvider != nil {
		historicalProvider = *meta.ModelProvider
	}
	if settings.ModelProvider == "" {
		return RehomeResult{}, fmt.Errorf("source rollout has no persisted current model provider")
	}
	if settings.Model == "" {
		return RehomeResult{}, fmt.Errorf("source rollout has no persisted current model")
	}
	content, err := rollout.RebindResumeAndIndexedCWD(sourcePath, request.CWD)
	if err != nil {
		return RehomeResult{}, fmt.Errorf("rebind Default Resume CWD and Indexed Thread CWD: %w", err)
	}
	destinationSHA256 := hashBytes(content)
	destinationPath, err := dependencies.install(ctx, rolloutInstallRequest{
		ThreadID: request.ThreadID,
		Destination: rolloutInstallDestination{
			Kind: rolloutInstallSSH,
			Host: request.Host,
		},
		CWD:          request.CWD,
		RelativePath: filepath.ToSlash(relativePath),
		Content:      content,
	})
	result := RehomeResult{
		ThreadID:                request.ThreadID,
		Host:                    request.Host,
		CWD:                     request.CWD,
		SourceRolloutPath:       sourcePath,
		RolloutPath:             destinationPath,
		SourceSHA256:            sourceSHA256,
		DestinationSHA256:       destinationSHA256,
		historicalModelProvider: historicalProvider,
		indexedModelProvider:    settings.ModelProvider,
		currentModel:            settings.Model,
	}
	if err != nil {
		return result, fmt.Errorf("install destination rollout: %w", err)
	}
	if err := verifyActiveRehomeSource(result); err != nil {
		return result, fmt.Errorf("destination_rollout_path=%s: verify source after remote install: %w", destinationPath, err)
	}

	activation, err := dependencies.activate(ctx, result)
	result.DestinationStatus = activation.Status
	result.DestinationModelProvider = activation.DestinationModelProvider
	result.DestinationDefaultModel = activation.DestinationDefaultModel
	result.FinalModel = activation.FinalModel
	result.ProviderRebound = activation.ProviderRebound
	if activation.RolloutPath != "" {
		result.RolloutPath = activation.RolloutPath
	}
	if err != nil {
		return result, fmt.Errorf("activate destination: %w", err)
	}
	if err := verifyActiveRehomeSource(result); err != nil {
		return result, fmt.Errorf("verify source before app archive: %w", err)
	}
	return result, nil
}

func verifyActiveRehomeSource(request RehomeResult) error {
	codexHome, err := resolveRehomeCodexHome()
	if err != nil {
		return err
	}
	activePath, err := rollout.ResolveSessionFile(codexHome, request.ThreadID, false)
	if err != nil {
		return fmt.Errorf("resolve active source rollout: %w", err)
	}
	if !sameExistingPath(activePath, request.SourceRolloutPath) {
		return fmt.Errorf("active source rollout path=%s, want %s", activePath, request.SourceRolloutPath)
	}
	content, err := os.ReadFile(activePath)
	if err != nil {
		return fmt.Errorf("read active source rollout: %w", err)
	}
	if hashBytes(content) != request.SourceSHA256 {
		return fmt.Errorf("active source rollout digest changed")
	}
	meta, err := rollout.SessionMeta(activePath)
	if err != nil {
		return err
	}
	if meta.ID != request.ThreadID || meta.SessionID != request.ThreadID {
		return fmt.Errorf("active source rollout identity does not match thread_id")
	}
	return nil
}

func validateRehomeRequest(request RehomeRequest) error {
	parsedID, err := uuid.Parse(request.ThreadID)
	if err != nil || parsedID.String() != request.ThreadID {
		return invalidRehomeRequest("thread_id must be a canonical UUID")
	}
	if !sshHostPattern.MatchString(request.Host) {
		return invalidRehomeRequest("host must be a safe SSH destination")
	}
	if !absoluteCleanPath(request.CWD) {
		return invalidRehomeRequest("cwd must be an absolute clean path")
	}
	return nil
}

func resolveRehomeCodexHome() (string, error) {
	codexHome := os.Getenv("CODEX_HOME")
	if codexHome == "" {
		home, err := os.UserHomeDir()
		if err != nil {
			return "", fmt.Errorf("resolve default codex_home: %w", err)
		}
		codexHome = filepath.Join(home, ".codex")
	}
	if !absoluteCleanPath(codexHome) {
		return "", fmt.Errorf("CODEX_HOME must be an absolute clean path")
	}
	info, err := os.Stat(codexHome)
	if err != nil {
		return "", err
	}
	if !info.IsDir() {
		return "", fmt.Errorf("codex_home is not a directory: %s", codexHome)
	}
	return codexHome, nil
}

func quotePOSIX(value string) string {
	return "'" + strings.ReplaceAll(value, "'", `'"'"'`) + "'"
}

func invalidRehomeRequest(format string, args ...any) error {
	return &invalidRehomeRequestError{err: fmt.Errorf(format, args...)}
}

func sameExistingPath(left string, right string) bool {
	if left == "" || right == "" {
		return false
	}
	leftPath, leftErr := normalizeExistingPath(left)
	rightPath, rightErr := normalizeExistingPath(right)
	return leftErr == nil && rightErr == nil && leftPath == rightPath
}

func existingPathInside(root string, candidate string) bool {
	rootPath, rootErr := normalizeExistingPath(root)
	candidatePath, candidateErr := normalizeExistingPath(candidate)
	return rootErr == nil && candidateErr == nil && pathInside(rootPath, candidatePath)
}
