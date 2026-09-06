package main

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"strconv"
	"strings"

	sessionmanagement "github.com/ronhuafeng/skills/catalog/codex-sessions/session-management/orchestration-go"
	rollout "github.com/ronhuafeng/skills/harnesses/codex/rollout-go"
)

const (
	exitSuccess = 0
	exitInvalid = 2
	exitBlocked = 3
)

func main() {
	os.Exit(run(context.Background(), os.Args[1:], os.Stdin, os.Stdout, os.Stderr))
}

func run(ctx context.Context, args []string, stdin io.Reader, stdout, stderr io.Writer) int {
	if len(args) > 0 && args[0] == "rollout" {
		return runRollout(args[1:], stdout, stderr)
	}
	if len(args) > 0 && args[0] == "partition" {
		return runPartition(ctx, args[1:], stdin, stdout, stderr)
	}
	if len(args) > 0 && args[0] == "split" {
		return runSplit(ctx, args[1:], stdin, stdout, stderr)
	}
	if len(args) > 0 && args[0] == "rehome" {
		return runRehome(ctx, args[1:], stdin, stdout, stderr)
	}
	if len(args) != 2 {
		fmt.Fprintln(stderr, "usage: session-management <rollout|rename|partition|split|rehome> ...")
		return exitInvalid
	}
	if args[0] == "rename" {
		code, err := runRename(args[1], stdin, stdout)
		if err != nil {
			fmt.Fprintln(stderr, err)
			return code
		}
		return code
	}
	fmt.Fprintln(stderr, "unknown session-management command")
	return exitInvalid
}

func runRename(action string, stdin io.Reader, stdout io.Writer) (int, error) {
	if action != "manifest-targets" {
		return exitInvalid, fmt.Errorf("usage: session-management rename manifest-targets")
	}
	var request sessionmanagement.RenameManifestTargetsRequest
	if err := decodeOne(stdin, &request); err != nil {
		return exitInvalid, err
	}
	if !filepath.IsAbs(request.SplitManifestPath) || request.SplitManifestPath != filepath.Clean(request.SplitManifestPath) {
		return exitInvalid, fmt.Errorf("split_manifest_path must be an absolute clean path")
	}
	targets, err := sessionmanagement.ExtractRenameManifestTargets(request)
	if err != nil {
		return exitBlocked, err
	}
	if err := encode(stdout, targets); err != nil {
		return exitBlocked, err
	}
	return exitSuccess, nil
}

type rehomeRunner func(context.Context, sessionmanagement.RehomeRequest) (sessionmanagement.RehomeResult, error)

func runRehome(ctx context.Context, args []string, stdin io.Reader, stdout io.Writer, stderr io.Writer) int {
	if len(args) != 1 {
		fmt.Fprintln(stderr, "usage: session-management rehome <establish|verify-archive>")
		return exitInvalid
	}
	switch args[0] {
	case "establish":
		return runRehomeEstablishWith(ctx, stdin, stdout, stderr, sessionmanagement.EstablishRehomeDestination)
	case "verify-archive":
		var request sessionmanagement.RehomeArchiveProofRequest
		if err := decodeOne(stdin, &request); err != nil {
			fmt.Fprintln(stderr, err)
			return exitInvalid
		}
		proof, err := sessionmanagement.VerifyRehomeSourceArchive(ctx, request)
		if err != nil {
			fmt.Fprintln(stderr, err)
			if sessionmanagement.IsInvalidRehomeRequest(err) {
				return exitInvalid
			}
			if encodeErr := encode(stdout, proof); encodeErr != nil {
				fmt.Fprintln(stderr, encodeErr)
			}
			return exitBlocked
		}
		if err := encode(stdout, proof); err != nil {
			fmt.Fprintln(stderr, err)
			return exitBlocked
		}
		return exitSuccess
	default:
		fmt.Fprintln(stderr, "usage: session-management rehome <establish|verify-archive>")
		return exitInvalid
	}
}

func runRehomeEstablishWith(ctx context.Context, stdin io.Reader, stdout io.Writer, stderr io.Writer, rehome rehomeRunner) int {
	var request sessionmanagement.RehomeRequest
	if err := decodeOne(stdin, &request); err != nil {
		fmt.Fprintln(stderr, err)
		return exitInvalid
	}
	result, err := rehome(ctx, request)
	if err != nil {
		fmt.Fprintln(stderr, err)
		if sessionmanagement.IsInvalidRehomeRequest(err) {
			return exitInvalid
		}
		if result.RolloutPath != "" {
			if encodeErr := encode(stdout, result); encodeErr != nil {
				fmt.Fprintln(stderr, encodeErr)
			}
		}
		return exitBlocked
	}
	if err := encode(stdout, result); err != nil {
		fmt.Fprintln(stderr, err)
		return exitBlocked
	}
	return exitSuccess
}

