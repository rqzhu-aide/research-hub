# Research Hub — Issue Tracker

Remaining open issues. Numbering is stable (historical) so cross-references
from situation docs and the follow-up doc stay valid. Resolved issues and
older situation analyses are in `archived/` (not tracked).

**Categories:**
- **🔴 Error** — current behavior is wrong, produces incorrect results, or loses data. Should be fixed.
- **🟡 Functionality** — a feature is missing or a design gap exists. Nothing is actively broken; the system works as designed but is incomplete.

**Error-class round (2026-07-30, commits `2e4f7c6`, `5d4a7f4`):**

- **#7 FIXED** — superseded same-version runs (e.g., a comprehensive P4
  replaced by a narrower rerun) now enter downstream context as labeled
  non-current history, so their findings are no longer invisible. Also fixed
  a regression where a newer failed run hid the current record from context.
- **#8 WITHDRAWN (false report)** — P5 already hard-blocks on yellow sibling
  edges: `phase_five_branch_readiness` aggregates counterpart edges into the
  P3/P4 graph nodes and the launch raises on any non-`exact_match` node
  (`launch_manifest.py:1719-1768`, `launch_run.py:851-858`; test
  `test_phase_five_readiness_rejects_yellow_p3_or_p4_alignment`). The
  situation analyses had read `current_upstream_basis()` and missed the gate.
  Situation docs 03 and 11 corrected.
- **#20 FIXED** — lead prompts and task briefs now carry a "Project scope and
  memory" block (namespace memory per project, disregard other projects'
  memories). Residual: profile contention between concurrent projects' runs
  is still invisible in the UI (🟡, see below).
- **#23 ADDRESSED** — a review-revision run now sees the previous cycle's
  summary in context (via the #7 mechanism; test
  `test_p5_review_context_includes_prior_review_cycle`). Residual: no hard
  cap on revision cycles (product decision — see below).

---

## 🔴 Errors

*(none open)*

---

## 🟡 Functionality gaps

### #5 — No "acknowledge" disposition for yellow edges

New literature makes every method's P1→P2 edge `review_required`; a sibling
rerun makes the other sibling's counterpart edge `review_required`. The only
way to clear yellow is rerunning the phase. **User decision (2026-07-30):
forced rerun is the accepted behavior; this will not be addressed for now.**
Lowest priority. (Situation 08.)

### #6 — No P1→P3/P4 propagation

New literature yellows P2 but leaves existing P3/P4 green even though novelty
claims, assumptions, or benchmarks may be affected. The P1→P2 half is
implemented (`reviewed_no_change` clears yellow without a method edit).
Remaining gap is P1→P3/P4 only.

### #9 — No storage lifecycle

Retired branches and sealed per-run context copies accumulate forever
(~1.4 MB/run linear growth). Follow-up doc Priority 6.

### #14 — P2 full-catalog scaling and no subset/batch operations

Full-catalog P2 review is O(n) in method count (~300 KB context per role at 10
methods); the only alternative is one focused run per method. No batch
"retire these, revise this, confirm the rest" operation (situation 11).

### #19-note — No re-registration command after hub.db loss

The destructive parts of #19 are fixed (loud failure, no redirect loop,
guidance page). Remaining: `hub.py` still exposes only `init`
(`hub.py:997-1010`); an `adopt <directory>` command (re-register a project
from its surviving workspace/control dir with the original id) would make
hub.db loss a non-event.

### #22 — No correction or retraction path for reference cards

P1's delta-only model rejects existing filenames/canonical identities
(`literature_records.py:12-13`) and the schema has no status/retraction field
(`literature_schema.py`). A misclassified card lives forever in the canonical
library; manual edits are detected (collection digest) but semantically
indistinguishable from tampering (situation 20). Minimal fix: card-level
`status: retracted` honored by the index and agent context.

### #23-note — No cap on P5 revision cycles

The visibility half of #23 is fixed (prior cycle's summary enters context).
Remaining: nothing limits revision rounds (`run_number` increments freely,
`project_state.py:4884-4886`). A cap is a product decision.

### #20-note — Profile contention between concurrent projects is invisible

When two projects' runs compete for the same Hermes profile, the losing run
waits with no status or queue hint (situation 18).
