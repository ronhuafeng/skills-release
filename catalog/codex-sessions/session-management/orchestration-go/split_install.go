package sessionmanagement

import (
	"context"
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"strings"

	"github.com/ronhuafeng/llm-go/codexsdk/protocolv2"
	rollout "github.com/ronhuafeng/skills/harnesses/codex/rollout-go"
)

const (
	splitInstallPending           = "pending"
	splitInstallUnknown           = "install_unknown"
	splitInstallInstalled         = "installed"
	splitInstallActivationUnknown = "activation_unknown"
	splitInstallVisible           = "visible"
	splitInstallProjectUnknown    = "project_unknown"
	splitInstallReady             = "ready"
)

type SplitInstallRequest struct {
	SplitManifestPath string `json:"split_manifest_path"`
	Host              string `json:"host"`
	CWD               string `json:"cwd"`
}

type SplitInstallPartResult struct {
	PartID            string `json:"part_id"`
	SessionID         string `json:"session_id"`
	RolloutPath       string `json:"rollout_path,omitempty"`
	DestinationSHA256 string `json:"destination_sha256,omitempty"`
	State             string `json:"state"`
}

type SplitInstallResult struct {
	SplitManifestPath string                   `json:"split_manifest_path"`
	Host              string                   `json:"host"`
	CWD               string                   `json:"cwd"`
	NativeProjectID   string                   `json:"native_project_id"`
	Parts             []SplitInstallPartResult `json:"parts"`
}

type invalidSplitInstallRequestError struct{ err error }

func (err *invalidSplitInstallRequestError) Error() string { return err.err.Error() }
func (err *invalidSplitInstallRequestError) Unwrap() error { return err.err }

func IsInvalidSplitInstallRequest(err error) bool {
	var invalid *invalidSplitInstallRequestError
	return errors.As(err, &invalid)
}

type splitInstallDependencies struct {
	install       func(context.Context, rolloutInstallRequest) (string, error)
	verifyInstall func(context.Context, rolloutInstallDestination, string, string) error
	connect       func(rolloutInstallDestination, string) (destinationAppServerConnection, error)
}

func InstallSplit(ctx context.Context, request SplitInstallRequest) (SplitInstallResult, error) {
	return installSplitWith(ctx, request, splitInstallDependencies{
		install:       installRollout,
		verifyInstall: verifyRolloutInstall,
		connect:       connectDestinationAppServer,
	})
}

func installSplitWith(
	ctx context.Context,
	request SplitInstallRequest,
	dependencies splitInstallDependencies,
) (SplitInstallResult, error) {
	result := newSplitInstallResult(request)
	if err := ctx.Err(); err != nil {
		return result, err
	}
	destination, err := validateSplitInstallRequest(request)
	if err != nil {
		return result, err
	}
	manifest, err := validatePublishedSplitManifest(request.SplitManifestPath)
	if err != nil {
		return result, fmt.Errorf("validate split manifest: %w", err)
	}
	result.Parts = make([]SplitInstallPartResult, len(manifest.Parts))
	for index, part := range manifest.Parts {
		result.Parts[index] = SplitInstallPartResult{
			PartID: part.PartID, SessionID: part.SessionID, State: splitInstallPending,
		}
	}

	connection, err := dependencies.connect(destination, request.CWD)
	if err != nil {
		return result, fmt.Errorf("connect destination app-server: %w", err)
	}
	closeConnection := guardedClose(connection.close)
	defer func() { _ = closeConnection() }()

	projectID, err := resolveSplitInstallProject(ctx, connection.projects, request.CWD)
	if err != nil {
		return result, err
	}
	result.NativeProjectID = projectID
	for index, part := range manifest.Parts {
		if err := installSplitPart(ctx, request, projectID, destination, part, &result.Parts[index], connection, dependencies); err != nil {
			return result, err
		}
	}
	if err := closeConnection(); err != nil {
		return result, fmt.Errorf("close destination app-server after verified install: %w", err)
	}
	return result, nil
}

func newSplitInstallResult(request SplitInstallRequest) SplitInstallResult {
	return SplitInstallResult{
		SplitManifestPath: request.SplitManifestPath,
		Host:              request.Host,
		CWD:               request.CWD,
		Parts:             []SplitInstallPartResult{},
	}
}

func validateSplitInstallRequest(request SplitInstallRequest) (rolloutInstallDestination, error) {
	if !absoluteCleanPath(request.SplitManifestPath) {
		return rolloutInstallDestination{}, invalidSplitInstallRequest("split_manifest_path must be an absolute clean path")
	}
	if !absoluteCleanPath(request.CWD) {
		return rolloutInstallDestination{}, invalidSplitInstallRequest("cwd must be an absolute clean path")
	}
	if request.Host == rolloutInstallLocal {
		return rolloutInstallDestination{Kind: rolloutInstallLocal}, nil
	}
	if !sshHostPattern.MatchString(request.Host) {
		return rolloutInstallDestination{}, invalidSplitInstallRequest("host must be local or a safe SSH destination")
	}
	return rolloutInstallDestination{Kind: rolloutInstallSSH, Host: request.Host}, nil
}

