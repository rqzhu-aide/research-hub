# Research Hub — Issue Tracker (post-redesign evaluation)

Compiled July 30, 2026, after a full evaluation of commit `d077722`
("Implement versioned research records and alignment") and a verification
pass over the `situations/` scenario analyses. Test state at evaluation:
**873 passed, 1 failed, 3 skipped** (HEAD red).

Legend: 🔴 code bug · 🟠 data/ops · 🟡 design gap (needs product decision) ·
🟢 docs housekeeping

---

## 🔴 Issue 1 — Crash recovery `_sync` crash wedges the project (both promotion modules)

**Status: FIXED (this change set).**

**Symptom.** `tests/test_empirical_promotion_intent.py::
test_lock_held_paths_do_not_reacquire_project_lock` fails at HEAD:
`EmpiricalRecordPromotionError: empirical transaction directory could not be
synchronized: .../branches/method-a/draft/sections`.

**Root cause.** In `empirical_promotion._recover_unlocked` (and symmetrically
in `theory_promotion`), the "completed" recovery states call
`_sync(canonical.parent)`, which does `os.open(directory, os.O_RDONLY)` +
`fsync`. When a **first-ever promotion for a new branch** is interrupted
*after* `promotion_journal.prepare()` made the intent durable but *before*
`promote_output()` created the branch directory tree, that parent directory
does not exist, so recovery crashes instead of returning the correct no-op.

**Why it matters.** `_reconcile_promotion_journals_unlocked` runs on **every
locked project load** (`project_state._load_reconciled_unlocked`) and re-raises
recovery failures as `StateValidationError`. A wedged journal therefore makes
the **whole project unopenable** — every page and launch fails — until manual
repair (`mkdir` the missing directory). Theory surfaces the same bug as a raw,
unwrapped `FileNotFoundError` and had **no test coverage** for it.

**Sites.**
- `core/empirical_promotion.py`: `_recover_unlocked` completed-state syncs
  (lines ~821, ~829, ~882).
- `core/theory_promotion.py`: `_sync_transaction_parent(canonical.parent)` in
  recovery completed states (lines ~926, ~947, ~955, ~994).

**Fix.** Guard the transaction-parent sync: create the parent directory when
it is missing (`mkdir(parents=True, exist_ok=True)`) before fsync, which is
also the semantically correct durability action (the directory entry itself
should exist and be synced). Added `test_theory_promotion_intent.py` regression
coverage mirroring the empirical test.

**Manual workaround (unfixed deployments).** Create the missing directory
(`branches/<method>/evaluations/` for theory, `branches/<method>/draft/
sections/` for empirical), then reload the project; reconcile completes.

---

## 🟠 Issue 2 — Project-004 legacy catalog breaks knowledge-graph build

**Status: FIXED (data repair, July 30, 2026; backup
`/tmp/registry-backup-20260730.yaml`).** Registry label aligned to the method
file (`Permutation-Augmented Independent Langevin (PAIL)`); catalog loads and
`build_branch_basis_graph` succeeds. All edges show `not_available` by design
— pre-redesign runs are not adopted into current records (see Issue 8).

**Original symptom.** `knowledge_graph.build_branch_basis_graph()` for
`~/research/projects/project-004-entangled-langevin-sampling` raises
`KnowledgeGraphBuildError: the current method catalog is invalid: method
registry label for 'permutation-augmented-langevin' does not match its method
file`.

**Cause.** The published registry (`ideas/methods/_registry.yaml`) records
label `Permutation-Augmented Independent Langevin`, while the method file
front-matter says `Permutation-Augmented Independent Langevin (PAIL)`. The
catalog was published before the redesign's strict registry↔file validation
existed. The UI degrades gracefully (phase pages render), but the branch
graph and its statuses are unavailable.

**Fix.** Data repair: align the registry label with the method file (the file
is the user-facing scientific record). No code change required, but a
repair/migration path for pre-redesign catalogs may be worth considering
(see Issue 8).

---

## 🟠 Issue 3 — Project-004 sealed-evidence hash chain broken by the slug migration

**Status: FIXED (data repair, July 30, 2026).**

**Symptom.** `project_state.prerequisite_report(..., "05-review-revision")`
reported Phase 3 blocked: `reason: "approved evidence is missing or changed"`,
`integrity_detail: "run manifest changed after launch preparation"`.

**Root cause (confirmed).** On 2026-07-26 00:43–00:44 the slug migration
(`_migrate_slug_aliases`, since removed in `e95da3f`) rewrote the sealed files
of every run under the two renamed phase directories (03, 04) — manifests,
sealed prompts, task briefs, decision records, and HTML summaries — replacing
old phase slugs with new ones, **without updating the corresponding recorded
digests** in `project.yaml`. Five hash layers went stale:

1. `run.manifest_sha256` (3 runs: 9081e83c, dab6390b, 75cfd941)
2. `manifest.prompt_sha256` embedded in each manifest
3. `rounds[].tasks[].brief_sha256` (21 task briefs)
4. `decision_record.sha256`/`size`/`data`/`schema_version` + the
   `approval_baseline_acknowledgement.decision_record_sha256` mirror
5. `summary_sha256` (3 HTML summaries)

Runs in unrenamed phases (01, 02) were untouched and always passed.

**Repair (following the in-repo precedent of `_migrate_sealed_decision_record`
/ "F9 fix").** For each affected run, recomputed every recorded digest from
the current sealed files (content verified to contain only new slugs), rewrote
manifests in their original serialization, refreshed embedded decision-record
state with the hub's own `_read_decision_record_file` normalizer, and stamped
`decision_record_rehashed_at_migration` on updated acknowledgements. Backups:
`/tmp/rh-repair-20260730/` (state + manifests + prompts).

**Verification.** All 7 runs now pass `_validate_run_integrity`; the P5 gate
reports P3 "approved and current". P4 remains blocked only by design
(`awaiting_review` — the user has not approved it).

**Residual risk.** The pre-migration file bytes are unrecoverable (no backups
of the originals existed), so the repair trusts that the Jul-26 rewrite was
the slug migration — supported by mtimes, zero remaining old-slug occurrences,
and all frozen snapshot hashes (12/12) validating. If a canonical
pre-migration copy ever surfaces, compare against it.

---

## 🟠 Issue 4 — Live server runs pre-redesign code under the wrong interpreter

**Status: FIXED (July 30, 2026).** Old process (PID 1020381, started Jul 29
under the Hermes venv, pre-`d077722`) stopped; server restarted from the repo
with `.venv/bin/python webapp.py` on :5055. All phase tabs verified 200
against project-004. Caveat: the replacement process is tied to the agent
session that launched it; for a durable service, start it from a login shell
or a systemd --user unit.

**Original symptom.** PID 1020381 (`webapp.py`, cwd `/home/tez/product/research-hub`)
has served :5055 since Jul 29 14:33 — before commit `d077722` — using the
Hermes agent venv Python instead of the project `.venv`.

**Fix.** Restart from the repo with `.venv/bin/python` (port via
`RESEARCH_HUB_PORT`, default 5055).

---

## 🟡 Issue 5 — No "acknowledge" disposition for yellow edges

New literature makes every method's P1→P2 edge `review_required`; a sibling
rerun makes the other sibling's counterpart edge `review_required`. The only
way to clear yellow is rerunning the phase, even when the user judges the
change irrelevant. Tracked as Priority 2/3 in
`STORAGE_GRAPH_STRUCTURAL_FOLLOWUP.md`. Highest day-to-day friction of the
design gaps (situations 01, 02, 03, 05). **Requires a product decision** on
what an acknowledgement records and what may clear it.

## 🟡 Issue 6 — No P1→P3/P4 propagation

New literature yellows P2 but leaves existing P3/P4 green even though novelty
claims, assumptions, or benchmarks may be affected. Follow-up doc Priority 2.

**Update (July 30, 2026, via `situations/08`):** the P1→P2 half of this is
now *implemented* — a focused P2 rerun applies the current literature basis
as provenance (`method_menu.apply_run_provenance(literature_basis=...)`) and
a `reviewed_no_change` review clears the P1→P2 yellow without a method edit.
The follow-up doc's Priority-2 statement ("no stored Phase 1 basis or review
disposition that can clear a Phase 2 yellow state") is partially outdated.
The remaining gap is P1→P3/P4 only.

## 🟡 Issue 7 — P4 replacement (not accumulation) evidence model

Completing failed experiments requires redoing all experiments; the prior
Partial package becomes a backup. Follow-up doc Priority 3 (cumulative P4
package).

## 🟡 Issue 8 — P5 does not gate on sibling alignment (and legacy data has no adoption path)

`phase_records.current_upstream_basis()` checks existence + method identity
only; P5 can assemble a manuscript from siblings that have not seen each
other's latest rerun (graph flags it, no hard block). Follow-up doc Priority 3.
Related: pre-redesign runs are never adopted into the new current-record
heads (`has_theory_history: False` for project-004 despite two P3 runs) —
legacy data is history-only by design, but no bootstrap/repair tooling exists
(cf. Issue 2).

## 🟡 Issue 9 — No storage lifecycle

Retired branches and sealed per-run context copies accumulate forever
(~1.4 MB/run linear growth). Follow-up doc Priority 6.

---

## 🟡 Issue 12 — P3 Partial trap: Partial theory can neither promote nor feed Phase 5

**Status: FIXED (July 30, 2026).** Both gates relaxed:

1. `phase_records.py:664` — theory seal gate now uses the standard
   Complete-or-Partial `eligible` check (was `outcome == "Complete"`).
