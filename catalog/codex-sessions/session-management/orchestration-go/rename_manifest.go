package sessionmanagement

import "fmt"

type RenameManifestTargetsRequest struct {
	SplitManifestPath string `json:"split_manifest_path"`
}

type RenameManifestTarget struct {
	ThreadID string `json:"thread_id"`
	Title    string `json:"title"`
}

type RenameManifestTargets struct {
	Targets []RenameManifestTarget `json:"targets"`
}

func ExtractRenameManifestTargets(request RenameManifestTargetsRequest) (RenameManifestTargets, error) {
	if !absoluteCleanPath(request.SplitManifestPath) {
		return RenameManifestTargets{}, fmt.Errorf("split_manifest_path must be an absolute clean path")
	}
	manifest, err := validatePublishedSplitManifest(request.SplitManifestPath)
	if err != nil {
		return RenameManifestTargets{}, fmt.Errorf("validate split manifest for rename targets: %w", err)
	}
	targets := make([]RenameManifestTarget, 0, len(manifest.Parts))
	for _, part := range manifest.Parts {
		targets = append(targets, RenameManifestTarget{ThreadID: part.SessionID, Title: part.Title})
	}
	return RenameManifestTargets{Targets: targets}, nil
}
