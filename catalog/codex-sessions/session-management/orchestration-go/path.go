package sessionmanagement

import "path/filepath"

func absoluteCleanPath(path string) bool {
	return filepath.IsAbs(path) && path == filepath.Clean(path)
}

func normalizeExistingPath(path string) (string, error) {
	resolved, err := filepath.EvalSymlinks(path)
	if err != nil {
		return "", err
	}
	abs, err := filepath.Abs(resolved)
	if err != nil {
		return "", err
	}
	return filepath.Clean(abs), nil
}
