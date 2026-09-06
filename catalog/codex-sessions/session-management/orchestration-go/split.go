package sessionmanagement

import (
	"bufio"
	"context"
	"crypto/sha256"
	"encoding/json"
	"errors"
	"fmt"
	"hash"
	"io"
	"os"
	"path/filepath"
	"strings"
	"time"

	"github.com/google/uuid"
	rollout "github.com/ronhuafeng/skills/harnesses/codex/rollout-go"
)

type SplitExecuteRequest struct {
	Plan            PartitionPlan `json:"plan"`
	OutputCodexHome string        `json:"output_codex_home"`
}

type splitPreparedPart struct {
	PartID          string `json:"part_id"`
	Title           string `json:"title"`
	StartSourceLine int    `json:"start_source_line"`
	EndSourceLine   int    `json:"end_source_line"`
	SessionID       string `json:"session_id"`
	CreatedAt       string `json:"created_at"`
	RolloutPath     string `json:"rollout_path"`
}

type splitWritePlan struct {
	OutputCodexHome string
	ManifestPath    string
	Parts           []splitPreparedPart
}

type splitManifest struct {
	SourceSessionID       string              `json:"source_session_id"`
	SourceCodexHome       string              `json:"source_codex_home"`
	SourceIncludeArchived bool                `json:"source_include_archived"`
	SourceRolloutPath     string              `json:"source_rollout_path"`
	ThroughSourceLine     int                 `json:"through_source_line"`
	SourcePrefixSHA256    string              `json:"source_prefix_sha256"`
	Parts                 []splitManifestPart `json:"parts"`
}

type splitManifestPart struct {
	PartID              string `json:"part_id"`
	Title               string `json:"title"`
	StartSourceLine     int    `json:"start_source_line"`
	EndSourceLine       int    `json:"end_source_line"`
	SourceRecordCount   int    `json:"source_record_count"`
	SourceRecordsSHA256 string `json:"source_records_sha256"`
	SessionID           string `json:"session_id"`
	CreatedAt           string `json:"created_at"`
	RolloutPath         string `json:"rollout_path"`
	OutputSHA256        string `json:"output_sha256"`
}

type SplitExecuteResult struct {
	OutputCodexHome string `json:"output_codex_home"`
	ManifestPath    string `json:"manifest_path"`
}

func ExecuteSplit(ctx context.Context, req SplitExecuteRequest) (SplitExecuteResult, error) {
	if req.OutputCodexHome == "" {
		return SplitExecuteResult{}, fmt.Errorf("output_codex_home is required")
	}
	source, partition, err := revalidatePartitionPlan(ctx, req.Plan)
	if err != nil {
		return SplitExecuteResult{}, err
	}
	if partition.Receipt.TailOpen {
		return SplitExecuteResult{}, fmt.Errorf("split requires a snapshot with a closed lifecycle tail")
	}
	format, err := validateSplitSource(ctx, source.Selected)
	if err != nil {
		return SplitExecuteResult{}, err
	}
	plan, err := prepareSplitWrite(partition.Receipt.Source, partition.Parts, req.OutputCodexHome)
	if err != nil {
		return SplitExecuteResult{}, err
	}
	return writeSplit(ctx, source, format, plan)
}

