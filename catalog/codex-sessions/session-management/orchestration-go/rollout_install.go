package sessionmanagement

import (
	"bytes"
	"context"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"strings"

	"github.com/google/uuid"
)

const (
	rolloutInstallLocal = "local"
	rolloutInstallSSH   = "ssh"
)

type rolloutInstallDestination struct {
	Kind string
	Host string
}

type rolloutInstallRequest struct {
	ThreadID     string
	Destination  rolloutInstallDestination
	CWD          string
	RelativePath string
	Content      []byte
}

func installRollout(ctx context.Context, request rolloutInstallRequest) (string, error) {
	if err := validateRolloutInstallRequest(request); err != nil {
		return "", err
	}
	switch request.Destination.Kind {
	case rolloutInstallLocal:
		return installLocalRollout(request)
	case rolloutInstallSSH:
		return installSSHRollout(ctx, request)
	default:
		return "", fmt.Errorf("unknown rollout install destination %q", request.Destination.Kind)
	}
}

func validateRolloutInstallRequest(request rolloutInstallRequest) error {
	if request.ThreadID == "" || !absoluteCleanPath(request.CWD) || len(request.Content) == 0 {
		return fmt.Errorf("rollout install requires thread id, absolute CWD, and content")
	}
	relative := filepath.Clean(filepath.FromSlash(request.RelativePath))
	if relative == "." || filepath.IsAbs(relative) ||
		strings.HasPrefix(relative, ".."+string(filepath.Separator)) ||
		!strings.HasPrefix(relative, "sessions"+string(filepath.Separator)) {
		return fmt.Errorf("rollout install path must be inside active sessions")
	}
	if request.Destination.Kind == rolloutInstallLocal && request.Destination.Host != "" {
		return fmt.Errorf("local rollout install does not accept a host")
	}
	if request.Destination.Kind == rolloutInstallSSH && !sshHostPattern.MatchString(request.Destination.Host) {
		return fmt.Errorf("SSH rollout install requires a safe host")
	}
	return nil
}

func installLocalRollout(request rolloutInstallRequest) (string, error) {
	codexHome, err := resolveRehomeCodexHome()
	if err != nil {
		return "", err
	}
	if info, err := os.Stat(request.CWD); err != nil || !info.IsDir() {
		if err == nil {
			err = fmt.Errorf("not a directory")
		}
		return "", fmt.Errorf("validate destination CWD: %w", err)
	}
	if collision, err := localRolloutIDCollision(codexHome, request.ThreadID); err != nil {
		return "", err
	} else if collision {
		return filepath.Join(codexHome, filepath.FromSlash(request.RelativePath)),
			fmt.Errorf("destination already contains thread id")
	}
	destinationPath := filepath.Join(codexHome, filepath.FromSlash(request.RelativePath))
	destinationDirectory := filepath.Dir(destinationPath)
	if err := validateRolloutParentDirectories(codexHome, destinationDirectory); err != nil {
		return destinationPath, err
	}
	if err := os.MkdirAll(destinationDirectory, 0o700); err != nil {
		return destinationPath, err
	}
	if err := validateRolloutParentDirectories(codexHome, destinationDirectory); err != nil {
		return destinationPath, err
	}
	temporaryPath := destinationPath + ".install-" + uuid.NewString()
	file, err := os.OpenFile(temporaryPath, os.O_WRONLY|os.O_CREATE|os.O_EXCL, 0o600)
	if err != nil {
		return destinationPath, err
	}
	cleanup := true
	defer func() {
		if cleanup {
			_ = os.Remove(temporaryPath)
		}
	}()
	if _, err := file.Write(request.Content); err != nil {
		_ = file.Close()
		return destinationPath, err
	}
	if err := file.Close(); err != nil {
		return destinationPath, err
	}
	if err := renameNoReplace(temporaryPath, destinationPath); err != nil {
		return destinationPath, err
	}
	cleanup = false
	return destinationPath, nil
}

