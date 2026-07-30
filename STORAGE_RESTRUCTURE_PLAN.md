# Storage Current-Head Foundation: Revised Implementation Plan

Status: proposed for implementation

Scope: minimum safe storage and current-version foundation

## 1. Decision and purpose

Research Hub needs a small, authoritative record of which completed result is
currently relevant for each phase. Later runs should use those current results
by default instead of collecting every earlier run.

This plan implements that foundation first. It deliberately does not implement
content-addressed object storage, context compaction, canonical scientific
packages, or the artifact dependency graph.

The first implementation will:

- preserve the existing schema 11 copied context directories;
- add exact current-head records for global and method-bound phases;
- introduce exact current-run selection instead of all-history selection;
- promote a valid finalized run automatically;
- keep the previous head current while a rerun is in progress;
- distinguish method freshness, scientific outcome, and record integrity;
- preserve every old run as archived provenance;
- bootstrap existing projects without rewriting scientific files;
- provide a stable interface for later scientific packages and graph work.

Production enforcement is phase-specific. In particular, Phase 4 and the
current-head-only Phase 5 path remain in `Shadow` until cumulative Phase 4
evidence has been consolidated.

With schema 11 copies still present, context growth becomes approximately linear
rather than quadratic. If a current context has size \(S\) and a branch is run
\(n\) times, the copied-input growth becomes

\[
O(nS)
\]

instead of

\[
S(1 + 2 + \cdots + n)
= \frac{n(n+1)}{2}S
= O(n^2S).
\]

Eliminating repeated copies of identical payloads is a later optimization.

## 2. User-control invariant

No phase is launched automatically.

The user decides:

- whether to run or rerun a phase;
- what instructions to provide;
- which method to select for a method-bound phase;
- whether to run Phase 3, Phase 4, or both after Phase 2;
- when to recheck a stale theoretical or empirical result.

Automatic promotion only changes which completed result is considered current.
It does not launch another phase, approve a result, or make a scientific
decision for the user.

## 3. Workflow invariants

### 3.1 Phase scope

- Phase 1 is global.
- Phase 2 is global and publishes the feasible-method catalog.
- Phases 3, 4, and 5 are bound to one selected method branch.

Phase 5 must never be stored under a global method key.

### 3.2 Parallel Phase 3 and Phase 4 work

After Phase 2 identifies a method, the user may run either Phase 3 or Phase 4
first. Both phases may use the most recent available Phase 3 and Phase 4 records
for that branch. Neither requires the other to have run first.

### 3.3 Phase 5 readiness

Phase 5 may run only when the selected branch has usable Phase 3 and Phase 4
heads matching the exact active method definition. Global Phase 1 and Phase 2
requirements must also be satisfied.

For this foundation, an intact `Complete` or `Partial` head counts as a
completed phase result, matching current behavior. A `Partial` result remains
yellow and fully visible, and the user decides whether to launch Phase 5. It
can never produce a graph-level green state.

Approval is not the scientific baseline. The current heads are. Existing
`approved_run` fields may remain temporarily for compatibility or for a
separate review-revision workflow, but they must not choose routine context,
make a P3 or P4 result current, or serve as the general Phase 5 gate.

### 3.4 Method revisions

Every method-bound head is tied to

\[
(\text{stable method ID},\ \text{method version},\
\text{method definition SHA-256}).
\]

When Phase 2 changes a method definition:

1. Update the branch's active method identity.
2. Retain the existing P3 and P4 heads.
3. Report those heads as stale because their identities no longer match.
4. Let the user rerun either phase in any order.
5. Make a result fresh only when its frozen identity matches the active method.

For this milestone, `definition_sha256` is the existing exact digest of the
complete method file. Any byte change therefore makes prior branch results
stale. A future normalized scientific-definition digest may exclude explicitly
specified presentation metadata, but this implementation must not infer that
two different method files are scientifically equivalent.