2. `launch_manifest.PHASE_FIVE_ACCEPTED_SCIENTIFIC_OUTCOMES` — P3 now accepts
   `("Complete", "Partial")`.

Contract docs updated (README, architecture/pipeline/phase-4/decisions,
P3 playbook): a Partial theory feeds Phase 5 with its stated limitations
carried forward; Failed still never qualifies. Tests:
`test_theory_seal_accepts_partial_outcome`,
`test_theory_seal_still_rejects_failed_outcome`,
`test_phase_five_readiness_accepts_partial_current_theory` (replaces the old
requires-Complete test).

**Original report.** Raised by `situations/06-p3-partial-trap.md`; **verified against code**
(July 30, 2026). Two independent gates create the trap:

1. **Seal gate** — `phase_records.py` (~line 664): theory sealing requires
   `outcome == "Complete"` specifically, unlike literature/method/empirical
   which use `eligible` (Complete **or** Partial). A Partial P3 promotes
   nothing; the branch has no current theory record.
2. **Readiness gate** — `launch_manifest.PHASE_FIVE_ACCEPTED_SCIENTIFIC_OUTCOMES`:
   P1, P2, P4 accept `("Complete", "Partial")`; P3 accepts `("Complete",)`
   only. Even a promoted Partial theory would be rejected by Phase 5.

Notable: `theory_records` itself already accepts Partial
(`_ELIGIBLE_OUTCOMES = {"Complete", "Partial"}`) — the record layer supports
it; only the orchestration and readiness gates block it. The README
("Phase 3 must be Complete") documents this as deliberate policy, so this is
a **design decision to revisit**, not a bug. Real research routinely produces
Partial theories (unproven lemma, numerically-verified regularity condition);
the current policy makes them dead ends. Any fix needs both gates plus a
visible limitation marker carried into the manuscript.

## 🟡 Issue 13 — Failed runs are invisible to rerun context

**Status: FIXED (July 30, 2026).** `launch_prompts.py`:
`_CONTEXT_RESULT_STATUSES` now includes `failed` (label "failed prior
attempt"). Branch-scoped phases admit the **latest** failed attempt on the
branch alongside the current record (older failures stay excluded); global
phases surface a failed run only when it is newer than the latest usable
result. Failed entries render as untrusted/unusable advisory evidence with
the pre-existing "scientific outcome Failed" label, so agents see what went
wrong without mistaking it for a valid result. The archived-summary option
still requires a *usable* non-current result (failed runs do not unlock it).
Tests: `test_latest_failed_attempt_enters_branch_context_as_advisory`,
`test_failed_run_enters_global_context_only_when_newer`.

**Original report.** Raised by `situations/10-failed-runs-recovery-loop.md`; **verified**.
`launch_prompts.py:715-717` — `_CONTEXT_RESULT_STATUSES = {"completed",
"approved", "awaiting_review", "revision_requested", "superseded"}` excludes
`failed`. A rerun's agents never see why the previous attempt failed; the
user must hand-encode failure lessons in the direction text. Likely fix:
include `failed` runs with an explicit "failed prior attempt" label in
`_CONTEXT_EVIDENCE_STATUS`. Small, high-value, but changes agent context —
needs a decision on labeling policy.

## 🟡 Issue 14 — P2 full-catalog scaling and no subset/batch operations

Raised by `situations/11-ten-method-p2-catalog.md`. Full-catalog P2 review is
O(n) in method count (~300 KB context per role at 10 methods); the only
alternative is one focused run per method. No batch "retire these, revise
this, confirm the rest" operation. Medium severity; matters only for
method-heavy projects.

## 🟢 Issue 15 — No accidental-run prevention or undo

**Status: WON'T FIX / largely mitigated (July 30, 2026 assessment).** The
method-bound launch picker already renders per-method P2/P3/P4/P5 record
status badges next to every radio (`templates/_tab_phase.html` ~:574-585),
so branch maturity is visible at selection time. A hard confirmation dialog
would add friction to every launch and conflicts with the deliberate
user-in-control design (the system does not second-guess the user). The
residual risk (a slip despite visible badges) is accepted; cleanup of a
mistaken run follows `references/run-cleanup.md`.

**Original report.** Raised by `situations/09-premature-p4-scoping-errors.md`. Launching a phase
for the wrong method creates permanent branch artifacts; cleanup requires
state-file surgery (`references/run-cleanup.md`). Not a bug — the system
deliberately doesn't second-guess the user — but a confirmation hint ("branch
X is already P5-ready") or an undo path would reduce risk. Low priority.

---

## 🟢 Issue 10 — `core/README.md` predates the redesign

Documents only the launch/state/view modules; says nothing about the ~20
records/knowledge/promotion modules that are now the core of the system.

## 🟢 Issue 11 — `situations/` untracked

Five verified scenario analyses plus this tracker belong in version control.
