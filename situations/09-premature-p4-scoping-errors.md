# Situation 09: Premature P4 with Scoping Errors

## Scenario

A researcher completes P1 and P2 with two methods: `method-alpha` and
`method-beta`.

They run P3 for alpha — Complete. Then they run P4 for alpha in
**comprehensive mode** (instead of the default preliminary). The
data_scientist designs an ambitious experiment suite: 6 experiments including
high-dimensional stress tests.

Three of the six experiments succeed. Two produce inconclusive results due to
insufficient compute budget. One experiment reveals a subtle numerical
instability that the theory didn't predict.

The research_lead declares P4 **Partial** — the successful experiments
validate the method, but the incomplete ones leave gaps.

The researcher then reruns P4 in **preliminary mode** to get a focused,
Complete result for the core experiments. This succeeds.

Then the researcher accidentally launches P3 for `method-beta` instead of
alpha (wrong method selected in the launch form). P3-beta runs and produces a
Complete theory. The researcher notices the mistake only after the run
finishes.

They then run P4-beta to at least have the empirical work for beta, and then
P5-beta.

Finally, they return to alpha for P5 assembly.

Total: 11 runs (1 P1, 1 P2, 2 P3, 3 P4, 1 P5 + 1 accidental P3-beta +
P4-beta + P5-beta).

## Step-by-step evaluation

### Step 1: P1 → P2 (2 methods)

Standard. Disk: ~2.5 MB.

### Step 2: P3-alpha — Complete

Standard. Theory promoted. Disk: ~3.5 MB.

### Step 3: P4-alpha run 1 — comprehensive mode, Partial

- **System behavior**: P4 launches with `run_mode: "comprehensive"`. The
  manifest records this scope. The data_scientist runs all 6 experiments.
  Three succeed, two are inconclusive, one reveals instability.
- **Sealing**: `seal_output()` with `outcome == "Partial"` — for empirical
  phase, `eligible = outcome in {"Complete", "Partial"}` → True. The package
  is sealed and promoted. Evidence index records 6 entries:
  - 3 `resolved` (success)
  - 2 `unresolved` (inconclusive)
  - 1 `outdated` (instability invalidates the result)
- **Graph**: P4-alpha = `current`, `scientific_outcome: "Partial"`. The node
  shows `outdated_count: 1`, `unresolved_count: 2`, `current_evidence_count:
  3`.
- **Smooth?** ✅ The Partial P4 promotion works correctly. The evidence
  dispositions are tracked.
- **Context per role (P4 comprehensive, 3 stages)**:
  - Stage 1 — DS: P3 theory (~40 KB) + comprehensive scope directive + P2
    method + current records. ≈ **150–180 KB**.
  - Other stages proportionally. ≈ 180–230 KB.
- **Disk**: +800 KB (more experiments = larger outputs). Running total:
  ~4.3 MB.

### Step 4: P4-alpha run 2 — preliminary mode, Complete

- **System behavior**: P4 reruns with `run_mode: "preliminary"`. The
  data_scientist focuses on the 3 core experiments. All succeed. Outcome:
  Complete.
- **Promotion**: `promote_staged_package()` **replaces** the Partial empirical
  package. The Partial package (6 experiments, 3 resolved) becomes a backup.
  The new Complete package (3 core experiments, all resolved) becomes current.
- **Smooth?** ⚠️ **The replacement model loses evidence.** The 3 successful
  comprehensive experiments that overlapped with the preliminary scope are
  re-derived. But the 2 inconclusive experiments and the instability finding
  from the comprehensive run are **no longer current** — they exist only in
  the backup. The evidence index of the new Complete package doesn't include
  them.
- **Graph**: P4-alpha = `current`, `scientific_outcome: "Complete"`.
  `outdated_count: 0`, `unresolved_count: 0`, `current_evidence_count: 3`.
  The instability finding is gone from the current record.
- **Context per role**: ~140–200 KB.
- **Disk**: +600 KB. Running total: ~4.9 MB.

### Step 5: Accidental P3-beta — Complete

- **System behavior**: The researcher selects `method-beta` in the P3 launch
  form instead of alpha. The launch succeeds (beta is a valid method in the
  catalog). The theorist develops beta's theory. Outcome: Complete.
