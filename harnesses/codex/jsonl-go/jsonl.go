package jsonl

import (
	"bufio"
	"bytes"
	"errors"
	"fmt"
	"io"
	"os"
)

// Line is one non-empty JSONL row preserved without its trailing newline.
type Line struct {
	Path   string
	Number int
	Raw    []byte
}

// Cursor identifies the next physical line and byte offset in one file.
type Cursor struct {
	Offset   int64
	NextLine int
}

// Scan visits every non-empty line in source order without retaining the file.
func Scan(path string, visit func(Line) error) (err error) {
	info, err := os.Stat(path)
	if err != nil {
		return err
	}
	_, err = ScanRange(path, Cursor{NextLine: 1}, info.Size(), func(line Line, _ Cursor) (bool, error) {
		return true, visit(line)
	})
	return err
}

// ScanRange visits non-empty lines from start through one fixed byte boundary.
// Returning false from visit stops after the current line and returns its
// successor cursor.
func ScanRange(
	path string,
	start Cursor,
	throughOffset int64,
	visit func(Line, Cursor) (bool, error),
) (next Cursor, err error) {
	if start.Offset < 0 || start.NextLine < 1 || throughOffset < start.Offset {
		return Cursor{}, fmt.Errorf("invalid JSONL scan range")
	}
	file, err := os.Open(path)
	if err != nil {
		return Cursor{}, err
	}
	defer func() {
		err = errors.Join(err, file.Close())
	}()
	if _, err := file.Seek(start.Offset, io.SeekStart); err != nil {
		return Cursor{}, err
	}

	reader := bufio.NewReader(io.LimitReader(file, throughOffset-start.Offset))
	next = start
	for next.Offset < throughOffset {
		current := next
		raw, readErr := reader.ReadBytes('\n')
		if len(raw) == 0 && readErr == io.EOF {
			return Cursor{}, fmt.Errorf("JSONL boundary %d ends before source data", throughOffset)
		}
		next.Offset += int64(len(raw))
		lineNumber := next.NextLine
		next.NextLine++
		if len(raw) > 0 {
			if raw[len(raw)-1] == '\n' {
				raw = raw[:len(raw)-1]
			}
			if len(bytes.TrimSpace(raw)) > 0 {
				keepGoing, visitErr := visit(Line{
					Path:   path,
					Number: lineNumber,
					Raw:    bytes.Clone(raw),
				}, current)
				if visitErr != nil {
					return Cursor{}, visitErr
				}
				if !keepGoing {
					return next, nil
				}
			}
		}
		if readErr == nil {
			continue
		}
		if readErr == io.EOF {
			if next.Offset != throughOffset {
				return Cursor{}, fmt.Errorf("JSONL boundary %d splits a source line", throughOffset)
			}
			return next, nil
		}
		return Cursor{}, readErr
	}
	return next, nil
}
