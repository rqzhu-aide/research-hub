# Research Hub — Issue Tracker

Remaining open issues. Numbering is stable (historical) so cross-references
from situation docs and the follow-up doc stay valid. Resolved issues and
older situation analyses are in `archived/` (not tracked).

**Categories:**
- **🔴 Error** — current behavior is wrong, produces incorrect results, or loses data. Should be fixed.
- **🟡 Functionality** — a feature is missing or a design gap exists. Nothing is actively broken; the system works as designed but is incomplete.

---

## 🔴 Errors

### #7 — P4 replacement model loses prior evidence

Each P4 promotion replaces the entire evidence index; findings from superseded
runs survive only in backups, invisible to downstream phases and P5. Follow-up
doc Priority 3 (cumulative P4 package). (Situation 09.)

### #8 — P5 does not gate on sibling alignment

`phase_records.current_upstream_basis()` checks existence + method identity
only; P5 can assemble from P3/P4 heads that haven't seen each other's latest
rerun. The graph flags the misalignment but P5 does not hard-block — a
manuscript can be assembled from incompatible theory/empirical heads.
Follow-up doc Priority 3. Related: pre-redesign runs are never adopted into
current-record heads — no bootstrap/repair tooling. (Situation 09.)

### #20 — Agent memory is an uncontrolled cross-project channel

Multi-project use shares the four Hermes profiles. Runs don't write profile
memory, but agents' own persistent memories accumulate across projects and
bypass the hub's frozen per-run context (situation 18). No per-project memory
namespacing. Secondary: profile contention between concurrent projects' runs
is invisible in the UI.

### #23 — Review-revision loops are uncapped and unledgered

No round caps on P5 review cycles (`run_number` increments freely,
`project_state.py:4884-4886`), no consolidated objection history — each
critique lives only in its run's summary (situation 14). Low-Medium.

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