func validateRolloutParentDirectories(root string, destinationDirectory string) error {
	relative, err := filepath.Rel(root, destinationDirectory)
	if err != nil || relative == "." || filepath.IsAbs(relative) ||
		strings.HasPrefix(relative, ".."+string(filepath.Separator)) {
		return fmt.Errorf("rollout destination directory is outside Codex home")
	}
	current := root
	for _, component := range strings.Split(relative, string(filepath.Separator)) {
		current = filepath.Join(current, component)
		info, err := os.Lstat(current)
		if os.IsNotExist(err) {
			return nil
		}
		if err != nil {
			return err
		}
		if info.Mode()&os.ModeSymlink != 0 {
			return fmt.Errorf("rollout destination parent is a symlink: %s", current)
		}
		if !info.IsDir() {
			return fmt.Errorf("rollout destination parent is not a directory: %s", current)
		}
	}
	return nil
}

func localRolloutIDCollision(codexHome string, threadID string) (bool, error) {
	suffix := "-" + threadID + ".jsonl"
	for _, root := range []string{
		filepath.Join(codexHome, "sessions"),
		filepath.Join(codexHome, "archived_sessions"),
	} {
		err := filepath.WalkDir(root, func(_ string, entry os.DirEntry, walkErr error) error {
			if walkErr != nil {
				if os.IsNotExist(walkErr) {
					return nil
				}
				return walkErr
			}
			if !entry.IsDir() && strings.HasSuffix(entry.Name(), suffix) {
				return errRolloutIDCollision
			}
			return nil
		})
		if err == errRolloutIDCollision {
			return true, nil
		}
		if err != nil && !os.IsNotExist(err) {
			return false, err
		}
	}
	return false, nil
}

var errRolloutIDCollision = fmt.Errorf("rollout id collision")

func installSSHRollout(ctx context.Context, request rolloutInstallRequest) (string, error) {
	remoteCodexHome, err := resolveSSHCodexHome(ctx, request.Destination.Host)
	if err != nil {
		return "", err
	}
	destinationPath := filepath.Join(remoteCodexHome, filepath.FromSlash(request.RelativePath))
	destinationDirectory := filepath.Dir(destinationPath)
	temporaryPath := destinationPath + ".install-" + uuid.NewString()
	expectedHash := hashBytes(request.Content)
	namePattern := "*-" + request.ThreadID + ".jsonl"

	scriptLines := []string{
		"set -eu",
		"test -d " + quotePOSIX(request.CWD),
		"test -d " + quotePOSIX(remoteCodexHome),
		"if { for root in " + quotePOSIX(filepath.Join(remoteCodexHome, "sessions")) + " " + quotePOSIX(filepath.Join(remoteCodexHome, "archived_sessions")) + `; do test ! -d "$root" || find "$root" -type f -name ` + quotePOSIX(namePattern) + ` -print -quit; done; } | grep -q .; then echo 'destination already contains thread id' >&2; exit 17; fi`,
	}
	scriptLines = append(scriptLines, remoteRolloutParentGuard(remoteCodexHome, destinationDirectory)...)
	scriptLines = append(scriptLines,
		"guard_rollout_parents",
		"mkdir -p "+quotePOSIX(destinationDirectory),
		"guard_rollout_parents",
		"test ! -e "+quotePOSIX(destinationPath),
		"tmp="+quotePOSIX(temporaryPath),
		`trap 'rm -f "$tmp"' EXIT`,
		"umask 077",
		`cat > "$tmp"`,
		`actual=$(shasum -a 256 "$tmp" | awk '{print $1}')`,
		"test \"$actual\" = "+quotePOSIX(expectedHash),
		`chmod 600 "$tmp"`,
		`mv -n "$tmp" `+quotePOSIX(destinationPath),
		`test ! -e "$tmp"`,
		"trap - EXIT",
	)
	script := strings.Join(scriptLines, "\n")
	command := exec.CommandContext(ctx, "ssh", "-o", "BatchMode=yes", request.Destination.Host, script)
	command.Stdin = bytes.NewReader(request.Content)
	output, err := command.CombinedOutput()
	if err != nil {
		return destinationPath, fmt.Errorf("atomic SSH install: %w: %s", err, strings.TrimSpace(string(output)))
	}
	return destinationPath, nil
}

