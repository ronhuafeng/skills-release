package sessionmanagement

import (
	"context"
	"fmt"
	"os"
	"path/filepath"
	"strings"

	"github.com/google/uuid"
	rollout "github.com/ronhuafeng/skills/harnesses/codex/rollout-go"
)

type RehomeArchiveProofRequest struct {
	ThreadID          string `json:"thread_id"`
	SourceRolloutPath string `json:"source_rollout_path"`
	SourceSHA256      string `json:"source_sha256"`
}

type RehomeArchiveProof struct {
	ThreadID      string `json:"thread_id"`
	ArchivedPath  string `json:"archived_path"`
	SourceSHA256  string `json:"source_sha256"`
	SourceRemoved bool   `json:"source_removed"`
}

func VerifyRehomeSourceArchive(ctx context.Context, request RehomeArchiveProofRequest) (RehomeArchiveProof, error) {
	if err := ctx.Err(); err != nil {
		return RehomeArchiveProof{}, err
	}
	parsedID, err := uuid.Parse(request.ThreadID)
	if err != nil || parsedID.String() != request.ThreadID {
		return RehomeArchiveProof{}, invalidRehomeRequest("thread_id must be a canonical UUID")
	}
	if !absoluteCleanPath(request.SourceRolloutPath) {
		return RehomeArchiveProof{}, invalidRehomeRequest("source_rollout_path must be an absolute clean path")
	}
	if !sha256Pattern.MatchString(request.SourceSHA256) {
		return RehomeArchiveProof{}, invalidRehomeRequest("source_sha256 must be a SHA-256 digest")
	}

	codexHome, err := resolveRehomeCodexHome()
	if err != nil {
		return RehomeArchiveProof{}, err
	}
	relativeSource, err := filepath.Rel(codexHome, request.SourceRolloutPath)
	if err != nil || relativeSource == "." ||
		strings.HasPrefix(relativeSource, ".."+string(filepath.Separator)) ||
		!strings.HasPrefix(relativeSource, "sessions"+string(filepath.Separator)) {
		return RehomeArchiveProof{}, invalidRehomeRequest("source_rollout_path must be under the active sessions directory")
	}
	archivedPath := filepath.Join(codexHome, "archived_sessions", filepath.Base(request.SourceRolloutPath))
	proof := RehomeArchiveProof{
		ThreadID:     request.ThreadID,
		ArchivedPath: archivedPath,
		SourceSHA256: request.SourceSHA256,
	}
	if _, err := os.Stat(request.SourceRolloutPath); !os.IsNotExist(err) {
		if err == nil {
			return proof, fmt.Errorf("active source rollout still exists after app archive")
		}
		return proof, fmt.Errorf("inspect active source after app archive: %w", err)
	}
	proof.SourceRemoved = true
	resolved, err := rollout.ResolveSessionFile(codexHome, request.ThreadID, true)
	if err != nil {
		return proof, fmt.Errorf("resolve archived source rollout: %w", err)
	}
	if !sameExistingPath(resolved, archivedPath) {
		return proof, fmt.Errorf("archived source rollout path=%s, want %s", resolved, archivedPath)
	}
	content, err := os.ReadFile(archivedPath)
	if err != nil {
		return proof, fmt.Errorf("read archived source rollout: %w", err)
	}
	if hashBytes(content) != request.SourceSHA256 {
		return proof, fmt.Errorf("archived source rollout digest mismatch")
	}
	meta, err := rollout.SessionMeta(archivedPath)
	if err != nil {
		return proof, err
	}
	if meta.ID != request.ThreadID || meta.SessionID != request.ThreadID {
		return proof, fmt.Errorf("archived source rollout identity does not match thread_id")
	}
	return proof, nil
}
