# Research Hub — Issue Tracker (remaining issues only)

Pruned July 30, 2026. Resolved issues were removed; they live in git history
and in `situations/SUMMARY-2026-07-30.md`. Numbering is stable (historical) so
cross-references from situation docs and the follow-up doc stay valid.

Legend: 🔴 code bug / data-loss risk · 🟡 design gap (needs product decision) ·
🟢 docs/UX housekeeping

---

## 🟡 Issue 5 — No "acknowledge" disposition for yellow edges

New literature makes every method's P1→P2 edge `review_required`; a sibling
rerun makes the other sibling's counterpart edge `review_required`. The only
way to clear yellow is rerunning the phase, even when the user judges the
change irrelevant. Follow-up doc Priority 2/3. Highest day-to-day friction of
the design gaps (situations 01, 02, 03, 05, 08).

## 🟡 Issue 6 — No P1→P3/P4 propagation

New literature yellows P2 but leaves existing P3/P4 green even though novelty
claims, assumptions, or benchmarks may be affected. The P1→P2 half is
implemented (`method_menu.apply_run_provenance(literature_basis=…)` +
`reviewed_no_change` clears yellow without a method edit); the follow-up doc's
Priority-2 statement is partially outdated. Remaining gap is P1→P3/P4 only.

## 🟡 Issue 7 — P4 replacement (not accumulation) evidence model

Each P4 promotion replaces the entire evidence index; findings from superseded
runs (e.g., an instability discovered in a comprehensive run replaced by a
narrower preliminary one) survive only in backups, invisible to downstream
phases and P5. Follow-up doc Priority 3 (cumulative P4 package).

## 🟡 Issue 8 — P5 does not gate on sibling alignment

`phase_records.current_upstream_basis()` checks existence + method identity
only; P5 can assemble from P3/P4 heads that haven't seen each other's latest
rerun (graph flags it, no hard block). Follow-up doc Priority 3. Related:
pre-redesign runs are never adopted into current-record heads
(`has_theory_history: False` for legacy projects) — no bootstrap/repair
tooling.

## 🟡 Issue 9 — No storage lifecycle

Retired branches and sealed per-run context copies accumulate forever
(~1.4 MB/run linear growth; ~39% dead weight in situation 07's analysis).
Follow-up doc Priority 6.

## 🟡 Issue 14 — P2 full-catalog scaling and no subset/batch operations

Full-catalog P2 review is O(n) in method count (~300 KB context per role at 10
methods); the only alternative is one focused run per method. No batch
"retire these, revise this, confirm the rest" operation (situation 11).

## 🟡 Issue 16 — Promotion validates only the frozen manifest identity (latent)

P3/P4/P5 promotion checks the record against the run's frozen manifest
identity, never the live catalog (`phase_records.py:884`, `:890-894`,
`:905-913`). Today the single-active-run rule (`project_state.py:4765-4773`)
makes the dangerous sequence impossible, but the invariant is incidental: if
parallel runs are ever allowed, a stale-identity record would promote as
current. Related: post-promotion staleness is advisory everywhere except the
P5 gate (`current_results.py:9-11`), and the legacy `approve_run` path has no
explicit freshness gate (mitigated by its context-acknowledgement
requirement).

## 🟡 Issue 17 — The protocol checkpoint is not a user checkpoint

Despite the name and read-only UI disclosure, P4's `protocol_checkpoint` never
pauses for user review: the lead dispatches the result task immediately after
machine sealing (`launch_prompts.py:1716-1721`,
`launch_dispatch.py:360-382`); `grep checkpoint webapp.py` = 0. The only user
lever is cancelling the entire run; a sealed checkpoint can never be amended
(`project_state.py:3037`). High expectation gap — either add a real pause or
rename/disclose honestly.

## 🟡 Issue 18 — Limit enforcement happens after the spend

(a) The lead prompt is written unchecked and the 16 MiB cap bites only at
worker start — launch-then-immediately-fail (`launch_run.py:1347` vs
`:1595`). (b) An oversize P1 summary is rejected only at seal, after the full
run completes (`literature_records.py:674-678`). Both should be pre-checked.

## 🔴 Issue 19 — Disaster recovery gaps

Empirically verified (situation 17). (a) A missing control dir makes `load()`
silently return empty state and recreate `project.yaml` — total run-history
loss with zero warning (`project_state.py:784-785`). (b) A deleted workspace
causes an index↔project redirect loop (`webapp.py:975-1005`). (c) Corrupt
YAML / stale-backup journal surface as raw Flask 500s (`webapp.py:934`,
`project_state.py:1711-1714`). (d) hub.db loss has no re-registration path —
the CLI exposes only `init` (`hub.py:997-1010`); an `adopt` command would
make it a non-event. Related (situation 21): hand-edits to workspace files
are all detected and fail closed, but errors name symptoms, not remedies —
no documented repair path for honest mistakes.

## 🟡 Issue 20 — Agent memory is an uncontrolled cross-project channel

Multi-project use shares the four Hermes profiles. Runs don't write profile
memory, but agents' own persistent memories accumulate across projects and
bypass the hub's frozen per-run context (situation 18). No per-project memory
namespacing. Secondary: profile contention between concurrent projects'
runs is invisible in the UI.

## 🟡 Issue 21 — P3 knowledge fragments are machine-unverified

The semantic layer treats agent-declared fragments as ground truth for graph
edges and sibling context. P4 fragments are machine-bound to the evidence
index; P3 fragments are validated only structurally — the manuscript is
hashed, never cross-checked (`theory_records.py:291-306`). A
manuscript/fragment divergence seals silently and renders green (situation
19). At minimum, disclose "semantic content is agent-declared" wherever graph
alignment is shown.

## 🟡 Issue 22 — No correction or retraction path for reference cards

P1's delta-only model rejects existing filenames/canonical identities
(`literature_records.py:12-13`) and the schema has no status/retraction field
(`literature_schema.py`). A misclassified card lives forever in the canonical
library; manual edits are detected (collection digest) but semantically
indistinguishable from tampering (situation 20). Minimal fix: card-level
`status: retracted` honored by the index and agent context.

## 🟡 Issue 23 — Review-revision loops are uncapped and unledgered

No round caps on P5 review cycles (`run_number` increments freely,
`project_state.py:4884-4886`), no consolidated objection history — each
critique lives only in its run's summary (situation 14). Low-Medium.