func prepareSplitWrite(selected SelectedRollout, derived []PartitionPlanPart, outputHome string) (splitWritePlan, error) {
	if err := validateSplitOutputRoot(outputHome, selected.CodexHome); err != nil {
		return splitWritePlan{}, err
	}
	sourceID, err := uuid.Parse(selected.SessionID)
	if err != nil || sourceID.String() != selected.SessionID {
		return splitWritePlan{}, fmt.Errorf("source session id must be a canonical UUID")
	}
	manifestPath := filepath.Join(outputHome, "split-manifest-"+selected.SessionID+".json")
	parts := make([]splitPreparedPart, 0, len(derived))
	for _, sourcePart := range derived {
		id, err := uuid.NewV7()
		if err != nil {
			return splitWritePlan{}, err
		}
		if id == sourceID {
			return splitWritePlan{}, fmt.Errorf("generated part %s reused the source session id", sourcePart.PartID)
		}
		seconds, nanoseconds := id.Time().UnixTime()
		created := time.Unix(seconds, nanoseconds).UTC()
		parts = append(parts, splitPreparedPart{
			PartID: sourcePart.PartID, Title: sourcePart.Title,
			StartSourceLine: sourcePart.StartSourceLine, EndSourceLine: sourcePart.EndSourceLine,
			SessionID: id.String(), CreatedAt: created.Format(time.RFC3339Nano),
			RolloutPath: splitRolloutPath(outputHome, id.String(), created),
		})
	}
	return splitWritePlan{
		OutputCodexHome: outputHome, ManifestPath: manifestPath, Parts: parts,
	}, nil
}

func writeSplit(
	ctx context.Context,
	source partitionPreflight,
	format splitSourceFormat,
	plan splitWritePlan,
) (SplitExecuteResult, error) {
	parent := filepath.Dir(plan.OutputCodexHome)
	tempRoot, err := os.MkdirTemp(parent, "."+filepath.Base(plan.OutputCodexHome)+".tmp-")
	if err != nil {
		return SplitExecuteResult{}, err
	}
	keepTemp := false
	defer func() {
		if !keepTemp {
			_ = os.RemoveAll(tempRoot)
		}
	}()

	selected := source.Selected
	manifest := splitManifest{
		SourceSessionID: selected.SessionID, SourceCodexHome: selected.CodexHome,
		SourceIncludeArchived: selected.IncludeArchived, SourceRolloutPath: selected.Path,
		ThroughSourceLine: selected.ThroughSourceLine, SourcePrefixSHA256: selected.PrefixSHA256,
		Parts: []splitManifestPart{},
	}
	parts, err := writeSplitParts(
		ctx,
		source.Selected.Path,
		source.Selected.ThroughSourceOffset,
		tempRoot,
		format,
		plan,
	)
	if err != nil {
		return SplitExecuteResult{}, err
	}
	manifest.Parts = parts
	manifestRaw, err := json.MarshalIndent(manifest, "", "  ")
	if err != nil {
		return SplitExecuteResult{}, err
	}
	manifestRaw = append(manifestRaw, '\n')
	tempManifest, err := stagedSplitPath(tempRoot, plan.OutputCodexHome, plan.ManifestPath)
	if err != nil {
		return SplitExecuteResult{}, err
	}
	if err := writePrivateFile(tempManifest, manifestRaw); err != nil {
		return SplitExecuteResult{}, err
	}
	if err := validateStagedSplit(ctx, tempRoot, tempManifest, selected, plan); err != nil {
		return SplitExecuteResult{}, err
	}
	if _, err := revalidatePartitionSource(ctx, selected); err != nil {
		return SplitExecuteResult{}, err
	}
	if err := renameNoReplace(tempRoot, plan.OutputCodexHome); err != nil {
		return SplitExecuteResult{}, err
	}
	keepTemp = true
	return SplitExecuteResult{OutputCodexHome: plan.OutputCodexHome, ManifestPath: plan.ManifestPath}, nil
}

func validateSplitOutputRoot(outputHome string, sourceHome string) error {
	if !absoluteCleanPath(outputHome) {
		return fmt.Errorf("output_codex_home must be an absolute clean path")
	}
	if _, err := os.Lstat(outputHome); err == nil {
		return fmt.Errorf("output_codex_home must not already exist")
	} else if !os.IsNotExist(err) {
		return err
	}
	parent := filepath.Dir(outputHome)
	info, err := os.Lstat(parent)
	if err != nil {
		return err
	}
	if !info.IsDir() || info.Mode()&os.ModeSymlink != 0 {
		return fmt.Errorf("output_codex_home parent must be a non-symlink directory")
	}
	resolvedSource, err := filepath.EvalSymlinks(sourceHome)
	if err != nil {
		return fmt.Errorf("resolve source Codex home: %w", err)
	}
	resolvedParent, err := filepath.EvalSymlinks(parent)
	if err != nil {
		return fmt.Errorf("resolve output_codex_home parent: %w", err)
	}
	resolvedOutput := filepath.Join(resolvedParent, filepath.Base(outputHome))
	if resolvedOutput == resolvedSource || pathInside(resolvedSource, resolvedOutput) {
		return fmt.Errorf("output_codex_home must resolve outside the source Codex home")
	}
	return nil
}

