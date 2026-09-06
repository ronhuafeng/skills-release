package sessionmanagement

import (
	"bufio"
	"bytes"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"hash"
	"io"
	"os"
	"path/filepath"
	"strings"
	"time"
	"unicode/utf8"

	"github.com/google/uuid"
	rollout "github.com/ronhuafeng/skills/harnesses/codex/rollout-go"
)

func validateSplitManifestFile(manifestPath, logicalRoot, actualRoot string, selected SelectedRollout) (splitManifest, error) {
	manifest, err := readSplitManifest(manifestPath)
	if err != nil {
		return splitManifest{}, err
	}
	if filepath.Base(manifestPath) != "split-manifest-"+manifest.SourceSessionID+".json" {
		return splitManifest{}, fmt.Errorf("split manifest filename does not match source session id")
	}
	if manifest.SourceSessionID != selected.SessionID || manifest.SourceCodexHome != selected.CodexHome ||
		manifest.SourceIncludeArchived != selected.IncludeArchived || manifest.SourceRolloutPath != selected.Path ||
		manifest.ThroughSourceLine != selected.ThroughSourceLine || manifest.SourcePrefixSHA256 != selected.PrefixSHA256 {
		return splitManifest{}, fmt.Errorf("split manifest source does not match the selected rollout")
	}
	if err := validateSplitManifest(manifest, logicalRoot, actualRoot, selected.Path); err != nil {
		return splitManifest{}, err
	}
	return manifest, nil
}

func validatePublishedSplitManifest(manifestPath string) (splitManifest, error) {
	manifest, err := readSplitManifest(manifestPath)
	if err != nil {
		return splitManifest{}, err
	}
	if filepath.Base(manifestPath) != "split-manifest-"+manifest.SourceSessionID+".json" {
		return splitManifest{}, fmt.Errorf("split manifest filename does not match source session id")
	}
	if !absoluteCleanPath(manifest.SourceCodexHome) {
		return splitManifest{}, fmt.Errorf("source_codex_home must be an absolute clean path")
	}
	sourcePath, err := rollout.ResolveSessionFile(manifest.SourceCodexHome, manifest.SourceSessionID, manifest.SourceIncludeArchived)
	if err != nil {
		return splitManifest{}, fmt.Errorf("resolve manifest source session: %w", err)
	}
	if err := validateResolvedSessionPath(manifest.SourceCodexHome, sourcePath, manifest.SourceIncludeArchived); err != nil {
		return splitManifest{}, err
	}
	if !sameExistingPath(sourcePath, manifest.SourceRolloutPath) {
		return splitManifest{}, fmt.Errorf("manifest source rollout path or archived selection no longer matches")
	}
	root := filepath.Dir(manifestPath)
	if err := validateSplitManifest(manifest, root, root, sourcePath); err != nil {
		return splitManifest{}, err
	}
	return manifest, nil
}

func readSplitManifest(path string) (splitManifest, error) {
	info, err := os.Lstat(path)
	if err != nil {
		return splitManifest{}, err
	}
	if !info.Mode().IsRegular() || info.Mode()&os.ModeSymlink != 0 {
		return splitManifest{}, fmt.Errorf("split manifest is not a regular non-symlink file: %s", path)
	}
	file, err := os.Open(path)
	if err != nil {
		return splitManifest{}, err
	}
	defer file.Close()
	decoder := json.NewDecoder(file)
	decoder.DisallowUnknownFields()
	var manifest splitManifest
	if err := decoder.Decode(&manifest); err != nil {
		return splitManifest{}, fmt.Errorf("decode split manifest: %w", err)
	}
	var trailing any
	if err := decoder.Decode(&trailing); err != io.EOF {
		if err == nil {
			err = fmt.Errorf("multiple JSON values")
		}
		return splitManifest{}, fmt.Errorf("decode split manifest: %w", err)
	}
	return manifest, nil
}

type splitOutputVerifier struct {
	part       splitManifestPart
	path       string
	file       *os.File
	reader     *bufio.Reader
	outputHash hash.Hash
	sourceHash hash.Hash
	count      int
}