func runPartition(ctx context.Context, args []string, stdin io.Reader, stdout, stderr io.Writer) int {
	switch {
	case len(args) > 0 && args[0] == "inspect":
		return runPartitionInspect(ctx, args, stdout, stderr)
	case len(args) == 1 && args[0] == "plan":
		return runPartitionPlan(ctx, stdin, stdout, stderr)
	default:
		fmt.Fprintln(stderr, "usage: session-management partition <inspect session-id [--include-archived] [--window-bytes N]|inspect --continue token|plan>")
		return exitInvalid
	}
}

func runPartitionInspect(ctx context.Context, args []string, stdout, stderr io.Writer) int {
	request, ok := inspectRequest(args, stderr)
	if !ok {
		return exitInvalid
	}
	inspection, err := sessionmanagement.InspectPartition(ctx, request)
	if err != nil {
		fmt.Fprintln(stderr, err)
		return exitBlocked
	}
	if err := encode(stdout, inspection); err != nil {
		fmt.Fprintln(stderr, err)
		return exitBlocked
	}
	return exitSuccess
}

func runPartitionPlan(ctx context.Context, stdin io.Reader, stdout, stderr io.Writer) int {
	var request sessionmanagement.PartitionPlanRequest
	if err := decodeOne(stdin, &request); err != nil {
		fmt.Fprintln(stderr, err)
		return exitInvalid
	}
	plan, err := sessionmanagement.PlanPartition(ctx, request)
	if err != nil {
		fmt.Fprintln(stderr, err)
		return exitBlocked
	}
	if err := encode(stdout, plan); err != nil {
		fmt.Fprintln(stderr, err)
		return exitBlocked
	}
	return exitSuccess
}

func runSplit(ctx context.Context, args []string, stdin io.Reader, stdout, stderr io.Writer) int {
	switch {
	case len(args) > 0 && args[0] == "execute":
		return runSplitExecute(ctx, args, stdin, stdout, stderr)
	case len(args) == 1 && args[0] == "install":
		return runSplitInstall(ctx, stdin, stdout, stderr)
	default:
		fmt.Fprintln(stderr, "usage: session-management split <execute --output-codex-home path|install>")
		return exitInvalid
	}
}

func runSplitExecute(ctx context.Context, args []string, stdin io.Reader, stdout, stderr io.Writer) int {
	if len(args) != 3 || args[1] != "--output-codex-home" || args[2] == "" {
		fmt.Fprintln(stderr, "usage: session-management split execute --output-codex-home path")
		return exitInvalid
	}
	var plan sessionmanagement.PartitionPlan
	if err := decodeOne(stdin, &plan); err != nil {
		fmt.Fprintln(stderr, err)
		return exitInvalid
	}
	result, err := sessionmanagement.ExecuteSplit(ctx, sessionmanagement.SplitExecuteRequest{
		Plan:            plan,
		OutputCodexHome: args[2],
	})
	if err != nil {
		fmt.Fprintln(stderr, err)
		return exitBlocked
	}
	if err := encode(stdout, result); err != nil {
		fmt.Fprintln(stderr, err)
		return exitBlocked
	}
	return exitSuccess
}

func runSplitInstall(ctx context.Context, stdin io.Reader, stdout, stderr io.Writer) int {
	var request sessionmanagement.SplitInstallRequest
	if err := decodeOne(stdin, &request); err != nil {
		fmt.Fprintln(stderr, err)
		return exitInvalid
	}
	result, err := sessionmanagement.InstallSplit(ctx, request)
	if err != nil {
		fmt.Fprintln(stderr, err)
		if sessionmanagement.IsInvalidSplitInstallRequest(err) {
			return exitInvalid
		}
		if encodeErr := encode(stdout, result); encodeErr != nil {
			fmt.Fprintln(stderr, encodeErr)
		}
		return exitBlocked
	}
	if err := encode(stdout, result); err != nil {
		fmt.Fprintln(stderr, err)
		return exitBlocked
	}
	return exitSuccess
}