type splitPartWriter struct {
	part       splitPreparedPart
	file       *os.File
	writer     *bufio.Writer
	sourceHash hash.Hash
	outputHash hash.Hash
	count      int
}

func writeSplitParts(
	ctx context.Context,
	sourcePath string,
	throughOffset int64,
	tempRoot string,
	format splitSourceFormat,
	plan splitWritePlan,
) ([]splitManifestPart, error) {
	if len(plan.Parts) == 0 {
		return nil, fmt.Errorf("split plan has no parts")
	}
	var header rollout.Record
	partIndex := 0
	var current *splitPartWriter
	manifestParts := make([]splitManifestPart, 0, len(plan.Parts))
	closeCurrent := func() error {
		if current == nil {
			return nil
		}
		if current.count == 0 {
			return fmt.Errorf("prepared part %s has no source records", current.part.PartID)
		}
		if err := current.writer.Flush(); err != nil {
			_ = current.file.Close()
			return err
		}
		if err := current.file.Close(); err != nil {
			return err
		}
		manifestParts = append(manifestParts, splitManifestPart{
			PartID: current.part.PartID, Title: current.part.Title,
			StartSourceLine: current.part.StartSourceLine, EndSourceLine: current.part.EndSourceLine,
			SourceRecordCount: current.count, SourceRecordsSHA256: fmt.Sprintf("%x", current.sourceHash.Sum(nil)),
			SessionID: current.part.SessionID, CreatedAt: current.part.CreatedAt,
			RolloutPath: current.part.RolloutPath, OutputSHA256: fmt.Sprintf("%x", current.outputHash.Sum(nil)),
		})
		current = nil
		return nil
	}
	openCurrent := func(part splitPreparedPart) error {
		created, ok := rollout.ParseTimestamp(part.CreatedAt)
		if !ok {
			return fmt.Errorf("prepared part %s created_at is invalid", part.PartID)
		}
		tempPath, err := stagedSplitPath(tempRoot, plan.OutputCodexHome, part.RolloutPath)
		if err != nil {
			return err
		}
		if err := os.MkdirAll(filepath.Dir(tempPath), 0o700); err != nil {
			return err
		}
		file, err := os.OpenFile(tempPath, os.O_WRONLY|os.O_CREATE|os.O_EXCL, 0o600)
		if err != nil {
			return err
		}
		current = &splitPartWriter{part: part, file: file, writer: bufio.NewWriter(file), sourceHash: sha256.New(), outputHash: sha256.New()}
		var ordinal *uint64
		if format.UsesOrdinals {
			value := uint64(0)
			ordinal = &value
		}
		rewritten, err := header.ProjectGeneratedSession(
			part.SessionID,
			created.Format(time.RFC3339Nano),
			ordinal,
		)
		if err != nil {
			_ = file.Close()
			return fmt.Errorf("%s: rewrite split header: %w", part.PartID, err)
		}
		return writeHashedLine(current.writer, current.outputHash, rewritten)
	}

	recordIndex := 0
	_, err := rollout.ScanRange(sourcePath, rollout.ScanCursor{NextLine: 1}, throughOffset, func(record rollout.Record, _ rollout.ScanCursor) (bool, error) {
		if err := ctx.Err(); err != nil {
			return false, err
		}
		recordIndex++
		if recordIndex == 1 {
			header = record
			return true, nil
		}
		for partIndex < len(plan.Parts) && record.Line > plan.Parts[partIndex].EndSourceLine {
			if err := closeCurrent(); err != nil {
				return false, err
			}
			partIndex++
		}
		if partIndex >= len(plan.Parts) {
			return false, fmt.Errorf("source record %d is outside the split plan", record.Line)
		}
		part := plan.Parts[partIndex]
		if record.Line < part.StartSourceLine {
			return false, fmt.Errorf("source record %d is not covered by %s", record.Line, part.PartID)
		}
		if current == nil {
			if record.Line != part.StartSourceLine {
				return false, fmt.Errorf("%s does not start at a source record", part.PartID)
			}
			if err := openCurrent(part); err != nil {
				return false, err
			}
		}
		var ordinal *uint64
		if format.UsesOrdinals {
			value := uint64(current.count + 1)
			ordinal = &value
		}
		rewritten, err := record.ProjectGeneratedSession(part.SessionID, "", ordinal)
		if err != nil {
			return false, fmt.Errorf("%s:%d: rewrite split record: %w", sourcePath, record.Line, err)
		}
		if err := writeHashedLine(current.writer, current.outputHash, rewritten); err != nil {
			return false, err
		}
		_, _ = current.sourceHash.Write(record.Raw)
		_, _ = current.sourceHash.Write([]byte{'\n'})
		current.count++
		return true, nil
	})
	if err != nil {
		if current != nil {
			_ = current.file.Close()
		}
		return nil, err
	}
	if recordIndex == 0 {
		return nil, fmt.Errorf("source rollout is empty")
	}
	if err := closeCurrent(); err != nil {
		return nil, err
	}
	if len(manifestParts) != len(plan.Parts) {
		return nil, fmt.Errorf("split plan does not cover all parts")
	}
	return manifestParts, nil
}

