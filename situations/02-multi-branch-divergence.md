# Situation 02: Multi-Branch Divergence and Cross-Contamination

## Hypothesis

A researcher completes P1 and P2, getting **three methods**: `method-alpha`,
`method-beta`, `method-gamma`.

They develop alpha fully (P3 + P4 complete, v1). Then they develop beta
partially (P3 complete v1, P4 Partial — some experiments failed). Gamma is
never developed.

Then the researcher reruns P1 (new literature found). This changes the
reference library and synthesis but does not change any method definition.

Now the researcher wants to run P5 for alpha. But they also want to run P4
for beta to complete the failed experiments.

## Steps and evaluation

### Step 1: Initial state — P1 done, P2 publishes 3 methods

Same as Situation 01, Step 1. Three methods published.

- **Context per role**: P1 ~8–50 KB/round. P2 ~35–80 KB/round.
- **Disk**: ~2.1 MB.

### Step 2: P3 + P4 for alpha v1 — both Complete

- **Graph**: alpha branch has P3 `current` v1, P4 `current` v1. Sibling edge
  `exact_match`.
- **Smooth?** ✅ Yes.
- **Context per role** (each of P3, P4): 100–200 KB per stage as in Situation 01.
- **Disk**: Adds ~1.6 MB. Running total: **~3.7 MB**.

### Step 3: P3 for beta v1 — Complete. P4 for beta v1 — Partial.

- **Graph**: beta branch has P3 `current` v1, P4 `current` v1 but with
  `scientific_outcome: "Partial"`. The P4 node carries `outdated_count` and
  `unresolved_count` for the failed experiments.
- **System behavior**: A Partial outcome is **eligible for promotion**
  (`ELIGIBLE_CUMULATIVE_OUTCOMES = {"Complete", "Partial"}`). The empirical
  record is promoted as current. The evidence index records failed/unresolved
  entries with their dispositions.
- **Smooth?** ✅ Yes. The Partial result is visible and carries forward.
- **Context per role**: Same range as alpha, but the P4 data_scientist sees
  beta's P3 theory. ≈ 100–200 KB per stage.
- **Disk**: Adds ~1.6 MB. Running total: **~5.3 MB**.

### Step 4: P1 rerun — new literature found

- **Graph**: P1 node digest changes (new synthesis + new reference cards). The
  edge P1→P2 flips to `review_required` for **all three methods** (alpha, beta,
  gamma), because the Phase 2 literature basis no longer matches.
- **System behavior**: `literature_records.promote_reference_delta()` applies
  the new delta. The P1 generation advances. The P2 method provenance records
  `phase_two_literature_basis` — since this was frozen at P2 launch time, it
  now differs from the current P1 basis.
- **Smooth?** ⚠️ **This is a critical design gap.** The P1→P2 edge makes all
  methods yellow. But:
  - **Gamma** has no P3/P4 — yellow on P2 is expected.
  - **Alpha** has complete P3+P4. The new literature doesn't change alpha's
    mathematical definition (no P2 rerun occurred). But the graph says P2 is
    yellow for alpha, which transitively suggests P3/P4 might need review.
  - **The system has no direct P1→P3 or P1→P4 edge.** So P3/P4 for alpha and
    beta remain `exact_match` (green) even though the research landscape
    shifted. The follow-up doc (Priority 2) calls this out explicitly.
  - **There is no "acknowledge" mechanism.** The user cannot say "I reviewed
    the new literature, it doesn't affect alpha's theory" without rerunning
    P2.
- **Context per role (P1 rerun, 2 rounds)**:
  - Round 1: souls + playbook + **current reference library** (~90 KB
    reference cards + ~7 KB summary) + prior P1 summary (~25 KB). ≈
    **130–150 KB** per role.
  - Round 2: + 3 role round-1 reports. ≈ **160–200 KB** per role.
- **Disk**: P1 second run adds ~500 KB. Running total: **~5.8 MB**.

### Step 5: Attempt P5 for alpha