### 3.5 Reruns

Starting a rerun does not invalidate the prior head. The old result remains
current until a valid replacement is finalized and promoted.

If a new attempt fails, is cancelled, or is ineligible, the prior head remains
unchanged. Mutable statuses such as `awaiting_review`, `revision_requested`,
`approved`, and `superseded` do not determine whether an intact head remains
current.

## 4. Scope

### Included

- versioned current-head records;
- exact method identity on every method-bound head;
- per-phase generation numbers;
- launch-basis records freezing selected heads and generations;
- automatic promotion after valid finalization;
- atomic comparison and update;
- crash recovery and idempotent reconciliation;
- current-only context resolution;
- conservative bootstrap for existing projects;
- Phase 2 method-change reconciliation;
- Phase 5 readiness projection from exact current heads;
- basic Web UI status;
- concurrency, integrity, migration, and workflow tests.

### Deferred

- content-addressed object storage;
- schema 12 object-reference manifests;
- hard-link, reflink, or copy-on-write optimization;
- context compaction and garbage collection;
- storage reporting;
- arbitrary archived-run selection in launch context;
- canonical Phase 3 and Phase 4 scientific packages;
- cumulative Phase 4 evidence reconciliation;
- the artifact dependency graph;
- scientific mutation history beyond operational promotion receipts.

`context_from` is static phase configuration. It is not an existing
user-facing archived-run selector.

A verified run bundle does not certify cumulative Phase 4 evidence. Therefore:

- Phase 4 current-only selection remains in `Shadow` until a canonical
  cumulative package or a verified one-time consolidation exists;
- the new Phase 5 head-only path also remains in `Shadow` until that condition
  is met;
- existing production Phase 4 and Phase 5 behavior is not silently narrowed
  during this foundation release.

## 5. Terminology

**Current head:** The one verified run that supplies the default result for a
phase.

**Active method identity:** The exact method identity currently published by
Phase 2 for a stable branch.

**Fresh head:** A method-bound head whose identity matches the active method.

**Stale head:** An intact prior head whose identity no longer matches the active
method. It remains useful as a labeled recheck baseline.

**Provisional legacy result:** An old run for which exact identity or a modern
run contract cannot be verified. It is preserved but cannot be treated as a
fresh current head.

**Verified run bundle:** The existing sealed manifest, final summary, decision,
and manifest-declared artifacts that pass current integrity validation.

**Launch basis:** The immutable record of the exact heads, method identity, and
generation numbers selected when a run launched.

**Promotion:** Atomic replacement of one phase head with a finalized eligible
run.

A verified run bundle is not yet a canonical Phase 3 or Phase 4 scientific
package. This distinction must remain visible.

## 6. Control-storage layout

All paths must be derived from `core.project_state.state_dir(project_dir)`.
Code must not construct a second control directory inside the user project.

Conceptual layout beneath the returned state directory:

```text
current-results/
  global.json
  branches/
    <safe-branch-key>.json
  launch-bases/
    <safe-run-key>.json
  transactions/
    <safe-operation-key>.prepared.json
  receipts/
    <safe-operation-key>.applied.json
    <safe-operation-key>.not-applied.json
  migration/
    bootstrap-report.json
```

Requirements:

- raw method, run, and operation IDs are never trusted as paths;
- validated helpers derive branch, run, and operation keys by hashing canonical
  validated identifiers;
- each branch record stores the original stable ID;
- launch, transaction, and receipt records store the original run and operation
  IDs inside their validated contents;
- directories must be plain directories, not redirects or reparse points;
- record sizes and collection lengths are bounded;
- schemas reject duplicate or unknown critical identity fields;
- writes use a temporary file in the same directory and atomic replacement;
- one current-results lock serializes publication;
- this implementation never moves or deletes scientific artifacts.

## 7. Record model

### 7.1 Global record

`global.json` stores only Phase 1 and Phase 2 heads:

```json
{
  "schema_version": 1,
  "heads": {
    "01-literature-review": {
      "generation": 3,
      "run_id": "run-01-example",
      "phase_slug": "01-literature-review",
      "scientific_outcome": "Complete",
      "representation": "verified_run_bundle",
      "source_integrity": {
        "run_manifest_sha256": "abc123...",
        "final_summary_sha256": "def456...",
        "decision_sha256": "789abc..."
      },
      "promoted_at": "2026-07-28T12:00:00Z",
      "operation_id": "promote-..."
    }
  }
}
```

### 7.2 Branch record

Each branch record stores the active method and independent P3, P4, and P5
heads:

```json
{
  "schema_version": 1,
  "stable_id": "method-a",
  "method_status": "active",
  "catalog_generation": 7,
  "active_method_identity": {
    "stable_id": "method-a",
    "version": "v3",
    "definition_sha256": "74bc..."
  },
  "heads": {
    "03-idea-evaluation": {
      "generation": 4,
      "run_id": "run-03-example",
      "phase_slug": "03-idea-evaluation",
      "method_identity": {
        "stable_id": "method-a",
        "version": "v3",
        "definition_sha256": "74bc..."
      },
      "scientific_outcome": "Complete",
      "representation": "verified_run_bundle",
      "source_integrity": {
        "run_manifest_sha256": "abc123...",
        "final_summary_sha256": "def456...",
        "decision_sha256": "789abc..."
      },
      "promoted_at": "2026-07-28T14:00:00Z",
      "operation_id": "promote-..."
    },
    "04-draft-assembly": {
      "generation": 6,
      "run_id": "run-04-example",
      "phase_slug": "04-draft-assembly",
      "method_identity": {
        "stable_id": "method-a",
        "version": "v2",
        "definition_sha256": "19ad..."
      },
      "scientific_outcome": "Complete",
      "representation": "verified_run_bundle",
      "source_integrity": {
        "run_manifest_sha256": "abc123...",
        "final_summary_sha256": "def456...",
        "decision_sha256": "789abc..."
      },
      "promoted_at": "2026-07-28T11:00:00Z",
      "operation_id": "promote-..."
    }
  }
}
```

Here P3 is fresh and P4 is stale. This is a valid transitional state. Every
head retains the identity of the run that produced it.

### 7.3 Required head fields

Every head contains:

- phase slug and run ID;
- per-phase generation;
- exact method identity for a method-bound phase;
- scientific outcome;
- representation type;
- sealed source digests;
- promotion time;
- idempotent promotion operation ID.

`status_at_promotion` may be recorded for diagnosis, but mutable run status is
never authoritative.

`head_sha256` is defined as SHA-256 over the UTF-8 canonical JSON encoding of
the complete validated head object. The encoding is:

```python
json.dumps(
    normalized_head,
    sort_keys=True,
    separators=(",", ":"),
    ensure_ascii=False,
    allow_nan=False,
).encode("utf-8")
```

The digest field itself is not part of `normalized_head`.

### 7.4 Derived state

Method-bound state is derived:

- `fresh`: identity matches and integrity passes;
- `stale`: exact intact identity differs from the active method;
- `provisional`: exact identity or modern contract cannot be verified;
- `corrupt`: a required digest or artifact fails;
- `missing`: no eligible head exists;
- `retired`: the method is retired.

Scientific outcome is separately `Complete` or `Partial`.

Representation is separately:

- `verified_run_bundle`;
- `canonical_scientific_package`, reserved for the next layer;
- `legacy_provisional`.

Until canonical packages exist, the UI may say that a run is up to date, but it
must also say that the scientific package is not consolidated. The dependency
graph must not treat a verified run bundle as a complete knowledge record.

## 8. Launch-basis record

Schema 11 snapshot leaves have strict field sets. Do not insert object IDs or
generation fields into them.