func inspectRequest(args []string, stderr io.Writer) (sessionmanagement.PartitionInspectRequest, bool) {
	if len(args) == 3 && args[0] == "inspect" && args[1] == "--continue" && args[2] != "" {
		return sessionmanagement.PartitionInspectRequest{Continuation: args[2]}, true
	}
	if len(args) < 2 || args[0] != "inspect" {
		fmt.Fprintln(stderr, "usage: session-management partition inspect <session-id> [--include-archived] [--window-bytes N]")
		return sessionmanagement.PartitionInspectRequest{}, false
	}
	includeArchived := false
	windowBytes := 0
	for index := 2; index < len(args); index++ {
		switch args[index] {
		case "--include-archived":
			if includeArchived {
				fmt.Fprintln(stderr, "inspect accepts --include-archived once")
				return sessionmanagement.PartitionInspectRequest{}, false
			}
			includeArchived = true
		case "--window-bytes":
			if windowBytes != 0 || index+1 >= len(args) {
				fmt.Fprintln(stderr, "inspect accepts one --window-bytes N option")
				return sessionmanagement.PartitionInspectRequest{}, false
			}
			parsed, err := strconv.Atoi(args[index+1])
			if err != nil || parsed < 1 {
				fmt.Fprintln(stderr, "window bytes must be a positive integer")
				return sessionmanagement.PartitionInspectRequest{}, false
			}
			windowBytes = parsed
			index++
		default:
			fmt.Fprintln(stderr, "inspect accepts --include-archived and --window-bytes N")
			return sessionmanagement.PartitionInspectRequest{}, false
		}
	}
	return sessionmanagement.PartitionInspectRequest{
		CodexHome: os.Getenv("CODEX_HOME"), SessionID: args[1], IncludeArchived: includeArchived, WindowBytes: windowBytes,
	}, true
}

func runRollout(args []string, stdout io.Writer, stderr io.Writer) int {
	if len(args) == 0 {
		fmt.Fprintln(stderr, "usage: session-management rollout <session-id-or-path> [--include-archived] [--filter <partial-json-object>]...")
		return exitInvalid
	}
	selector := args[0]
	includeArchived := false
	filters := []rollout.Filter{}
	for index := 1; index < len(args); {
		if args[index] == "--include-archived" {
			includeArchived = true
			index++
			continue
		}
		if args[index] != "--filter" || index+1 >= len(args) {
			fmt.Fprintln(stderr, "rollout accepts --include-archived and repeated --filter <partial-json-object> arguments")
			return exitInvalid
		}
		filter, err := rollout.ParseFilter(args[index+1])
		if err != nil {
			fmt.Fprintf(stderr, "invalid --filter: %v\n", err)
			return exitInvalid
		}
		filters = append(filters, filter)
		index += 2
	}

	path, err := resolveRolloutPath(selector, includeArchived)
	if err != nil {
		fmt.Fprintln(stderr, err)
		return exitInvalid
	}
	err = rollout.Select(path, filters, func(record rollout.Record) error {
		if _, err := stdout.Write(record.Raw); err != nil {
			return err
		}
		_, err := io.WriteString(stdout, "\n")
		return err
	})
	if err != nil {
		var structural *rollout.StructuralError
		if errors.As(err, &structural) {
			fmt.Fprintf(stderr, "%s:%d\n", structural.Path, structural.Line)
			return exitBlocked
		}
		fmt.Fprintln(stderr, err)
		return exitBlocked
	}
	return exitSuccess
}

func resolveRolloutPath(selector string, includeArchived bool) (string, error) {
	if strings.Contains(selector, string(filepath.Separator)) || strings.HasSuffix(selector, ".jsonl") {
		if !filepath.IsAbs(selector) || selector != filepath.Clean(selector) {
			return "", fmt.Errorf("rollout path must be an absolute clean path: %s", selector)
		}
		info, err := os.Stat(selector)
		if err != nil {
			return "", err
		}
		if info.IsDir() {
			return "", fmt.Errorf("rollout path is a directory: %s", selector)
		}
		return selector, nil
	}

	codexHome := os.Getenv("CODEX_HOME")
	if !filepath.IsAbs(codexHome) || codexHome != filepath.Clean(codexHome) {
		return "", fmt.Errorf("CODEX_HOME must be an absolute clean path when selecting by session id")
	}
	return rollout.ResolveSessionFile(codexHome, selector, includeArchived)
}

func decodeOne(reader io.Reader, target any) error {
	decoder := json.NewDecoder(reader)
	var raw json.RawMessage
	if err := decoder.Decode(&raw); err != nil {
		return fmt.Errorf("invalid JSON input: %w", err)
	}
	var extra any
	if err := decoder.Decode(&extra); !errors.Is(err, io.EOF) {
		return fmt.Errorf("invalid JSON input: expected one object")
	}
	trimmed := bytes.TrimSpace(raw)
	if len(trimmed) == 0 || trimmed[0] != '{' {
		return fmt.Errorf("invalid JSON input: expected one object")
	}
	strict := json.NewDecoder(bytes.NewReader(raw))
	strict.DisallowUnknownFields()
	if err := strict.Decode(target); err != nil {
		return fmt.Errorf("invalid JSON input: %w", err)
	}
	return nil
}

func encode(writer io.Writer, value any) error {
	encoder := json.NewEncoder(writer)
	encoder.SetEscapeHTML(false)
	return encoder.Encode(value)
}
