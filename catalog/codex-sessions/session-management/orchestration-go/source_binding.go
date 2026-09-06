package sessionmanagement

import (
	"context"
	"crypto/sha256"
	"fmt"
	"os"
	"path/filepath"
	"strings"

	rollout "github.com/ronhuafeng/skills/harnesses/codex/rollout-go"
)

type contentSourceRequest struct {
	CodexHome       string
	SessionID       string
	IncludeArchived bool
}

type partitionPreflight struct {
	Selected       SelectedRollout
	RawRecordCount int
	SemanticCount  int
	CandidateCount int
	TailOpen       bool
}

func preflightPartitionSource(
	ctx context.Context,
	req contentSourceRequest,
) (partitionPreflight, error) {
	path, err := resolveContentSource(ctx, req)
	if err != nil {
		return partitionPreflight{}, err
	}
	before, err := os.Stat(path)
	if err != nil {
		return partitionPreflight{}, err
	}
	if !before.Mode().IsRegular() {
		return partitionPreflight{}, fmt.Errorf("rollout is not a regular file: %s", path)
	}
	return inspectPartitionPrefix(ctx, req, path, before.Size())
}

func inspectPartitionPrefix(
	ctx context.Context,
	req contentSourceRequest,
	path string,
	throughOffset int64,
) (partitionPreflight, error) {
	before, err := os.Stat(path)
	if err != nil {
		return partitionPreflight{}, err
	}
	if !before.Mode().IsRegular() || throughOffset <= 0 || before.Size() < throughOffset {
		return partitionPreflight{}, sourceChanged()
	}
	hash := sha256.New()
	state := newPartitionScanState()
	rawCount := 0
	semanticCount := 0
	lastLine := 0
	next, err := rollout.ScanRange(path, rollout.ScanCursor{NextLine: 1}, throughOffset, func(record rollout.Record, _ rollout.ScanCursor) (bool, error) {
		if err := ctx.Err(); err != nil {
			return false, err
		}
		rawCount++
		lastLine = record.Line
		if rawCount == 1 {
			if _, err := rollout.DecodeSessionMeta(record); err != nil {
				return false, fmt.Errorf("%s:%d: %w", path, record.Line, err)
			}
		}
		_, content, err := state.consume(path, record)
		if err != nil {
			return false, err
		}
		if content != nil {
			semanticCount++
		}
		_, _ = hash.Write(record.Raw)
		_, _ = hash.Write([]byte{'\n'})
		return true, nil
	})
	if err != nil {
		return partitionPreflight{}, err
	}
	if next.Offset != throughOffset {
		return partitionPreflight{}, sourceChanged()
	}
	if rawCount < 2 {
		return partitionPreflight{}, fmt.Errorf("%s: partition requires at least one record after session_meta", path)
	}
	if err := state.validateSnapshot(path); err != nil {
		return partitionPreflight{}, err
	}
	after, err := os.Stat(path)
	if err != nil {
		return partitionPreflight{}, err
	}
	if !os.SameFile(before, after) || after.Size() < throughOffset {
		return partitionPreflight{}, sourceChanged()
	}
	timestamp, err := rollout.SessionFileTimestamp(path)
	if err != nil {
		return partitionPreflight{}, err
	}
	return partitionPreflight{
		Selected: SelectedRollout{
			SessionID: req.SessionID, Timestamp: timestamp,
			CodexHome: req.CodexHome, IncludeArchived: req.IncludeArchived,
			Path: path, ThroughSourceLine: lastLine,
			ThroughSourceOffset: throughOffset,
			PrefixSHA256:        fmt.Sprintf("%x", hash.Sum(nil)),
		},
		RawRecordCount: rawCount, SemanticCount: semanticCount,
		CandidateCount: state.EligibleCandidates, TailOpen: state.tailOpen(),
	}, nil
}

func revalidatePartitionSource(
	ctx context.Context,
	selected SelectedRollout,
) (partitionPreflight, error) {
	if selected.SessionID == "" ||
		selected.SessionID != strings.TrimSpace(selected.SessionID) ||
		!absoluteCleanPath(selected.CodexHome) ||
		!absoluteCleanPath(selected.Path) ||
		selected.ThroughSourceLine <= 0 ||
		selected.ThroughSourceOffset <= 0 ||
		selected.PrefixSHA256 == "" {
		return partitionPreflight{}, fmt.Errorf("source identity, paths, boundary, and digest are required")
	}
	req := contentSourceRequest{
		CodexHome: selected.CodexHome, SessionID: selected.SessionID,
		IncludeArchived: selected.IncludeArchived,
	}
	path, err := resolveContentSource(ctx, req)
	if err != nil {
		return partitionPreflight{}, err
	}
	if !sameExistingPath(path, selected.Path) {
		return partitionPreflight{}, sourceChanged()
	}
	current, err := inspectPartitionPrefix(ctx, req, path, selected.ThroughSourceOffset)
	if err != nil {
		return partitionPreflight{}, err
	}
	if current.Selected != selected {
		return partitionPreflight{}, sourceChanged()
	}
	return current, nil
}

func resolveContentSource(ctx context.Context, req contentSourceRequest) (string, error) {
	if err := ctx.Err(); err != nil {
		return "", err
	}
	if !absoluteCleanPath(req.CodexHome) {
		return "", fmt.Errorf("codex_home must be an absolute clean path")
	}
	if req.SessionID == "" || req.SessionID != strings.TrimSpace(req.SessionID) {
		return "", fmt.Errorf("session_id is required")
	}
	path, err := rollout.ResolveSessionFile(req.CodexHome, req.SessionID, req.IncludeArchived)
	if err != nil {
		return "", err
	}
	if err := validateResolvedSessionPath(req.CodexHome, path, req.IncludeArchived); err != nil {
		return "", err
	}
	return path, nil
}

func validateResolvedSessionPath(codexHome string, resolvedPath string, includeArchived bool) error {
	roots := []string{filepath.Join(codexHome, "sessions")}
	if includeArchived {
		roots = append(roots, filepath.Join(codexHome, "archived_sessions"))
	}
	for _, root := range roots {
		if !pathInside(root, resolvedPath) {
			continue
		}
		if !existingPathInside(root, resolvedPath) {
			return fmt.Errorf("resolved session rollout escapes its Codex home storage root: %s", resolvedPath)
		}
		return nil
	}
	return fmt.Errorf("resolved session rollout is outside the selected Codex home roots: %s", resolvedPath)
}

func sourceChanged() error {
	return fmt.Errorf("source no longer contains the inspected prefix; rerun inspection")
}