Create an immutable sidecar at:

```text
current-results/launch-bases/<safe-run-key>.json
```

Example:

```json
{
  "schema_version": 1,
  "run_id": "new-run-id",
  "target_phase": "04-draft-assembly",
  "selected_method_identity": {
    "stable_id": "method-a",
    "version": "v3",
    "definition_sha256": "74bc..."
  },
  "selected_heads": [
    {
      "scope": "global",
      "phase_slug": "02-method-development",
      "run_id": "run-02-example",
      "generation": 5,
      "head_sha256": "ed12..."
    },
    {
      "scope": "branch",
      "phase_slug": "03-idea-evaluation",
      "run_id": "run-03-example",
      "generation": 4,
      "head_sha256": "c8a1..."
    },
    {
      "scope": "branch",
      "phase_slug": "04-draft-assembly",
      "run_id": "run-04-example",
      "generation": 6,
      "head_sha256": "b731...",
      "relationship": "stale_recheck_baseline"
    }
  ],
  "same_phase_base_generation": 6,
  "created_at": "2026-07-28T15:00:00Z"
}
```

Run state stores the sidecar path and SHA-256 in a versioned
`current_results_basis` field. This is an explicit project-state schema change.

Implementation must:

- increment `project_state.SCHEMA_VERSION`;
- add migration defaults for existing runs;
- validate that the sidecar path remains beneath `state_dir(project_dir)`;
- validate its digest in `_validate_run_integrity` and `run_integrity_report`;
- reject an enforced new run whose required launch basis is missing or changed.

The existing schema 11 context still freezes the actual files used. The sidecar
freezes why they were selected and which head generations were observed.

## 9. Context resolution

Preserve the configured phase context policy, but resolve each allowed phase
and scope to at most one exact head.

Resolve target run IDs first. Verify them, then pass only those runs to the
existing snapshot builder. Do not enumerate all runs and filter later.

The resolver merges:

1. global P1 and P2 heads;
2. branch-specific P3, P4, and P5 heads.

Default inputs:

| Target | Default current inputs |
|---|---|
| P1 | Current P1 baseline when rerun policy permits |
| P2 | Current P1 and current P2 baseline |
| P3 | Global prerequisites, branch P3 head, branch P4 head if available |
| P4 | Global prerequisites, branch P4 head, branch P3 head if available |
| P5 | Global prerequisites, fresh branch P3 and P4 heads, branch P5 head on rerun |

A stale P3 or P4 head may be included for the same stable method as a labeled
recheck baseline. It is not presented as evidence about the new definition.
No older sibling runs are added automatically.

For a missing or corrupt record:

1. Validate the current-head record.
2. If absent, attempt deterministic bootstrap of one exact head.
3. If exactly one head is recovered, write it and continue.
4. If ambiguous, preserve the archive and report ambiguity.
5. If corrupt, report an integrity error.
6. Omit optional context or block required context according to phase policy.

There is no fallback to all historical runs, and no silent `except: pass`.

## 10. Promotion eligibility

A run may replace a head only when:

- finalization succeeded;
- scientific outcome is `Complete` or `Partial`;
- current integrity checks pass;
- required final summary and decision are sealed;
- the phase is eligible to produce a replacement head;
- a method-bound run has exact frozen identity;
- its identity matches the active Phase 2 method at promotion time;
- its same-phase base generation satisfies the promotion policy.

A structurally intact `Partial` result may become current, but remains visibly
partial. Promotion does not imply that every downstream policy must accept it.

Never promote:

- failed or cancelled runs;
- corrupt runs;
- method-bound runs without exact identity;
- runs for an obsolete method definition;
- Phase 3 `audit_only` under its current contract;
- auxiliary reviews or diagnostics that do not replace the phase result.

An unresolved method-bound run is never assigned to `_global`.

## 11. Promotion, locking, and recovery