- **Graph check**: `phase5_projection` validates all upstream identities. P3
  alpha = v1 `current`. P4 alpha = v1 `current`. P2 alpha = v1 `current`
  (definition unchanged). P1 = new generation. The manuscript upstream basis
  includes P1 synthesis digest and P1 collection digest. Since P1 changed, the
  manuscript edges P1→P5 will be `review_required`.
- **System behavior**: `current_upstream_basis()` checks that P1, P2, P3, P4
  all exist and match method identity. P2 identity for alpha is still v1
  (unchanged), so this passes. The Phase 5 launch form also submits
  `branch_graph_version` (a sha256 of the branch graph as rendered), but this
  is an **optimistic-concurrency check, not a yellow-edge acknowledgement**:
  `launch_run` rejects the launch only when the graph *changed between page
  render and submit* ("prerequisites changed after this page was shown —
  reload and review again"). A graph containing `review_required` edges
  passes as long as it is unchanged since the page was shown.
- **Smooth?** ⚠️ Partially. The system **allows** the launch (Phase 5 doesn't
  hard-block on yellow edges), and the rendered page shows the yellow P1 edge,
  so an attentive user is warned. The manuscript will be assembled, and the
  P1→P5 edge in the resulting graph will show `review_required`, meaning the
  manuscript may need another revision pass after the user reviews the new
  literature's impact.
- **Context per role (P5)**: All current records for alpha:
  - P1 synthesis (~7 KB) + P1 reference index (~5 KB)
  - P2 method alpha (~2 KB)
  - P3 theory manuscript (~up to 20 MB limit, realistically ~50–100 KB)
  - P4 empirical synthesis (~4 KB) + evidence index (~4 KB) + knowledge
    fragment (~4 KB)
  - + souls, playbooks, context text.
  ≈ **200–300 KB** per role.
- **Disk**: Adds ~500 KB. Running total: **~6.3 MB**.

### Step 6: P4 rerun for beta — complete the experiments

- **Graph**: At launch, the frozen context includes P3 beta v1 (Complete),
  prior P4 beta v1 (Partial, labeled historical). The new P4 run replaces the
  Partial empirical record with a Complete one.
- **System behavior**: `empirical_records.promote_staged_package()` atomically
  replaces the Partial package. The Partial backup is retained. Evidence index
  generation advances to 2.
- **Smooth?** ⚠️ **Replacement model limitation.** The new P4 run must redo
  **all** experiments, not just the failed ones. The prior Partial evidence
  (successful experiments) is backed up but no longer "current." The data
  scientist sees the prior Partial summary as labeled historical context, but
  cannot simply "add" to it. They must re-derive everything.
- **Context per role (P4 beta rerun, 3 stages)**:
  - Stage 1 — DS: P3 beta theory (~40 KB) + prior P4 Partial summary (~20 KB,
    labeled historical) + P2 beta method (~2 KB). ≈ **120–150 KB**.
  - Other stages: + reports. ≈ 150–200 KB.
- **Disk**: Adds ~600 KB. Running total: **~6.9 MB**.

## Space summary

| Component | Size |
|---|---|
| P1 (2 runs) | ~1.0 MB |
| P2 (1 run, 3 methods) | ~0.5 MB |
| P3 alpha v1 + P4 alpha v1 | ~1.6 MB |
| P3 beta v1 + P4 beta v1 (Partial) | ~1.6 MB |
| P4 beta rerun (Complete) | ~0.6 MB |
| P5 alpha v1 | ~0.5 MB |
| Control + backups | ~1.5 MB |
| **Total** | **~7.3 MB** |

## Verdict

⚠️ **Two design gaps surface here:**

1. **P1→P3/P4 silent gap**: new literature makes P2 yellow for all methods, but
   P3/P4 stay green. The user may not realize the research landscape has shifted
   under their existing theory/experiments. The system can only clear the P2
   yellow by rerunning Phase 2 — there is no "reviewed, no rerun needed"
   disposition.

2. **P4 replacement, not accumulation**: completing failed experiments requires
   redoing all experiments. No incremental evidence model exists.