func validateSplitManifest(manifest splitManifest, logicalRoot, actualRoot, requiredSourcePath string) error {
	if !absoluteCleanPath(logicalRoot) || !absoluteCleanPath(actualRoot) ||
		!absoluteCleanPath(manifest.SourceCodexHome) || !absoluteCleanPath(manifest.SourceRolloutPath) {
		return fmt.Errorf("manifest roots and source paths must be absolute clean paths")
	}
	if !sameExistingPath(manifest.SourceRolloutPath, requiredSourcePath) {
		return fmt.Errorf("manifest source rollout does not match the selected rollout")
	}
	if manifest.ThroughSourceLine <= 1 || !validSHA256(manifest.SourcePrefixSHA256) {
		return fmt.Errorf("manifest source boundary and SHA-256 are required")
	}
	if len(manifest.Parts) == 0 {
		return fmt.Errorf("split manifest must contain at least one part")
	}

	sourceUUID, err := uuid.Parse(manifest.SourceSessionID)
	if err != nil || sourceUUID.String() != manifest.SourceSessionID {
		return fmt.Errorf("manifest source session id must be a canonical UUID")
	}
	seenIDs := map[uuid.UUID]bool{}
	seenPaths := map[string]bool{}
	actualPaths := make([]string, len(manifest.Parts))
	for index, part := range manifest.Parts {
		expectedPartID := fmt.Sprintf("P%03d", index+1)
		if part.PartID != expectedPartID {
			return fmt.Errorf("manifest part %d must use id %s", index+1, expectedPartID)
		}
		if strings.TrimSpace(part.Title) == "" || utf8.RuneCountInString(part.Title) > 120 || strings.ContainsAny(part.Title, "\r\n") {
			return fmt.Errorf("manifest part %s title must be one line with 1..120 characters", part.PartID)
		}
		if part.StartSourceLine <= 1 || part.EndSourceLine < part.StartSourceLine || part.SourceRecordCount < 1 || !validSHA256(part.SourceRecordsSHA256) {
			return fmt.Errorf("manifest part %s source proof is invalid", part.PartID)
		}
		created, err := validateManifestPartIdentity(part, sourceUUID, seenIDs)
		if err != nil {
			return err
		}
		expectedPath := splitRolloutPath(logicalRoot, part.SessionID, created)
		if part.RolloutPath != expectedPath || seenPaths[part.RolloutPath] {
			return fmt.Errorf("manifest part %s rollout path is invalid", part.PartID)
		}
		seenPaths[part.RolloutPath] = true
		actualPath, err := manifestActualPath(actualRoot, logicalRoot, part.RolloutPath)
		if err != nil {
			return err
		}
		info, err := os.Lstat(actualPath)
		if err != nil {
			return err
		}
		if !info.Mode().IsRegular() || info.Mode()&os.ModeSymlink != 0 {
			return fmt.Errorf("manifest part %s rollout is not a regular non-symlink file", part.PartID)
		}
		actualPaths[index] = actualPath
	}

	prefixHash := sha256.New()
	state := newPartitionScanState()
	sourceValidator := splitSourceValidator{sessionID: manifest.SourceSessionID}
	partIndex := 0
	var verifier *splitOutputVerifier
	var header rollout.Record
	lastPrefixLine := 0
	recordIndex := 0
	closeVerifier := func() error {
		if verifier == nil {
			return nil
		}
		if verifier.count != verifier.part.SourceRecordCount || fmt.Sprintf("%x", verifier.sourceHash.Sum(nil)) != verifier.part.SourceRecordsSHA256 {
			_ = verifier.file.Close()
			return fmt.Errorf("manifest part %s source record proof is invalid", verifier.part.PartID)
		}
		if _, err := verifier.reader.ReadByte(); err != io.EOF {
			_ = verifier.file.Close()
			if err == nil {
				err = fmt.Errorf("unexpected output data")
			}
			return fmt.Errorf("manifest part %s output has extra data: %w", verifier.part.PartID, err)
		}
		if err := verifier.file.Close(); err != nil {
			return err
		}
		if !validSHA256(verifier.part.OutputSHA256) || fmt.Sprintf("%x", verifier.outputHash.Sum(nil)) != verifier.part.OutputSHA256 {
			return fmt.Errorf("manifest part %s output hash does not match", verifier.part.PartID)
		}
		if err := validateGeneratedSplitRollout(
			verifier.path,
			verifier.part,
			sourceValidator.usesOrdinals,
		); err != nil {
			return fmt.Errorf("manifest part %s is not a standalone rollout: %w", verifier.part.PartID, err)
		}
		verifier = nil
		return nil
	}
	openVerifier := func(part splitManifestPart, actualPath string) error {
		file, err := os.Open(actualPath)
		if err != nil {
			return err
		}
		verifier = &splitOutputVerifier{
			part: part, path: actualPath, file: file, reader: bufio.NewReader(file),
			outputHash: sha256.New(), sourceHash: sha256.New(),
		}
		created, _ := rollout.ParseTimestamp(part.CreatedAt)
		var ordinal *uint64
		if sourceValidator.usesOrdinals {
			value := uint64(0)
			ordinal = &value
		}
		expected, err := header.ProjectGeneratedSession(
			part.SessionID,
			created.Format(time.RFC3339Nano),
			ordinal,
		)
		if err != nil {
			_ = file.Close()
			return fmt.Errorf("manifest part %s header rewrite: %w", part.PartID, err)
		}
		return verifyOutputLine(verifier, expected)
	}

	err = rollout.Scan(requiredSourcePath, func(record rollout.Record) error {
		if record.Line > manifest.ThroughSourceLine {
			return nil
		}
		lastPrefixLine = record.Line
		recordIndex++
		_, _ = prefixHash.Write(record.Raw)
		_, _ = prefixHash.Write([]byte{'\n'})
		if err := sourceValidator.consume(requiredSourcePath, record); err != nil {
			return err
		}
		if recordIndex == 1 {
			header = record
			return nil
		}
		if _, _, err := state.consume(requiredSourcePath, record); err != nil {
			return err
		}
		for partIndex < len(manifest.Parts) && record.Line > manifest.Parts[partIndex].EndSourceLine {
			if err := closeVerifier(); err != nil {
				return err
			}
			partIndex++
		}
		if partIndex >= len(manifest.Parts) {
			return fmt.Errorf("manifest parts do not cover source line %d", record.Line)
		}
		part := manifest.Parts[partIndex]
		if record.Line < part.StartSourceLine {
			return fmt.Errorf("manifest part %s source range is not contiguous", part.PartID)
		}
		if verifier == nil {
			if record.Line != part.StartSourceLine {
				return fmt.Errorf("manifest part %s does not start at a source record", part.PartID)
			}
			if err := openVerifier(part, actualPaths[partIndex]); err != nil {
				return err
			}
		}
		var ordinal *uint64
		if sourceValidator.usesOrdinals {
			value := uint64(verifier.count + 1)
			ordinal = &value
		}
		rewritten, err := record.ProjectGeneratedSession(part.SessionID, "", ordinal)
		if err != nil {
			return fmt.Errorf("manifest part %s source line %d rewrite: %w", part.PartID, record.Line, err)
		}
		if err := verifyOutputLine(verifier, rewritten); err != nil {
			return err
		}
		_, _ = verifier.sourceHash.Write(record.Raw)
		_, _ = verifier.sourceHash.Write([]byte{'\n'})
		verifier.count++
		return nil
	})
	if err != nil {
		if verifier != nil {
			_ = verifier.file.Close()
		}
		return err
	}
	if err := closeVerifier(); err != nil {
		return err
	}
	partIndex++
	if recordIndex < 2 || lastPrefixLine != manifest.ThroughSourceLine || fmt.Sprintf("%x", prefixHash.Sum(nil)) != manifest.SourcePrefixSHA256 {
		return fmt.Errorf("manifest source prefix does not match its rollout")
	}
	if partIndex != len(manifest.Parts) || manifest.Parts[len(manifest.Parts)-1].EndSourceLine != manifest.ThroughSourceLine {
		return fmt.Errorf("manifest parts do not cover the complete source prefix")
	}
	if err := state.validateSnapshot(requiredSourcePath); err != nil {
		return err
	}
	if state.tailOpen() {
		return fmt.Errorf("split manifest source prefix has an open lifecycle tail")
	}
	return nil
}

