# Situation 14: The P5 Review-Revision Loop

## Scenario

P5 assembly produces a manuscript for `method-alpha`. The researcher launches
P5 in `review_revision` mode; the paper_reviewer requests revisions. The team
revises and reruns review-revision. The reviewer requests changes **again** —
and a third time — before acceptance. How does the cycle work mechanically,
and what keeps it honest?

## Step-by-step evaluation

### Step 1: P5 assembly

- **System behavior**: assembly freezes the exact upstream basis (P1
  synthesis + collection digests, P2 definition digest, P3 record, P4
  synthesis + evidence index) via `current_upstream_basis()`
  (`phase_records.py:408`) and promotes a current manuscript record (schema
  2). Manuscript records are **current-replacement**: each promotion replaces
  the canonical manuscript for the branch, backup retained
  (`manuscript_records.py`).
- **Smooth?** ✅ Yes.

### Step 2: First review-revision run

- **System behavior**: the reviewer substage works on a **sealed review
  target**. `seal_review_target()` (`project_state.py:5140-5188`) records the
  manuscript path + sha256 + size while the run is `starting`/`running`;
  every reviewer substage reads exactly that file. Tamper evidence:
  `_validate_recorded_review_target()` (`:5191-5218`) fails integrity if the
  target changes after reviewer dispatch ("review target changed after
  reviewer dispatch"). Re-sealing identical content is idempotent
  (`:5170-5177`); different content → `StateConflict("the run review target
  is already sealed")` (`:5178`).
- **Available targets**: the launch form lists prior assembly runs whose
  manuscript can be reviewed (`web_phase_data._available_review_targets`,
  `:690-759`; each entry carries run_id, path, sha256).
- **Smooth?** ✅ The reviewer cannot be fooled by a mid-run manuscript swap.

### Step 3: Reviewer requests revisions

- **System behavior**: the review run completes with a revision outcome; the
  review output is recorded (2 MB review-output cap,
  `project_state.py:67`). The manuscript record is not touched by a rejected
  review — the current manuscript stays as assembled.
- **Smooth?** ✅ Yes.

### Step 4: Revise and rerun review-revision

- **System behavior**: each revision cycle is a **new run** with its own
  review-target seal. The same unchanged manuscript *can* be reviewed again
  (new run → new seal); equally, a revised manuscript can be assembled first
  (a new assembly run → new manuscript generation) and then reviewed.
- **Cap on rounds**: none. P5 has no `rounds` policy for review cycles;
  `run_number = len(phase["runs"]) + 1` (`project_state.py:4884-4886`). A
  reviewer can request changes indefinitely.
- **Smooth?** ⚠️ Mechanically fine, but nothing surfaces "this is revision
  round N" or detects an oscillating reviewer.

### Step 5: Third review accepts

- **System behavior**: the accepted review promotes the manuscript record
  with an advanced generation; the record's `paper_review` kind distinguishes
  assembly vs review (`review_only`/`full`). Review history lives in run
  records, not in the manuscript record — the manuscript record stores the
  current manuscript and its basis, not the chain of critiques.
- **Smooth?** ⚠️ The audit trail of *what the reviewer objected to across
  rounds* exists only as per-run summaries; there is no consolidated review
  ledger.

### Step 6: P3/P4 change between assembly and review

- **System behavior**: the review run freezes its own upstream basis at
  launch and validates frozen identities (`phase_records.py:902-915`,
  `expected_upstream_basis=manifest_upstream_basis(...)`). If the underlying
  P3/P4 records changed between assembly and review, the branch graph flags
  the manuscript's edges `review_required`, and any *new* assembly must match
  the current basis.
- **Smooth?** ✅ Detected and surfaced; not hard-blocked (consistent with the
  sibling-alignment policy, ISSUES.md #8).

## Issues identified

### 🟡 Issue A: No cap or visibility on revision loops

**Severity: Low-Medium.** Nothing limits or even counts revision cycles; an
oscillating reviewer (or a manuscript that genuinely can't converge) burns
uncapped runs. A "revision round N, previous objections: …" rollup would help
the user decide when to intervene.

### 🟡 Issue B: Review history is fragmented across runs

**Severity: Low.** Each critique lives in its run's summary; the manuscript
record carries no review ledger. After three rounds, answering "what did the
reviewer ask for, and did we address it?" means reading three run summaries
manually.

### 🟢 Observation: mid-run review integrity is solid

The sealed review target + tamper re-validation means the reviewer always
evaluates exactly the manuscript the user saw at dispatch. Re-reviewing an
unchanged manuscript across runs is allowed (each run re-seals), which is the
correct semantics.

## Space summary

| Component | Size |
|---|---|
| P5 assembly (manuscript gen-1) | ~0.5 MB |
| 3 × review-revision runs | ~0.9 MB |
| Final accepted review (gen-2) | ~0.3 MB |
| Control + backups | ~0.5 MB |
| **Total** | **~2.2 MB** |

## Verdict

✅ **The review-revision loop is mechanically sound** — sealed targets,
frozen bases, exact tamper evidence, correct re-review semantics.

⚠️ **It is also unbounded and unledgered.** No round caps, no consolidated
objection history; convergence is entirely the user's judgment.
