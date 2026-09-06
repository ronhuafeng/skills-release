package sessionmanagement

import (
	"context"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func TestVerifyRehomeSourceArchiveRequiresExactArchivedSnapshot(t *testing.T) {
	home := t.TempDir()
	t.Setenv("CODEX_HOME", home)
	sourcePath := writeRehomeSource(t, home)
	content, err := os.ReadFile(sourcePath)
	if err != nil {
		t.Fatal(err)
	}
	archivedPath := filepath.Join(home, "archived_sessions", filepath.Base(sourcePath))
	if err := os.MkdirAll(filepath.Dir(archivedPath), 0o700); err != nil {
		t.Fatal(err)
	}
	if err := os.Rename(sourcePath, archivedPath); err != nil {
		t.Fatal(err)
	}

	proof, err := VerifyRehomeSourceArchive(context.Background(), RehomeArchiveProofRequest{
		ThreadID: rehomeSessionID, SourceRolloutPath: sourcePath, SourceSHA256: hashBytes(content),
	})
	if err != nil {
		t.Fatal(err)
	}
	if proof.ThreadID != rehomeSessionID || proof.ArchivedPath != archivedPath ||
		proof.SourceSHA256 != hashBytes(content) || !proof.SourceRemoved {
		t.Fatalf("proof=%#v", proof)
	}

	if err := os.WriteFile(archivedPath, append(content, '\n'), 0o600); err != nil {
		t.Fatal(err)
	}
	_, err = VerifyRehomeSourceArchive(context.Background(), RehomeArchiveProofRequest{
		ThreadID: rehomeSessionID, SourceRolloutPath: sourcePath, SourceSHA256: hashBytes(content),
	})
	if err == nil || !strings.Contains(err.Error(), "digest mismatch") {
		t.Fatalf("error=%v", err)
	}
}