func validateGeneratedSplitRollout(
	path string,
	part splitManifestPart,
	usesOrdinals bool,
) error {
	recordCount := 0
	err := rollout.Scan(path, func(record rollout.Record) error {
		ordinal, present, err := record.Ordinal()
		if err != nil {
			return fmt.Errorf("%s:%d: %w", path, record.Line, err)
		}
		if present != usesOrdinals {
			return fmt.Errorf("%s:%d: generated ordinal mode is inconsistent", path, record.Line)
		}
		if present && ordinal != uint64(recordCount) {
			return fmt.Errorf(
				"%s:%d: generated ordinal %d is not the expected %d",
				path,
				record.Line,
				ordinal,
				recordCount,
			)
		}
		if recordCount == 0 {
			if err := validateGeneratedSplitMeta(record, part, usesOrdinals); err != nil {
				return fmt.Errorf("%s:%d: %w", path, record.Line, err)
			}
		} else if record.Envelope != nil && record.Envelope.Type == "session_meta" {
			return fmt.Errorf("%s:%d: generated rollout has more than one session_meta", path, record.Line)
		}
		recordCount++
		return nil
	})
	if err != nil {
		return err
	}
	if recordCount != part.SourceRecordCount+1 {
		return fmt.Errorf("generated rollout record count does not match its source range")
	}
	return rollout.ValidateThreadIdentity(path, part.SessionID)
}