func resolveSplitInstallProject(
	ctx context.Context,
	projects destinationProjects,
	cwd string,
) (string, error) {
	if projects == nil {
		return "", fmt.Errorf("destination app-server does not expose projects")
	}
	limit := uint32(100)
	var cursor *protocolv2.Nullable[string]
	match := ""
	for {
		response, err := projects.List(ctx, protocolv2.ProjectListParams{
			Cursor: cursor, Limit: protocolv2.Value(limit),
		})
		if err != nil {
			return "", fmt.Errorf("list destination projects: %w", err)
		}
		for _, project := range response.Data {
			for _, root := range project.Roots {
				if root.Path != cwd {
					continue
				}
				if project.ID == "" {
					return "", fmt.Errorf("destination project matching cwd %q has no id", cwd)
				}
				if match != "" && match != project.ID {
					return "", fmt.Errorf("more than one destination project matches cwd %q", cwd)
				}
				match = project.ID
			}
		}
		next, present := nullableValue(response.NextCursor)
		if !present || next == "" {
			break
		}
		cursor = protocolv2.Value(next)
	}
	if match == "" {
		return "", fmt.Errorf("destination has no saved project whose root exactly matches cwd %q", cwd)
	}
	return match, nil
}

func installSplitPart(
	ctx context.Context,
	request SplitInstallRequest,
	desiredProjectID string,
	destination rolloutInstallDestination,
	part splitManifestPart,
	result *SplitInstallPartResult,
	connection destinationAppServerConnection,
	dependencies splitInstallDependencies,
) error {
	content, err := verifiedSplitInstallContent(part, request.CWD)
	if err != nil {
		return fmt.Errorf("part %s: rebind destination cwd: %w", part.PartID, err)
	}
	digest := hashBytes(content)
	result.DestinationSHA256 = digest
	manifestRoot := filepath.Dir(request.SplitManifestPath)
	relativePath, err := filepath.Rel(manifestRoot, part.RolloutPath)
	if err != nil || relativePath == "." || filepath.IsAbs(relativePath) ||
		strings.HasPrefix(relativePath, ".."+string(filepath.Separator)) {
		return fmt.Errorf("part %s: rollout path is outside the split bundle", part.PartID)
	}
	destinationPath, installErr := dependencies.install(ctx, rolloutInstallRequest{
		ThreadID:     part.SessionID,
		Destination:  destination,
		CWD:          request.CWD,
		RelativePath: filepath.ToSlash(relativePath),
		Content:      content,
	})
	result.RolloutPath = destinationPath
	if destinationPath == "" {
		result.State = splitInstallUnknown
		return fmt.Errorf("part %s: install destination rollout: %w", part.PartID, installErr)
	}
	if verifyErr := dependencies.verifyInstall(ctx, destination, destinationPath, digest); verifyErr != nil {
		result.State = splitInstallUnknown
		if installErr != nil {
			return fmt.Errorf("part %s: install result is unknown (%v); readback failed: %w", part.PartID, installErr, verifyErr)
		}
		return fmt.Errorf("part %s: verify destination rollout: %w", part.PartID, verifyErr)
	}
	result.State = splitInstallInstalled

	activationRequest := RehomeResult{
		ThreadID: part.SessionID, CWD: request.CWD, RolloutPath: destinationPath,
	}
	preflight, err := readInstalledSplitThread(ctx, connection.threads, activationRequest)
	if err != nil {
		result.State = splitInstallActivationUnknown
		return fmt.Errorf("part %s: read installed destination task: %w", part.PartID, err)
	}
	observedProjectID, assigned := nullableProjectID(preflight.ProjectID)
	if assigned {
		result.State = splitInstallVisible
		if observedProjectID != desiredProjectID {
			return fmt.Errorf("part %s: destination task already belongs to project %q", part.PartID, observedProjectID)
		}
		result.State = splitInstallReady
		return nil
	}
	activationErr := activateSplitRollout(ctx, activationRequest, preflight, connection.threads)
	thread, readErr := readActiveSplitThread(ctx, connection.threads, activationRequest)
	if readErr != nil {
		result.State = splitInstallActivationUnknown
		if activationErr != nil {
			return fmt.Errorf("part %s: activation is unknown (%v); readback failed: %w", part.PartID, activationErr, readErr)
		}
		return fmt.Errorf("part %s: read back active destination task: %w", part.PartID, readErr)
	}
	result.State = splitInstallVisible

	observedProjectID, assigned = nullableProjectID(thread.ProjectID)
	if assigned && observedProjectID != desiredProjectID {
		return fmt.Errorf("part %s: destination task already belongs to project %q", part.PartID, observedProjectID)
	}
	if !assigned {
		_, updateErr := connection.threads.MetadataUpdate(ctx, protocolv2.ThreadMetadataUpdateParams{
			ThreadID:  part.SessionID,
			ProjectID: protocolv2.Value(desiredProjectID),
		})
		if updateErr != nil {
			readback, readErr := readActiveSplitThread(ctx, connection.threads, activationRequest)
			if readErr != nil {
				result.State = splitInstallProjectUnknown
				return fmt.Errorf("part %s: project assignment is unknown (%v); readback failed: %w", part.PartID, updateErr, readErr)
			}
			observedProjectID, assigned = nullableProjectID(readback.ProjectID)
			if !assigned || observedProjectID != desiredProjectID {
				result.State = splitInstallProjectUnknown
				return fmt.Errorf("part %s: project assignment is unknown: %w", part.PartID, updateErr)
			}
		}
	}
	final, err := readActiveSplitThread(ctx, connection.threads, activationRequest)
	if err != nil {
		result.State = splitInstallProjectUnknown
		return fmt.Errorf("part %s: read back project assignment: %w", part.PartID, err)
	}
	observedProjectID, assigned = nullableProjectID(final.ProjectID)
	if !assigned || observedProjectID != desiredProjectID {
		result.State = splitInstallProjectUnknown
		return fmt.Errorf("part %s: project readback=%q, want %q", part.PartID, observedProjectID, desiredProjectID)
	}
	result.State = splitInstallReady
	return nil
}

