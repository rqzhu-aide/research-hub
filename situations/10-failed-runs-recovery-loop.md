# Situation 10: Failed Runs and the Recovery Loop

## Scenario

A researcher completes P1 and P2 with one method, `method-alpha` v1. They
begin P3.

**Run 1**: The theorist works, but the process is killed (OOM) mid-round.
The run is left in `running` status with 1 of 3 stages partially complete.

**Run 2**: The researcher relaunches P3. This time the theorist completes
its work, but the data_scientist (stage 2, auditing) finds the theory has a
critical gap and declares the run **Failed**.

**Run 3**: The researcher provides additional direction and relaunches P3.
The theorist addresses the gap. The data_scientist confirms. The research_lead
declares **Complete**. P3 is promoted.

Then P4 begins:

**Run 4**: The data_scientist's code crashes during the experiment. The
process exits with a non-zero code. The run is left in `failed` status.

**Run 5**: P4 reruns. The data_scientist fixes the code. All experiments
succeed. **Complete**. P4 is promoted.

Then P5 assembly runs. During the assembly, the Hermes session disconnects.
The run is in `submitting` status when recovery kicks in.

Total: 9 runs (1 P1, 1 P2, 3 P3, 2 P4, 1 P5 + 1 crash recovery).

## Step-by-step evaluation

### Step 1: P1 → P2

Standard. Disk: ~2.1 MB.

### Step 2: P3 run 1 — OOM crash mid-round

- **System behavior**: The process is killed during stage 1 (theorist). The
  run status is `running`. The round may have partial output (the theorist's
  `.md` file may be partially written or complete but unsubmitted).
- **On next project load**: `_reconcile_promotion_journals_unlocked` runs.
  No promotion journal exists (the run never reached submission). No recovery
  is needed.
- **The run state**: `status: "running"`, `process_pid` points to a dead
  process, `process_identity` doesn't match any live process.
- **Smooth?** ⚠️ The system detects the orphaned run but cannot automatically
  cancel it. The user must explicitly cancel or rerun. The UI shows the run
  as "running" with a stale process indicator.
- **Disk**: Partial round output (~20–40 KB). Running total: ~2.2 MB.

### Step 3: P3 run 2 — Failed

- **System behavior**: The researcher launches a new P3 run (run 2). The old
  run 1 remains in state as `running` (or the researcher cancels it first).
  If not cancelled, the system may have both runs visible.

  **Launch with prior `running` run**: The `start_phase` route checks for
  active runs. If run 1 is still `running`, the launch form requires
  `rerun_from` + `replace_awaiting_review` or the user must cancel first.
  Actually, `running` is in `ACTIVE_RUN_STATUSES` — the system blocks new
  launches until the prior run leaves active status. The user must cancel run
  1 explicitly.

- After cancelling run 1 and launching run 2: the theorist produces a theory.
  The data_scientist audits and finds a critical gap. The research_lead
  declares **Failed**.
- **System behavior**: `seal_output()` with `outcome == "Failed"`. For
  theory phase, only `Complete` triggers sealing. Failed is not
  `ELIGIBLE_CUMULATIVE_OUTCOMES` either. No theory record is promoted.
  `kind = "none"`, `eligible = False`.
- **Smooth?** ✅ The Failed run is recorded with its summary and decision
  record. The summary documents what went wrong. The graph shows P3-alpha
  still `missing`.
- **Disk**: ~1.0 MB (full 3-stage run output). Running total: ~3.2 MB.

### Step 4: P3 run 3 — Complete

- **System behavior**: Launch succeeds (run 2 is `failed`, not active).
  `_trusted_context` includes run 2's summary as historical evidence (it's in
  `_CONTEXT_RESULT_STATUSES` as `failed`... wait — is `failed` in the set?

  Checking: `_CONTEXT_RESULT_STATUSES = {"completed", "approved",
  "awaiting_review", "revision_requested", "superseded"}`. **`failed` is NOT
  in this set.** So the Failed run 2's summary is **excluded** from context.

- **Impact**: The theorist in run 3 does **not** see run 2's Failed summary.
  They don't know what the data_scientist found wrong. The researcher must
  include this context in their user direction text.
- **Smooth?** ⚠️ **Failed runs are invisible to downstream context.** This is
  by design (failed runs may contain misleading information), but it means
  the researcher must manually carry forward lessons from failed runs. The
  system provides no mechanism to reference a failed run's findings in a
  subsequent run's context.
- When P3 run 3 completes with Complete: theory promoted. P3-alpha = gen-1
  `current`.
- **Context per role**: ~100–160 KB (no historical P3 context since prior
  runs were failed/running).
- **Disk**: +1.0 MB. Running total: ~4.2 MB.

### Step 5: P4 run 1 — Failed (code crash)