The project lock is non-reentrant. A current-results helper must not be called
inside `finalize_run_submission()` when it might reacquire that lock.

The first implementation should not hold the project lock and current-results
lock at the same time.

Finalization sequence:

1. Under the project lock, validate and persist normal finalization.
2. Capture immutable candidate data in an internal result or local variable.
3. Release the project lock.
4. Build and validate the candidate.
5. Acquire the current-results lock.
6. Load the current global or branch record.
7. Recheck active method identity and same-phase generation.
8. Write a prepared transaction.
9. Atomically write the updated current-head record.
10. Write an applied receipt.
11. Release the current-results lock.
12. Reacquire the project lock only for a non-authoritative run annotation.

The public `finalize_run_submission(...) -> bool` contract must remain
unchanged because worker and submission callers rely on it. Use an internal
unlocked helper, wrapper, or local post-lock candidate rather than returning
promotion data through the public API.

Review every finalization early return so an eligible run cannot silently skip
post-lock promotion.

Generation comparison is per phase, not for the whole branch. Concurrent P3 and
P4 promotions must preserve both heads. For concurrent reruns of the same phase,
the first valid comparison wins. The other run remains archived and receives a
generation-conflict result.

Compare the run identity with the active Phase 2 identity, not with the old
head. Otherwise the first valid run after a method revision cannot promote.

Prepared transactions include:

- operation ID deterministically derived from phase and run ID;
- run, phase, scope, and branch key;
- expected same-phase generation;
- frozen and observed active method identities;
- proposed complete head and digest;
- preparation time.

The filesystem name uses the safe hash key, never the raw operation ID.

Recovery handles:

- finalized run with no transaction;
- prepared transaction with no pointer update;
- pointer update with no receipt;
- receipt with missing run annotation;
- generation or method conflicts.

Each unapplied operation receives an exact reason. Promotion failure is never
ignored, and the prior head remains valid until atomic replacement succeeds.

Operational receipts are not the later scientific mutation history. They only
record current-head publication.

## 12. Phase 2 reconciliation

The sealed Phase 2 catalog is authoritative. The active identities in branch
records are validated cache projections of that catalog.

When Phase 2 publishes its method catalog:

1. Under the project lock, seal the catalog and persist a
   `reconciliation_pending` marker containing the source P2 run ID and catalog
   digest.
2. Release the project lock.
3. Create a durable current-results reconciliation transaction.
4. Resolve and validate every stable ID, version, and definition digest.
5. Create or load each branch record.
6. Store `catalog_source_run_id` and `catalog_sha256` in every updated branch.
7. Increment `catalog_generation` for a method identity change.
8. Retain all phase heads without rewriting their identities.
9. Derive fresh or stale state from the new identity.
10. Complete every branch update and write the reconciliation receipt.
11. Clear the project-state pending marker in a later project-lock operation.

For retirement, set `method_status` to `retired`, preserve all heads and runs,
and require explicit reactivation before ordinary method-bound work.

Multiple branch files cannot be replaced atomically. On every read or launch,
compare the authoritative sealed catalog digest with the branch
`catalog_sha256`. A mismatch or pending marker yields
`reconciliation_pending`: warn or block according to phase requirements, and
never report old cached heads as fresh.

Recovery resumes the transaction idempotently. Project state must not claim a
new catalog and silently treat old cached identities as current.

## 13. Phase 5 readiness

For the selected method, verify:

- active exact method identity;
- intact P3 and P4 heads;
- both heads match the active method;
- each outcome is `Complete` or structurally intact `Partial`;
- no unresolved required promotion;
- required global P1 and P2 state.

Freeze exact P3 and P4 run IDs, generations, identities, and head digests in the
P5 launch basis. A completed P5 head stores the launch-basis digest and those
upstream generations and head digests.

Later P3 or P4 promotion does not change the inputs of an active or completed
P5 run. It deterministically makes the existing P5 head stale for future use
when either current upstream generation or head digest differs.

