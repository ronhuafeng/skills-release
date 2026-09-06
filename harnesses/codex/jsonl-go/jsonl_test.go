package jsonl

import (
	"bytes"
	"os"
	"path/filepath"
	"reflect"
	"testing"
)

func TestScanPreservesNonEmptyRawLines(t *testing.T) {
	long := append([]byte(`{"text":"`), bytes.Repeat([]byte("x"), 1024*1024)...)
	long = append(long, []byte(`"}`)...)

	tests := []struct {
		name    string
		content []byte
		want    []Line
	}{
		{
			name:    "raw bytes blank lines and malformed evidence",
			content: []byte("\n  {not json} \r\n\t \n{\"ok\":true}"),
			want: []Line{
				{Number: 2, Raw: []byte("  {not json} \r")},
				{Number: 4, Raw: []byte(`{"ok":true}`)},
			},
		},
		{
			name:    "line longer than scanner defaults",
			content: append(append([]byte(nil), long...), '\n'),
			want:    []Line{{Number: 1, Raw: long}},
		},
	}

	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			path := filepath.Join(t.TempDir(), "input.jsonl")
			if err := os.WriteFile(path, test.content, 0o600); err != nil {
				t.Fatal(err)
			}

			got := []Line{}
			err := Scan(path, func(line Line) error {
				got = append(got, line)
				return nil
			})
			if err != nil {
				t.Fatal(err)
			}
			for index := range test.want {
				test.want[index].Path = path
			}
			if !reflect.DeepEqual(got, test.want) {
				t.Fatalf("Scan() = %#v, want %#v", got, test.want)
			}
		})
	}
}

func TestScanRangeReturnsSuccessorCursor(t *testing.T) {
	path := filepath.Join(t.TempDir(), "input.jsonl")
	content := []byte("{\"a\":1}\n\n{\"b\":2}\n{\"c\":3}")
	if err := os.WriteFile(path, content, 0o600); err != nil {
		t.Fatal(err)
	}
	first := []Line{}
	next, err := ScanRange(path, Cursor{NextLine: 1}, int64(len(content)), func(line Line, _ Cursor) (bool, error) {
		first = append(first, line)
		return len(first) < 2, nil
	})
	if err != nil {
		t.Fatal(err)
	}
	if next.NextLine != 4 || next.Offset != int64(len("{\"a\":1}\n\n{\"b\":2}\n")) {
		t.Fatalf("successor = %#v", next)
	}
	remaining := []Line{}
	end, err := ScanRange(path, next, int64(len(content)), func(line Line, _ Cursor) (bool, error) {
		remaining = append(remaining, line)
		return true, nil
	})
	if err != nil {
		t.Fatal(err)
	}
	if end.Offset != int64(len(content)) || end.NextLine != 5 || len(remaining) != 1 || remaining[0].Number != 4 {
		t.Fatalf("end = %#v, remaining = %#v", end, remaining)
	}
}