func verifiedSplitInstallContent(part splitManifestPart, cwd string) ([]byte, error) {
	raw, err := os.ReadFile(part.RolloutPath)
	if err != nil {
		return nil, err
	}
	if hashBytes(raw) != part.OutputSHA256 {
		return nil, fmt.Errorf("staging rollout digest no longer matches manifest")
	}
	return rollout.RebindResumeAndIndexedCWDBytes(part.RolloutPath, raw, cwd)
}

func activateSplitRollout(
	ctx context.Context,
	request RehomeResult,
	thread protocolv2.Thread,
	threads destinationThreads,
) error {
	switch thread.Status.Kind() {
	case protocolv2.ThreadStatusKindIdle:
		return nil
	case protocolv2.ThreadStatusKindNotLoaded:
	default:
		return fmt.Errorf("installed task status=%s, want notLoaded or idle", thread.Status.Kind())
	}

	excludeTurns := true
	response, err := threads.Resume(ctx, protocolv2.ThreadResumeParams{
		ThreadID: request.ThreadID, ExcludeTurns: &excludeTurns,
	})
	if err != nil {
		return fmt.Errorf("resume installed task: %w", err)
	}
	rolloutPath, present := nullableValue(response.Thread.Path)
	if response.Thread.ID != request.ThreadID || response.Thread.SessionID != request.ThreadID {
		return fmt.Errorf("resumed thread_id=%s session_id=%s, want %s", response.Thread.ID, response.Thread.SessionID, request.ThreadID)
	}
	if response.CWD != request.CWD || response.Thread.CWD != request.CWD {
		return fmt.Errorf("resumed cwd=%s thread_cwd=%s, want %s", response.CWD, response.Thread.CWD, request.CWD)
	}
	if response.Thread.Status.Kind() != protocolv2.ThreadStatusKindIdle {
		return fmt.Errorf("resumed status=%s, want idle", response.Thread.Status.Kind())
	}
	if !present || rolloutPath != request.RolloutPath {
		return fmt.Errorf("resumed rollout_path=%s, want %s", rolloutPath, request.RolloutPath)
	}
	return nil
}

func readInstalledSplitThread(
	ctx context.Context,
	threads destinationThreads,
	request RehomeResult,
) (protocolv2.Thread, error) {
	includeTurns := true
	response, err := threads.Read(ctx, protocolv2.ThreadReadParams{
		ThreadID: request.ThreadID, IncludeTurns: &includeTurns,
	})
	if err != nil {
		return protocolv2.Thread{}, err
	}
	if err := validateInstalledThread(response.Thread, request, ""); err != nil {
		return protocolv2.Thread{}, err
	}
	if len(response.Thread.Turns) == 0 {
		return protocolv2.Thread{}, fmt.Errorf("destination task has no persisted turns")
	}
	status := response.Thread.Status.Kind()
	if status != protocolv2.ThreadStatusKindIdle && status != protocolv2.ThreadStatusKindNotLoaded {
		return protocolv2.Thread{}, fmt.Errorf("destination task status=%s, want notLoaded or idle", status)
	}
	return response.Thread, nil
}

func readActiveSplitThread(
	ctx context.Context,
	threads destinationThreads,
	request RehomeResult,
) (protocolv2.Thread, error) {
	thread, err := readInstalledSplitThread(ctx, threads, request)
	if err != nil {
		return protocolv2.Thread{}, err
	}
	if thread.Status.Kind() != protocolv2.ThreadStatusKindIdle {
		return protocolv2.Thread{}, fmt.Errorf("destination task status=%s, want idle", thread.Status.Kind())
	}
	return thread, nil
}

func nullableProjectID(value protocolv2.Nullable[string]) (string, bool) {
	if value.Value == nil || *value.Value == "" {
		return "", false
	}
	return *value.Value, true
}

func invalidSplitInstallRequest(format string, args ...any) error {
	return &invalidSplitInstallRequestError{err: fmt.Errorf(format, args...)}
}
