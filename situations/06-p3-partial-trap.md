# Situation 06: The P3 Partial Trap

## Scenario

A researcher completes P1 and P2, getting two methods: `method-alpha` and
`method-beta`.

They run P3 for alpha. The theorist works through the main theorem, but one
lemma remains unproven — it requires a technical regularity condition the
theorist cannot verify without numerical evidence. The research_lead declares
the outcome **Partial**.

The researcher then runs P4 for alpha (preliminary mode). The data_scientist
implements the method and runs diagnostics. The experiments actually confirm
the regularity condition numerically. Outcome: **Complete**.

Now the researcher has the missing piece for the theory. They rerun P3 for
alpha, aiming for Complete. But the second P3 run produces the same Partial
outcome — the theorist can now see the numerical evidence but still cannot
prove the lemma analytically. It's a genuinely hard problem.

The researcher decides to move forward with the Partial P3 and run P5.

They then switch to `method-beta` and run the full pipeline: P3 (Complete), P4
(Complete), P5 (assembly).

Total: 10 runs (2 P1, 1 P2, 2 P3-alpha, 1 P4-alpha, 1 P5-alpha, 1 P3-beta,
1 P4-beta, 1 P5-beta).

## Step-by-step evaluation

### Step 1: P1 → P2 (2 methods published)

Standard. Context ~10–90 KB per role. Disk: ~2.1 MB.

### Step 2: P3-alpha run 1 — Partial

- **System behavior**: `seal_output()` line 664 checks
  `phase_slug == THEORY_PHASE and outcome == "Complete"`. A Partial outcome
  does **not** match this condition. The theory record is **not sealed** —
  `kind` stays `"none"`, `data` is `None`, `eligible` is `False`.
- **Promotion**: `promote_output()` sees `data is None`, returns `None`. **No
  theory record is promoted.** The P3-alpha branch has no current theory
  package.
- **Smooth?** ✅ The run itself completes fine. The Partial result is visible
  as a finished run with a summary. The lead's report documents the unproven
  lemma and the regularity condition.
- **But**: the graph shows P3-alpha as `missing` — no current record exists.
  The run is history-only.

### Step 3: P4-alpha run 1 — Complete (preliminary)

- **System behavior**: P4 is gated by P2 only, not P3. Launch succeeds despite
  no current P3 theory. The `_trusted_context` function looks for P3 context:
  `_branch_current_run_id()` returns empty (no current theory). The latest
  finalized P3 run *is* included as evidence (it has `final_summary` and is in
  `_CONTEXT_RESULT_STATUSES`), but it's labeled "historical" since it's not
  the canonical current record.
- **Smooth?** ✅ The data_scientist sees the Partial P3 summary as advisory
  context. The experiments run and produce a Complete empirical package.
  Promotion succeeds. P4-alpha empirical record is current.
- **Context per role**: ~140–200 KB per stage.

### Step 4: P3-alpha run 2 — still Partial

- **System behavior**: Same as run 1. The theorist now has P4's numerical
  evidence as frozen context, but the outcome is still Partial. No theory
  record promoted.
- **Graph**: P3-alpha still `missing`. P4-alpha still `current`/`exact_match`.
- **Smooth?** ⚠️ The system is consistent, but the researcher is now stuck:
  two P3 runs, both Partial, neither promoted. The only visible P3 output is
  the latest summary.

### Step 5: Attempt P5-alpha

- **System behavior**: `phase_five_branch_readiness()` checks:
  - P1: present ✅
  - P2: present ✅ (alpha v1)
  - P3: `theory_records.load_current_theory()` returns `None` (no promoted
    theory record). ❌
  - P4: `empirical_records.load_current_package()` returns the record,
    identity matches. ✅
- **Result**: P5 launch is **blocked**. Blocker: "Phase 3 theoretical
  development".
- **Smooth?** ❌ **The Partial P3 trap.** The researcher has a Complete P4,
  a Partial P3 with substantial theoretical work, and cannot assemble a
  manuscript. The system requires P3 to be `Complete` for both promotion and
  Phase 5 readiness. There is no mechanism to proceed with a Partial theory.

### Step 6: P3-beta — Complete, P4-beta — Complete, P5-beta

Standard pipeline for beta. All promoted. P5 assembles.

### Step 7: P5-beta review-revision

P5 assembly completed for beta. Researcher launches P5 review-revision mode.
The paper_reviewer reviews the manuscript. Outcome: Complete. Manuscript
record promoted with generation 2.

## Issues identified

### 🟡 Issue A: P3 Partial is a dead end for Phase 5

**Severity: High.** Phase 3 theory records are only sealed when
`outcome == "Complete"`. A Partial P3 produces no current record, and Phase 5
requires a current P3 theory package. This means:

- Any theoretical contribution with an unresolved lemma cannot proceed to
  manuscript assembly, regardless of how much useful work was done.
- The researcher's only options are: (a) keep rerunning P3 hoping for Complete
  (wasteful if the problem is genuinely hard), or (b) abandon the branch.
- There is no concept of "proceed with acknowledged limitations."

**Root cause**: `phase_records.py:664` — the `elif phase_slug == THEORY_PHASE
and outcome == "Complete"` gate. Partial outcomes are silently dropped from
promotion.

**Possible fix**: Allow Partial P3 to promote a theory record with a visible
limitation marker. Phase 5 could proceed with the Partial theory, and the
manuscript would carry the limitation forward. The follow-up doc (Priority 3)
discusses separating "scientific completion outcome" from "record integrity" —
this is the exact case where that separation matters.

### 🟡 Issue B: Context labeling for non-promoted runs

The Partial P3 summaries are included as "historical advisory evidence" for
downstream P4 runs. This labeling is correct but may confuse the data_scientist
into treating the Partial theory as irrelevant, when it actually contains
substantial results (just not a Complete proof).

## Space summary

| Component | Size |
|---|---|
| P1 (2 runs) + P2 (1 run, 2 methods) | ~2.6 MB |
| P3-alpha (2 runs, both Partial — not promoted) | ~2.0 MB |
| P4-alpha (1 run, Complete) | ~0.8 MB |
| P3-beta (1 run, Complete) | ~1.0 MB |
| P4-beta (1 run, Complete) | ~0.6 MB |
| P5-beta (2 runs: assembly + review) | ~1.0 MB |
| Control + state | ~2.0 MB |
| **Total** | **~10.0 MB** |

## Verdict

⚠️ **The P3 Partial trap is the most consequential design gap for real
research workflows.** Mathematical research routinely produces Partial results
— lemmas that resist proof, bounds that are conjectural, conditions that are
verified numerically but not analytically. The current system treats these as
unpromotable dead ends. A researcher who has done substantial theoretical work
but cannot reach Complete is entirely blocked from manuscript assembly.
