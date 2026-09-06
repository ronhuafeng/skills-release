//go:build darwin

package sessionmanagement

import "golang.org/x/sys/unix"

func renameNoReplace(source string, destination string) error {
	return unix.RenamexNp(source, destination, unix.RENAME_EXCL)
}
