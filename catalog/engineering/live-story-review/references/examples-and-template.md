# Live Story Examples and Template

These product-neutral fixtures illustrate the `live-story-review` contract.
They do not add review rules, define a test runner, or authorize a live
operation.

## Good: external report export

```text
Role and goal: An analyst exports one filtered report from a document workspace.
Boundary: The document workspace, from its user interface to the downloaded file.
Given: The reviewed artifact is deployed and deterministic export gates pass.
When: The analyst requests one export through the normal user path.
Then: The interface reaches a terminal state and one readable file is available to the analyst.
Proof-run invocation budget: The acceptance runner requests one export. It does not re-invoke the export after a failed or missing terminal result.
Evidence: Artifact identity, terminal state, file media type, non-zero byte count, and one runner invocation.
Negative evidence: No fallback outside the document workspace, runner re-invocation, unintended mutation, raw report content, or stable user identifier retained.
Partial success: A queued job or internal file record without a user-accessible file.
Does not prove: Other formats, later versions, performance, or another workspace.
```

Deterministic export tests prove prerequisites. The downloaded user artifact
remains the primary proof. One runner invocation does not imply one downstream
transport attempt. The Story constrains product-internal attempts only when
attempt count, cost, latency, exactly-once behavior, or another user-visible
property is part of its claim.

## Bad: internal implementation replaces the outcome

```text
Then: ExportRequest serializes into ExportJob and the storage test observes status=complete.
Evidence: Unit tests, a serializer snapshot, and one database row.
```

This is `P0`: the Story can pass while the user interface never exposes a
download. The internal facts are prerequisite evidence only. The minimum
correction requires one real export and bounded evidence that the
user-accessible file exists.

## Bad: retry manufactures acceptance

```text
When: The acceptance runner sends the paid summarization request up to three times.
Then: Any attempt that returns a terminal result completes the Story.
```

This is `P0`: a failed first operation can disappear behind a later success.
The minimum correction permits one proof-run invocation per acceptance run. A
missing terminal result fails that run. A later invocation requires a new
explicit decision and remains separate evidence.

## Bad: proof budget becomes global provider policy

```text
Story claim: One compaction request uses the selected provider and does not fall back to another provider.
Observed configuration: The selected provider can retry a transient transport failure internally.
Proposed Story repair: Set the provider's global request and stream retry limits to zero.
```

The proposed repair is outside the Story boundary. A single runner invocation
does not imply a single product-internal transport attempt. The no-fallback
claim can reject a request handled by another provider without changing the
selected provider's global retry policy. A zero-retry requirement belongs in
the Story only when single-attempt behavior, cost, latency, or another
user-visible effect is an explicit stable claim.

## Story template

```markdown
# <User-visible outcome>

## User story
As <role>, I can <goal> within <one product or system boundary>.

## Real path
<real operation> -> <externally observable result>

## Acceptance
**Given** <preconditions>, **when** <one bounded operation>, **then** <external terminal result>.

## Partial success is not completion
- <intermediate state>

## Material failure boundaries
- <fallback, attempt, cost, latency, or mutation constraint that is part of the user-visible claim>

## What this does not prove
<explicit limits on version, route, product, environment, and operation scope>

## Proof plan

### Preconditions
- <artifact and environment identity>
- <deterministic prerequisite gates>

### Proof-run invocation budget
<minimum runner invocation count and no runner re-invocation rule>

### Secret-safe evidence
- <bounded positive facts>
- Negative evidence: <plausible alternate paths that could fake the claim or cross its boundary>
```