func validateGeneratedSplitMeta(
	record rollout.Record,
	part splitManifestPart,
	usesOrdinals bool,
) error {
	meta, err := rollout.DecodeSessionMeta(record)
	if err != nil {
		return err
	}
	if err := validateSplitRootMeta(meta, part.SessionID); err != nil {
		return err
	}
	if meta.Timestamp != part.CreatedAt || record.Envelope.Timestamp != part.CreatedAt {
		return fmt.Errorf("generated timestamps do not match created_at")
	}
	wantHistoryMode := "legacy"
	if usesOrdinals {
		wantHistoryMode = "paginated"
	}
	if meta.HistoryMode != wantHistoryMode {
		return fmt.Errorf("generated history_mode must be %s", wantHistoryMode)
	}
	var source string
	if err := json.Unmarshal(meta.Source, &source); err != nil || source != "mcp" {
		return fmt.Errorf("generated source must be mcp")
	}
	var contextWindow struct {
		WindowID string `json:"window_id"`
	}
	if err := json.Unmarshal(meta.ContextWindow, &contextWindow); err != nil ||
		contextWindow.WindowID != part.SessionID {
		return fmt.Errorf("generated context_window must use the session id")
	}
	var payload map[string]json.RawMessage
	if err := json.Unmarshal(record.Envelope.Payload, &payload); err != nil || payload == nil {
		return fmt.Errorf("generated session_meta payload must be an object")
	}
	for _, field := range []string{
		"forked_from_id",
		"forked_from_ordinal_exclusive",
		"parent_thread_id",
		"history_base",
		"subagent_history_start_ordinal",
		"agent_nickname",
		"agent_role",
		"agent_type",
		"agent_path",
		"thread_source",
	} {
		if _, present := payload[field]; present {
			return fmt.Errorf("generated session_meta retains %s", field)
		}
	}
	return nil
}

func verifyOutputLine(verifier *splitOutputVerifier, expected []byte) error {
	line, err := verifier.reader.ReadBytes('\n')
	if err != nil {
		return fmt.Errorf("manifest part %s output ended early: %w", verifier.part.PartID, err)
	}
	want := append(bytes.Clone(expected), '\n')
	if !bytes.Equal(line, want) {
		return fmt.Errorf("manifest part %s output does not exactly represent its source records", verifier.part.PartID)
	}
	_, _ = verifier.outputHash.Write(line)
	return nil
}

func validateManifestPartIdentity(part splitManifestPart, sourceID uuid.UUID, seenIDs map[uuid.UUID]bool) (time.Time, error) {
	id, err := uuid.Parse(part.SessionID)
	if err != nil || id.String() != part.SessionID || id.Version() != 7 || id == sourceID || seenIDs[id] {
		return time.Time{}, fmt.Errorf("manifest part %s requires a unique non-source UUIDv7 session id", part.PartID)
	}
	seenIDs[id] = true
	created, ok := rollout.ParseTimestamp(part.CreatedAt)
	if !ok {
		return time.Time{}, fmt.Errorf("manifest part %s created_at must be RFC3339", part.PartID)
	}
	seconds, nanos := id.Time().UnixTime()
	want := time.Unix(seconds, nanos).UTC()
	if !created.Equal(want) || part.CreatedAt != want.Format(time.RFC3339Nano) {
		return time.Time{}, fmt.Errorf("manifest part %s created_at does not match its UUIDv7 timestamp", part.PartID)
	}
	return want, nil
}

func manifestActualPath(actualRoot, logicalRoot, target string) (string, error) {
	if actualRoot == logicalRoot {
		return target, nil
	}
	return stagedSplitPath(actualRoot, logicalRoot, target)
}

func validSHA256(value string) bool {
	if len(value) != 64 || value != strings.ToLower(value) {
		return false
	}
	decoded, err := hex.DecodeString(value)
	return err == nil && len(decoded) == 32
}