Routine P5 readiness does not require approval.

Until P4 cumulative evidence is consolidated, this exact head-only P5 check is
computed in `Shadow`; it does not replace the production input path.

## 14. Existing-project bootstrap

Bootstrap is non-destructive derived indexing, not destructive migration.

Rules:

- never edit or delete existing runs;
- never rewrite schema 11 manifests;
- never infer version or digest from a branch path alone;
- never assign unresolved method work to `_global`;
- reuse the identity and integrity rules of verified completed-result selectors;
- verify manifests, exact identity, summary, decision, outcome, and integrity;
- report every skipped or ambiguous candidate.

Do not call `completed_method_branch_result()` unchanged. Its workflow-status
filter excludes `revision_requested` and `superseded`. Factor its exact
identity, outcome, summary, manifest, and integrity checks into a generalized
candidate validator, then apply this plan's broader bootstrap status policy.

For exact modern global or branch runs:

- require sufficient modern identity data;
- require `Complete` or `Partial`;
- require intact finalization and summary;
- accept mutable statuses including `awaiting_review`, `revision_requested`,
  `approved`, and `superseded` when the scientific result remains intact;
- select the newest deterministically finalized eligible run.

Global bootstrap covers P1 and P2. Branch bootstrap covers P3, P4, and P5.

If only a stable ID is recovered from `output_root`, mark the run
`legacy_provisional`. Do not attach the current version or digest to it.

Legacy P3 without a verifiable replacement contract and legacy P4 without
cumulative evidence reconciliation are not graph-eligible. They may be shown as
provisional comparison baselines.

Run bootstrap on first project open after enablement, before resolving a missing
head, through an explicit repair operation, and during startup recovery. It must
be idempotent.

## 15. Web UI behavior

For every method, show separately:

- active method version;
- current P3 and P4 runs and times;
- freshness for each phase;
- scientific outcome for each phase;
- representation type;
- integrity warnings;
- latest failed or conflicted attempt.

Suggested labels:

- `Up to date`;
- `Needs recheck after method change`;
- `Current result is partial`;
- `Legacy result needs reconciliation`;
- `No current result`;
- `Integrity problem`;
- `Method retired`.

Do not collapse these into one ambiguous color. A stale yellow state informs the
user but does not launch anything.

The primary workflow does not need an approval button to make a completed run
current. Legacy approval metadata may remain hidden or in a compatibility view.
The UI must not claim that archived-run selection already exists.

## 16. Code integration

Add `core/current_results.py` for:

- paths through `state_dir(project_dir)`;
- schemas, bounds, and branch keys;
- record reads and integrity validation;
- locking and atomic writes;
- launch-basis creation;
- promotion and recovery;
- catalog reconciliation;
- bootstrap and repair;
- UI status projection.

Update:

| File | Change |
|---|---|
| `core/project_state.py` | Preserve the public finalization boolean, capture internal post-lock promotion data, bump state schema, validate launch-basis integrity, and journal catalog reconciliation |
| `core/launch_prompts.py` | Resolve exact heads before the existing schema 11 snapshot builder |
| `core/launch_run.py` | Freeze head identities and generations; compute exact P5 readiness behind the rollout gate |
| `core/launch_manifest.py` | Keep schema 11 leaf validation unchanged and verify head run bundles |
| `core/launch_plans.py` | Use branch P3 and P4 heads for P5 planning |
| `core/web_phase_data.py` | Expose heads, freshness, outcomes, representation, and recovery errors |
| `webapp.py` and `templates/` | Show method-level current state without approval-based selection |
| `config.yaml` | Preserve P5 method binding and prohibit a global fallback |

Use small helpers instead of adding another large block to `project_state.py`.

## 17. Implementation sequence

### Milestone 0: contract tests

Add schema fixtures, failing workflow tests, selector comparison fixtures, and
an `off`, `shadow`, or `enforced` feature mode.