- **Smooth?** ✅ Technically smooth — the system has no concept of "wrong
  method." Beta is a valid branch. But:
  - The accidental run consumed compute resources.
  - Beta now has a current theory record.
  - The researcher must decide: keep it or retire beta.
- **Disk**: +1.0 MB. Running total: ~5.9 MB.

### Step 6: Researcher decides to keep beta, runs P4-beta

- **System behavior**: P4-beta runs. Since P3-beta exists and is current,
  P4-beta sees the theory as context. Outcome: Complete.
- **Disk**: +600 KB. Running total: ~6.5 MB.

### Step 7: P5-beta assembly

- **System behavior**: `phase_five_branch_readiness()` checks beta: P1 ✅,
  P2 ✅, P3 ✅ (Complete), P4 ✅ (Complete). Launch succeeds.
- **Disk**: +500 KB. Running total: ~7.0 MB.

### Step 8: P5-alpha assembly

- **System behavior**: `phase_five_branch_readiness()` checks alpha: P1 ✅,
  P2 ✅, P3 ✅ (Complete, gen-1), P4 ✅ (Complete, gen-2, preliminary).
  Launch succeeds.
- **But**: P4-alpha gen-2 (preliminary) replaced P4-alpha gen-1
  (comprehensive, Partial). The manuscript is assembled from the narrower
  preliminary evidence. The comprehensive run's instability finding is not
  in the current record. If the paper_reviewer asks about edge cases, the
  researcher must manually consult the backup evidence.
- **Disk**: +500 KB. Running total: ~7.5 MB.

## Issues identified

### 🟡 Issue A: P4 replacement discards prior evidence findings

The most significant issue. When P4-alpha run 2 (preliminary, Complete)
replaces run 1 (comprehensive, Partial), the evidence index is **entirely
replaced**. The instability finding from the comprehensive run exists only in
the backup directory, not in the current record. The manuscript assembled
from the preliminary evidence has no knowledge of this finding.

This is the "P4 replacement, not accumulation" design gap (ISSUES.md #7,
follow-up doc Priority 3). In a real research workflow, the researcher would
want to:
1. Keep the 3 successful core experiments as the primary evidence.
2. Carry forward the 2 inconclusive experiments as acknowledged limitations.
3. Flag the instability finding as a known issue in the manuscript.

The current system can only do (1).

### 🟡 Issue B: No accidental-run prevention

The system cannot prevent the user from launching P3 for the wrong method.
The launch form shows all active methods. If the user selects beta instead of
alpha, the system proceeds without warning. The accidental P3-beta run is
valid and creates a permanent branch record.

This is not a bug — it's a human factors issue. A "you already have a P5-ready
alpha branch; are you sure you want to develop beta?" prompt might help, but
the system intentionally doesn't second-guess the user.

### 🟡 Issue C: Run mode (preliminary vs comprehensive) doesn't affect promotion

The manifest records `run_mode: "comprehensive"` or `"preliminary"`, but the
promotion system treats both the same way — the latest Complete/Partial
result replaces the prior current record. A comprehensive Complete run and a
preliminary Complete run produce the same promotion. The scope information is
in the manifest but doesn't affect the evidence index structure or the graph.

## Space summary

| Component | Size |
|---|---|
| P1 + P2 (2 methods) | ~2.5 MB |
| P3-alpha (1 run) | ~1.0 MB |
| P4-alpha (2 runs: comprehensive + preliminary) | ~1.4 MB |
| P3-beta (accidental, 1 run) | ~1.0 MB |
| P4-beta (1 run) | ~0.6 MB |
| P5-alpha + P5-beta | ~1.0 MB |
| Control + state + backups | ~2.0 MB |
| **Total** | **~9.5 MB** |

## Verdict

⚠️ **The P4 replacement model is the primary friction point.** Real
experimental research is iterative — preliminary runs reveal issues,
comprehensive runs explore edge cases, and the researcher wants to combine
evidence across runs. The current system's all-or-nothing replacement means
valuable findings from superseded runs (the instability discovery) are
invisible to downstream phases.

⚠️ **Accidental runs create permanent artifacts** that cannot be undone
without state-file surgery (the cleanup procedure from the skill's
`references/run-cleanup.md`). A confirmation step or undo mechanism would
reduce this risk.
