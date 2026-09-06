//go:build !darwin && !linux

package sessionmanagement

import "fmt"

func renameNoReplace(_ string, _ string) error {
	return fmt.Errorf("atomic no-replace directory publication is unsupported on this platform")
}