Exit: intended semantics are executable as tests.

### Milestone 1: storage primitives

Implement `core/current_results.py`, safe paths, bounded schemas, the dedicated
lock, atomic writes, record reads, and derived status.

Exit: corrupt records are rejected without changing launch behavior.

### Milestone 2: shadow bootstrap

Build heads for existing projects, compare them with current selectors, and
write exact, provisional, skipped, and ambiguous results to a report.

Exit: deterministic results with no changed scientific files.

### Milestone 3: freeze launch basis

Resolve exact heads, write the sidecar, save its digest in run state, preserve
schema 11 snapshots, bump and migrate project state, extend run-integrity
checks, and verify copied files came from the selected runs.

Exit: each launch has reproducible files and frozen head generations.

### Milestone 4: promotion and recovery

Refactor post-lock finalization, implement eligibility and per-phase comparison,
add transactions and receipts, recover interrupted operations, and expose
errors.

Exit: valid runs promote exactly once and every injected crash recovers.

### Milestone 5: method reconciliation

Journal the authoritative catalog digest, publish cached active identities,
derive P3 and P4 staleness, preserve retired methods, detect pending projection,
and test concurrent catalog and phase finalization.

Exit: a method revision makes both heads stale and either can independently
return to fresh after a user-launched rerun, with no interval in which a stale
catalog projection is reported as current.

### Milestone 6: current-only context

Enable exact selection, merge global and branch heads, include one labeled stale
baseline when useful, and remove all-history fallback for phase-gated enforced
paths. Keep P4 in `Shadow` until cumulative evidence is consolidated.

Exit: every eligible enforced phase receives at most one head per relevant
phase, while P4 shadow comparison exposes any evidence that would be omitted.

### Milestone 7: Phase 5 and UI

Compute exact P5 readiness from branch heads, freeze P3 and P4 generations,
derive completed P5 staleness from upstream changes, show method-level state,
separate current from failed attempts, and remove approval from current-result
selection. Keep the new P5 input path in `Shadow` until P4 consolidation.

Exit: users can understand state and decide what to run, and shadow comparison
demonstrates that P5 would not lose applicable P4 evidence.

### Milestone 8: rollout

Run Linux tests, available Windows path and locking tests, shadow comparisons,
controlled enablement, recovery monitoring, and documentation updates.

## 18. Required tests

### Scope and identity

- only P1 and P2 create global heads;
- P3, P4, and P5 require exact branch identity;
- unresolved method runs never become global;
- P3 `audit_only` never replaces the ordinary P3 head;
- P3 and P4 may temporarily have different method versions;
- promotion compares with the active catalog, not the old head.

### Reruns and concurrency

- first eligible run creates generation 1;
- rerun start leaves the prior head current;
- mutable review status does not remove the head;
- intact `Complete` and `Partial` results promote with distinct outcomes;
- failed, cancelled, corrupt, and obsolete runs do not promote;
- two same-phase reruns cannot both replace one generation;
- concurrent P3 and P4 promotions preserve both heads;
- repeated promotion is idempotent.

### Context

- each allowed phase contributes at most one head;
- global and branch heads merge correctly;
- P3 receives P4 and P4 receives P3 when available;
- stale inputs are labeled as recheck baselines;
- archives are not automatic context;
- missing heads rebuild deterministically or report a problem;
- corrupt heads never trigger all-history fallback;
- schema 11 contexts remain verifiable.

### Phase 5

- P5 is method-bound;
- P5 rejects mismatched, missing, or corrupt P3 and P4 heads;
- P5 freezes exact P3 and P4 generations;
- later upstream promotions make a completed P5 head stale;
- `Complete` and intact `Partial` satisfy the initial routine completion rule;
- `Partial` remains yellow and never graph-green;
- routine readiness does not require approval.

### Method changes