func writeHashedLine(writer io.Writer, digest hash.Hash, raw []byte) error {
	if _, err := writer.Write(raw); err != nil {
		return err
	}
	if _, err := writer.Write([]byte{'\n'}); err != nil {
		return err
	}
	_, _ = digest.Write(raw)
	_, _ = digest.Write([]byte{'\n'})
	return nil
}

func validateStagedSplit(ctx context.Context, tempRoot string, tempManifest string, selected SelectedRollout, plan splitWritePlan) error {
	if err := ctx.Err(); err != nil {
		return err
	}
	if _, err := validateSplitManifestFile(tempManifest, plan.OutputCodexHome, tempRoot, selected); err != nil {
		return fmt.Errorf("validate split manifest: %w", err)
	}
	return nil
}

func stagedSplitPath(tempRoot string, outputRoot string, target string) (string, error) {
	relative, err := filepath.Rel(outputRoot, target)
	if err != nil || relative == "." || relative == ".." || strings.HasPrefix(relative, ".."+string(filepath.Separator)) {
		return "", fmt.Errorf("split output path must stay within output_codex_home: %s", target)
	}
	return filepath.Join(tempRoot, relative), nil
}

func splitRolloutPath(outputHome string, sessionID string, created time.Time) string {
	created = created.UTC()
	filename := fmt.Sprintf("rollout-%s-%s.jsonl", created.Format("2006-01-02T15-04-05"), sessionID)
	return filepath.Join(outputHome, "sessions", created.Format("2006"), created.Format("01"), created.Format("02"), filename)
}

func writePrivateFile(path string, content []byte) error {
	if err := os.MkdirAll(filepath.Dir(path), 0o700); err != nil {
		return err
	}
	file, err := os.OpenFile(path, os.O_WRONLY|os.O_CREATE|os.O_EXCL, 0o600)
	if err != nil {
		return err
	}
	if _, err := file.Write(content); err != nil {
		return errors.Join(err, file.Close())
	}
	return file.Close()
}

func hashBytes(value []byte) string {
	sum := sha256.Sum256(value)
	return fmt.Sprintf("%x", sum[:])
}

func pathInside(root string, candidate string) bool {
	relative, err := filepath.Rel(root, candidate)
	return err == nil && relative != ".." && !strings.HasPrefix(relative, ".."+string(filepath.Separator))
}
