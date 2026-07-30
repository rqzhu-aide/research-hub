# Research Hub — Issue Tracker (remaining issues only)

Pruned July 30, 2026 (second pass). Resolved issues live in git history and in
`situations/SUMMARY-2026-07-30.md`. Numbering is stable (historical) so
cross-references from situation docs and the follow-up doc stay valid.

**Fixed in this round** (commits `01a4a8d`, `7ee3cbc`, `bf24c66`, `28e0bb2`):

- **#19** Disaster recovery: missing control dir now fails loudly instead of
  silently resetting (run-generated artifact dirs detected); index↔project
  redirect loop killed; corrupt state renders a recovery-guidance page.
  (Residual: no `adopt` re-registration command — see #19-note below.)
- **#18** Lead-prompt cap enforced at launch (`check_lead_prompt_size`); P1
  playbook documents the 5 MiB synthesis / 1 MiB card budget.
- **#16** Promotion now refuses an outdated frozen method identity
  (`enforce_catalog_identity_current` at P3/P4/P5 promotion).
- **#17** Protocol checkpoint disclosed everywhere as a machine-sealed
  provenance record, not a user gate (UI, playbook, website docs).
- **#21** Graph alignment note discloses agent-authored fragments: P4
  machine-checked, P3 content not machine-verified.

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
implemented (`reviewed_no_change` clears yellow without a method edit).
Remaining gap is P1→P3/P4 only.

## 🟡 Issue 7 — P4 replacement (not accumulation) evidence model

Each P4 promotion replaces the entire evidence index; findings from superseded
runs survive only in backups, invisible to downstream phases and P5. Follow-up
doc Priority 3 (cumulative P4 package).

## 🟡 Issue 8 — P5 does not gate on sibling alignment

`phase_records.current_upstream_basis()` checks existence + method identity
only; P5 can assemble from P3/P4 heads that haven't seen each other's latest
rerun (graph flags it, no hard block). Follow-up doc Priority 3. Related:
pre-redesign runs are never adopted into current-record heads — no
bootstrap/repair tooling.

## 🟡 Issue 9 — No storage lifecycle

Retired branches and sealed per-run context copies accumulate forever
(~1.4 MB/run linear growth; ~39% dead weight in situation 07's analysis).
Follow-up doc Priority 6.

## 🟡 Issue 14 — P2 full-catalog scaling and no subset/batch operations

Full-catalog P2 review is O(n) in method count (~300 KB context per role at 10
methods); the only alternative is one focused run per method. No batch
"retire these, revise this, confirm the rest" operation (situation 11).

## 🟡 Issue 20 — Agent memory is an uncontrolled cross-project channel

Multi-project use shares the four Hermes profiles. Runs don't write profile
memory, but agents' own persistent memories accumulate across projects and
bypass the hub's frozen per-run context (situation 18). No per-project memory
namespacing. Secondary: profile contention between concurrent projects' runs
is invisible in the UI.

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

## 🟢 Issue 19-note — Residual: no re-registration command after hub.db loss

The destructive parts of #19 are fixed (loud failure, no redirect loop,
guidance page). Remaining: `hub.py` still exposes only `init`
(`hub.py:997-1010`); an `adopt <directory>` command (re-register a project
from its surviving workspace/control dir with the original id) would make
hub.db loss a non-event.