func remoteRolloutParentGuard(codexHome string, destinationDirectory string) []string {
	return []string{
		"guard_rollout_parents() {",
		"  probe=" + quotePOSIX(destinationDirectory),
		"  while [ \"$probe\" != " + quotePOSIX(codexHome) + " ]; do",
		`    if [ -L "$probe" ]; then echo "rollout destination parent is a symlink: $probe" >&2; exit 18; fi`,
		`    if [ -e "$probe" ] && [ ! -d "$probe" ]; then echo "rollout destination parent is not a directory: $probe" >&2; exit 18; fi`,
		`    parent=$(dirname "$probe")`,
		`    test "$parent" != "$probe"`,
		`    probe=$parent`,
		"  done",
		"}",
	}
}

func resolveSSHCodexHome(ctx context.Context, host string) (string, error) {
	remote := `printf '%s' "${CODEX_HOME:-$HOME/.codex}"`
	command := exec.CommandContext(
		ctx,
		"ssh",
		"-o",
		"BatchMode=yes",
		host,
		"bash -lic "+quotePOSIX(remote),
	)
	output, err := command.CombinedOutput()
	if err != nil {
		return "", fmt.Errorf("resolve remote Codex home: %w: %s", err, strings.TrimSpace(string(output)))
	}
	codexHome := strings.TrimSpace(string(output))
	if !absoluteCleanPath(codexHome) {
		return "", fmt.Errorf("remote Codex home is not an absolute clean path: %q", codexHome)
	}
	return codexHome, nil
}

func verifyRolloutInstall(
	ctx context.Context,
	destination rolloutInstallDestination,
	path string,
	expectedSHA256 string,
) error {
	if !absoluteCleanPath(path) {
		return fmt.Errorf("installed rollout path is not absolute and clean")
	}
	if destination.Kind == rolloutInstallLocal {
		codexHome, err := resolveRehomeCodexHome()
		if err != nil {
			return err
		}
		if err := validateRolloutParentDirectories(codexHome, filepath.Dir(path)); err != nil {
			return err
		}
		info, err := os.Lstat(path)
		if err != nil {
			return err
		}
		if !info.Mode().IsRegular() || info.Mode()&os.ModeSymlink != 0 {
			return fmt.Errorf("installed rollout is not a regular non-symlink file")
		}
		content, err := os.ReadFile(path)
		if err != nil {
			return err
		}
		if hashBytes(content) != expectedSHA256 {
			return fmt.Errorf("installed rollout digest does not match")
		}
		return nil
	}
	if destination.Kind != rolloutInstallSSH || !sshHostPattern.MatchString(destination.Host) {
		return fmt.Errorf("invalid rollout verification destination")
	}
	remoteCodexHome, err := resolveSSHCodexHome(ctx, destination.Host)
	if err != nil {
		return err
	}
	lines := []string{
		"set -eu",
		"test -d " + quotePOSIX(remoteCodexHome),
	}
	lines = append(lines, remoteRolloutParentGuard(remoteCodexHome, filepath.Dir(path))...)
	lines = append(lines,
		"guard_rollout_parents",
		"test -f "+quotePOSIX(path),
		"test ! -L "+quotePOSIX(path),
		`actual=$(shasum -a 256 `+quotePOSIX(path)+` | awk '{print $1}')`,
		"test \"$actual\" = "+quotePOSIX(expectedSHA256),
	)
	script := strings.Join(lines, "\n")
	command := exec.CommandContext(ctx, "ssh", "-o", "BatchMode=yes", destination.Host, script)
	output, err := command.CombinedOutput()
	if err != nil {
		return fmt.Errorf("verify SSH rollout install: %w: %s", err, strings.TrimSpace(string(output)))
	}
	return nil
}
