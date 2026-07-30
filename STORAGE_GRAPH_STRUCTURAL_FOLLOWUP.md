# Storage and Graph Structural Follow-up

## Audit conclusion

The current implementation has a sound core:

- every phase is started explicitly by the user;
- Phase 3 and Phase 4 are parallel sibling workflows;
- method-bound runs freeze an exact method definition and current branch inputs;
- method changes and sibling changes represented in the structured knowledge
  fragment cannot remain falsely green;
- Phase 3 and Phase 5 maintain one current replacement record;
- Phase 1 and Phase 4 retain cumulative material under phase-specific rules;
- Phase 5 binds exact usable current runs and rechecks branch state before
  launch; and
- the branch graph is derived from authoritative current records rather than
  treated as a source of scientific truth.

The remaining items below require schema changes, new user interfaces, or
cross-module transaction work. They should not be folded into small cleanup
patches.

## Completed: Phase 1 basis used by Phase 5

Phase 5 now records two independent Phase 1 inputs:

- the current literature synthesis digest; and
- the canonical reference-card collection digest.

The launch snapshot validates the frozen synthesis and reference index before
constructing the manuscript basis. The branch graph compares the two inputs on
separate edges, so a new reference can require manuscript review even when the
synthesis text is unchanged. Phase 1 generation identifiers remain available
as provenance but do not by themselves imply a scientific change.

The manuscript schema is now version 2 and the graph schema is version 3.
Older records remain readable. A legacy manuscript that does not identify its
exact Phase 1 reference collection is shown as requiring review rather than
being treated as current. The user decides whether and when to rerun Phase 5;
the change never starts a run automatically.

An in-progress schema 12 Phase 5 run reconstructs its basis only from its
frozen launch files. Older launch manifests that do not contain an exact frozen
basis must start a new run before publication. A legacy manuscript can still be
read or restored during rollback, but it cannot replace a current schema 2
manuscript.

Regression tests cover collection-only changes, synthesis-only changes,
combined changes, legacy records, frozen-snapshot consistency, replacement,
rollback, ambiguous JSON rejection, and historical launch compatibility.

## Priority 2: complete Phase 2 provenance and literature propagation

### Current gap

After a focused Phase 2 rerun, the Phase 2 prerequisite used by Phase 5 points
to the latest catalog run for every method. The catalog does not state which run
introduced or most recently changed each individual method. The global snapshot
may be the intended provenance, but that policy is not explicit.

The graph currently connects Phase 1 directly to Phase 5. New literature can
also change novelty claims, method positioning, assumptions, theoretical
comparisons, or experimental benchmarks in Phases 2 through 4. The software
does not yet encode which of those records should require review. It also has no
stored Phase 1 basis or review disposition that can clear a Phase 2 yellow state
when a rerun concludes that the new references do not require a method change.

### Required product decision

1. Define the Phase 2 provenance model. Either store a per-method
   `source_run_id` or last-definition-change identity, or explicitly define the
   complete current catalog snapshot as the provenance for every method.
2. Store the Phase 1 basis reviewed by the current catalog, together with the
   outcome of that review. A no-change conclusion must update this basis so the
   workflow can converge without an artificial method edit.
3. Define explicit directed effects for a Phase 1 change. A conservative first
   policy is:

   - new literature makes the Phase 2 catalog yellow;
   - a Phase 2 definition change then makes the affected Phase 3 and Phase 4
     branch records yellow through the existing method edges; and
   - the user decides which phase to rerun, with no automatic launch.

If direct Phase 1 effects on Phase 3 or Phase 4 are desired, represent them as
separate review edges with clear reasons. Do not infer scientific consequences
from a changed hash alone.

### Acceptance criteria

- Every literature-driven yellow state identifies the affected claim or phase.
- Phase 5 reports the intended Phase 2 provenance for the selected method.
- A Phase 2 no-change review records the new literature basis and clears the
  corresponding yellow state.
- A status change never launches work.
- A researcher can leave a record unchanged after inspection only through an
  explicit, auditable acknowledgement policy.

## Priority 3: separate alignment, research attention, and scientific outcome

### Current gap

The graph uses `alignment_status` both for dependency alignment and for Phase 4
evidence attention. Any outdated or unresolved evidence makes the Phase 4 node
yellow and blocks Phase 5. This may be the desired Phase 5 policy, but the state
is not purely mechanical alignment.

A cumulative Phase 4 package can also be valid and current while retaining
superseded, withdrawn, outdated, or unresolved entries for provenance. These
states have different scientific meanings and should not be compressed into one
field.

### Required change

Represent at least four independent dimensions:

- record integrity: present, missing, or invalid;
- dependency alignment: exact, changed, legacy unknown, or unavailable;
- research attention: none, outdated evidence, unresolved evidence, or another
  stated limitation; and
- scientific completion outcome: Complete, Partial, or Failed.

Then define Phase 5 eligibility explicitly. For example, method and sibling
alignment may be mandatory, while the product policy can separately decide
whether unresolved evidence blocks assembly or is carried into the manuscript
as a limitation. Also decide whether a changed sibling basis always requires a
rerun, or whether the researcher can record an auditable "reviewed, no rerun
required" disposition when the change is immaterial to the current result.