- definition change makes both P3 and P4 stale;
- display-only change does not;
- either phase may return to fresh first;
- first valid run for the new method can promote;
- old-definition completion is archived as obsolete;
- interrupted catalog reconciliation recovers.
- any method-file byte change stales prior heads in this milestone.
- a pending marker or catalog-digest mismatch prevents a stale branch cache
  from being reported as fresh.

### Bootstrap and integrity

- exact modern runs produce deterministic heads;
- stable-ID-only recovery stays provisional;
- old schemas without exact identity are not certified;
- ambiguous ordering is reported;
- bootstrap is idempotent and changes no legacy file;
- bootstrap uses the generalized candidate validator under the broader status
  policy;
- raw method, run, and operation IDs never become filenames;
- canonical JSON produces the same `head_sha256` deterministically;
- a missing or changed launch-basis sidecar fails integrity for an enforced new
  run;
- invalid paths, links, reparse escapes, and oversized records are rejected;
- failed writes preserve the prior record;
- every transaction boundary recovers;
- no lock inversion occurs.

### Storage growth

Across ten reruns:

- each run copies only selected current heads;
- no context includes a chain of every earlier run;
- counts and bytes grow approximately linearly;
- tests do not claim object-level deduplication.

## 19. Rollout modes

**Off:** Existing behavior.

**Shadow:** Compute and compare current heads without controlling context.

**Enforced:** Current heads control context only for phase paths whose
replacement completeness has been verified. Missing, ambiguous, or corrupt
required heads warn or block. They never restore all-history behavior.

The active mode is visible and logged. Automatic rollback may return to
`Shadow`, but not silently to all-history behavior in `Enforced`.

P4 remains in `Shadow` until cumulative evidence is consolidated. The new
head-only P5 path remains in `Shadow` for the same reason. This foundation can
be complete while those two production switches remain gated.

## 20. Foundation completion criteria

The foundation is complete when:

1. Phase scope is correct.
2. Every method-bound head retains exact run identity.
3. Valid finalization promotes automatically without approval.
4. Failed reruns preserve the prior head.
5. Method changes make P3 and P4 independently stale.
6. Context resolves at most one head per relevant phase.
7. Missing or corrupt pointers never restore all history.
8. Launch bases freeze identity and generations.
9. Promotion is atomic, idempotent, and recoverable.
10. Existing projects bootstrap without deletion.
11. Phase 5 readiness projection uses exact P3 and P4 branch heads.
12. P5 staleness follows exact upstream generations and head digests.
13. The UI distinguishes freshness, outcome, provisional state, and integrity.
14. Schema 11 contexts remain readable.
15. Eligible enforced paths show linear rather than quadratic context growth.
16. P4 and P5 shadow comparison reports evidence that current-only selection
    would omit.

Only then should other subsystems depend on the current-head interface.

## 21. Required next core layer

Before the production dependency graph:

- ordinary P3 runs must produce a complete replacement theory manuscript;
- P4 runs must produce a current empirical synthesis and cumulative evidence
  index;
- every prior P4 evidence item must be retained, revalidated, revised,
  superseded, withdrawn, or marked unresolved.

Only canonical packages can support a graph-level green state representing the
complete current scientific record. This is core functionality, not cosmetic
polishing.

A verified cumulative P4 package, or an equivalent one-time consolidation, is
also required before enabling current-only P4 context and the head-only P5
input path in production.

## 22. Later optimization

After current heads and canonical packages are stable, a separate plan may add:

- a project-scoped content-addressed object store;
- schema 12 object references;
- safe copy-on-write views or normal copies;
- storage reporting and archive-selection controls;
- mark-and-sweep compaction and explicit quarantine.

Canonical objects must never be hard-linked into writable contexts. A write
through a hard link would mutate the object. Schema 11 leaves remain unchanged
unless a new schema or verified sidecar is introduced.

The artifact graph must not be implemented in parallel with an unverified
current-head foundation.