- **System behavior**: The data_scientist's experiment code crashes. The
  Hermes process exits non-zero. The run status is set to `failed`.
- **Smooth?** ✅ Same as P3 run 2. The failed run is recorded. No empirical
  record promoted.
- **Disk**: ~500 KB (partial outputs). Running total: ~4.7 MB.

### Step 6: P4 run 2 — Complete

- **System behavior**: Launch succeeds. The data_scientist sees no P4
  historical context (run 1 was `failed`, excluded from
  `_CONTEXT_RESULT_STATUSES`). The P3 theory (Complete, gen-1) is included.
  Experiments succeed. **Complete**. Empirical promoted.
- **Smooth?** ⚠️ Same issue as P3: the data_scientist doesn't see run 1's
  crash output. If the crash revealed a useful error (e.g., a numerical edge
  case), that information is lost to the rerun. The researcher must include
  it in user direction.
- **Disk**: +600 KB. Running total: ~5.3 MB.

### Step 7: P5 assembly — crash during submission

- **System behavior**: The P5 assembly run completes. The lead produces the
  manuscript. `seal_output()` begins sealing the manuscript record.
  `promote_output()` begins the atomic promotion.

  The process is killed during the promotion phase (after `seal_output`
  but before `promote_output` completes). The run status is `submitting`.

- **Recovery**: On next project load:
  1. `_reconcile_promotion_journals_unlocked` detects a `prepared` journal
     entry for this run.
  2. `promotion_recovery.py` inspects the transaction state.
  3. If the prepared directory exists and the canonical doesn't: recovery
     completes the promotion (`_replace(prepared, canonical)`).
  4. The manuscript record is promoted. Run status updates.

- **Smooth?** ✅ **The crash recovery works** (assuming the fix from
  ISSUES.md #1 is applied — the `_sync` guard for first-promotion branch
  directories). This is the exact scenario the recovery system was designed
  for. The journal-based approach ensures the promotion is idempotent: if
  recovery runs twice, the second run sees the completed state and does
  nothing.

- **Context per role (P5)**: ~250 KB (all current records frozen).
- **Disk**: +500 KB. Running total: ~5.8 MB.

## Issues identified

### 🟡 Issue A: Failed runs are invisible to subsequent runs

`_CONTEXT_RESULT_STATUSES` excludes `failed`. This means a Failed run's
summary — which may contain valuable diagnostic information (what went wrong,
what the auditor found, what the gap was) — is **not included** in the
context of the next run.

In real research, the most important context for a rerun is often "what
failed last time and why." The system deliberately hides this.

**Root cause**: `launch_prompts.py:715-717`:
```python
_CONTEXT_RESULT_STATUSES = frozenset({
    "completed", "approved", "awaiting_review", "revision_requested", "superseded"
})
```

**Possible fix**: Include `failed` runs in context but label them clearly
as "failed prior attempt — the lead declared this run's theory
incomplete/incorrect. Read the summary to understand what went wrong, then
produce a better result." This would give the rerun's agents the benefit of
learning from the failure.

### 🟡 Issue B: Orphaned running runs block new launches

When P3 run 1 is killed mid-round, it stays in `running` status. The system
blocks new P3 launches until the user explicitly cancels run 1. There is no
automatic detection of dead processes (the `process_identity` check could
detect this, but it requires a page load or status check to trigger).

**Impact**: if the researcher doesn't notice the orphaned run, they'll try to
launch P3 again and get an error. They must navigate to the phase tab, cancel
the run, then relaunch.

### 🟢 Observation: Crash recovery for promotion works well

The journal-based recovery system is the bright spot. The P5 crash during
promotion (Step 7) is handled correctly: the prepared transaction is
detected, the promotion is completed, and the run reaches a consistent state.
This is the system working as designed.

## Space summary

| Component | Size |
|---|---|
| P1 + P2 | ~2.1 MB |
| P3 (3 runs: crashed + failed + complete) | ~2.2 MB |
| P4 (2 runs: failed + complete) | ~1.1 MB |
| P5 (1 run + crash recovery) | ~0.5 MB |
| Control + state + journals | ~1.5 MB |
| **Total** | **~7.4 MB** |

About 30% of the disk usage is from failed/crashed runs that produced no
current records. These cannot be cleaned up without state-file surgery.

## Verdict

⚠️ **The Failed-run invisibility issue is the most consequential gap.** In
real research, failed attempts contain the most valuable learning. The
system's exclusion of `failed` from context means each rerun starts from
scratch — the theorist doesn't know what the previous attempt got wrong.
The researcher must manually encode failure context in their user direction,
which is error-prone.

⚠️ **Orphaned running runs create friction** but are manageable — the user
just needs to cancel before relaunching.

✅ **Promotion crash recovery works correctly**, assuming the `_sync` guard
fix is in place. The journal-based approach is sound and idempotent.