### Acceptance criteria

- Green never implies scientific validity.
- Yellow states identify whether the cause is changed inputs or unresolved
  research.
- The Phase 5 blocker names the exact policy dimension that failed.
- Partial outcomes remain visible wherever their current records are used.
- Any no-rerun disposition records who made the decision, the compared inputs,
  the reason, and the exact state that the decision clears.

## Priority 4: strengthen the semantic coverage contract

### Current gap

P3 and P4 sibling comparison is intentionally based on structured knowledge
fragments, not every byte in the theory manuscript, empirical synthesis, or
lead summary. This avoids false ping-pong from formatting and metadata changes.
It also means a decision-relevant change is detected only if the lead records it
in the structured fragment.

### Required change

1. Define which theorem, assumption, limitation, implementation, and evidence
   changes must appear in the structured fragment.
2. Validate coverage against the lead summary and canonical package before
   promotion.
3. Record an explicit coverage result in the promotion transaction.
4. Add adversarial tests in which the manuscript changes but the fragment does
   not.

Do not simply hash the full manuscripts into sibling semantic alignment. That
would restore noise-driven reciprocal reruns.

### Acceptance criteria

- Every decision-relevant canonical change has a structured identity.
- Formatting-only edits do not make the sibling phase yellow.
- Omitted structured coverage prevents promotion or produces a clear red state.

## Priority 5: add researcher-facing current-record and context views

### Current gap

The Web UI shows the Phase 2 method definition, latest run summary, and compact
branch status. It does not provide one branch-centered view of the authoritative
current theory manuscript, empirical synthesis, evidence dispositions, current
manuscript, and structured change history. It also does not enumerate the exact
inputs that a configured run will receive before launch.

### Required change

Build two read-only views:

1. **Current branch record**
   - method identity and version;
   - current P3, P4, and P5 source run;
   - safe links or rendered views of the canonical files;
   - evidence counts by disposition;
   - scientific outcome and limitations; and
   - the reason for every yellow or red state.
2. **Inputs this run will receive**
   - exact P1 through P5 records selected by phase policy;
   - source run and generation where relevant;
   - archived Phase 3 summaries included or excluded;
   - run mode and method definition; and
   - any acknowledged context limitation.

Add a branch change timeline backed by the immutable events. The current
structured event ledger covers P3 and P4; extend or map P1, P2, and P5 changes
so the researcher sees one coherent history.

### Acceptance criteria

- A researcher can inspect the material behind a status without browsing
  internal control files.
- The prelaunch receipt matches the sealed manifest exactly.
- A red state offers a supported diagnostic and recovery path.
- Review and revision is disabled until a verified current manuscript exists.

## Priority 6: design a bounded storage lifecycle

### Current gap

Current working records are compact, but sealed run provenance and Phase 4
artifacts accumulate. The Phase 4 evidence index also has a fixed 2,000-entry
limit and no supported archival or compaction path. There is no storage report,
export-and-prune workflow, or safe garbage collector.

### Required change

1. Add per-project and per-branch storage accounting.
2. Define content-addressed reuse for identical frozen inputs and large
   artifacts.
3. Add a provenance-preserving archive format.
4. Add a safe pruning plan that first computes every reference from current
   records, review snapshots, manifests, and change events.
5. Partition or compact the Phase 4 evidence index without losing stable
   evidence identities.
6. Keep export, verification, and restore tests as part of the storage contract.

### Acceptance criteria

- The interface explains what is using storage.
- No referenced current input can be pruned.
- An archived branch can be verified and restored.
- Phase 4 can exceed 2,000 lifetime evidence entries without losing provenance.

## Priority 7: complete transaction and cache coverage

### Current gaps

- The optional persistent graph cache is refreshed for P3 and P4 promotion
  recovery, but P1, P2, and P5 changes can leave an existing cache stale. Live
  decisions currently rebuild the graph and remain safe.
- Phase 5 promotion does not explicitly compare the live current manuscript
  with the manuscript state frozen at launch. A manual external edit during a
  run could therefore be overwritten.

### Required change

1. Either remove the unused persistent graph cache or invalidate every affected
   branch after P1, P2, and P5 transactions.
2. Include cache invalidation in the same recovery and fault-injection tests as
   canonical promotion.
3. Add an expected current manuscript identity to Phase 5 promotion.
4. Reject a lost-update attempt and preserve both the frozen run output and the
   intervening current manuscript.

### Acceptance criteria

- No durable cache survives an upstream mutation while claiming to be current.
- A Phase 5 run cannot overwrite a current manuscript that changed after launch.
- Crash recovery converges to one verified state without manual file edits.

## Priority 8: continue module separation

The storage implementation is now divided by phase, but several coordination
modules remain very large. In particular, project state, prompt construction,
launch coordination, Web phase projection, and method catalog logic still mix
schema validation, migration, transaction control, and presentation.

Split by stable responsibility after the correctness items above:

1. run-state schema and migration;
2. run lifecycle transitions;
3. prerequisite and current-record selection;
4. promotion coordination and recovery;
5. phase-specific prompt assembly;
6. Web view models; and
7. legacy compatibility adapters.

Each extraction should preserve behavior with characterization tests before
moving code. Avoid a broad rewrite.
