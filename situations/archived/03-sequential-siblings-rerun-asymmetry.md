# Situation 03: Sequential Siblings and Rerun Asymmetry

## Hypothesis

A researcher completes P1 + P2 with one method, `method-alpha` v1.

They run P3 (Theory) for alpha v1 — Complete. Then they run P4 (Experiments)
for alpha v1 — Complete. P4 saw P3's theory at launch, so its stored
counterpart basis reflects the current P3.

Then P4 reveals something that changes the theoretical picture. The researcher
reruns P3 for alpha v1 (same method version, new theory generation). P3 is now
generation 2, but P4 is still generation 1 — its stored counterpart basis
points to the old P3.

Can the researcher run P5 now? What does the graph show?

Then the researcher reruns P4 to catch up. But P3 was generation 2 and now
P4 becomes generation 2 as well. What if they then rerun P3 again?

## Important constraint

Research Hub runs **one phase at a time per project**. A project-level lock
and `active_run` state prevent concurrent launches. P3 and P4 are siblings
in the dependency graph (neither gates the other), but they execute
sequentially in whatever order the user chooses.

## Steps and evaluation

### Step 1: P1 + P2 complete, alpha v1 published

Standard. Disk: ~2.1 MB.

### Step 2: P3 for alpha v1 — Complete (generation 1)

- **Graph**: P3-alpha = `current`/`exact_match` v1. P4-alpha = `missing`.
- **System behavior**: Theory promoted to
  `branches/method-alpha/evaluations/`. Theory record stores
  `counterpart_basis` = absent (P4 didn't exist at launch).
- **Smooth?** ✅ Yes.
- **Context per role (3 sequential stages)**:
  - Stage 1 — theorist: souls + playbook + P1 summary (~25 KB) + P2 method
    (~2 KB) + current_records (P1 + P2 ≈ 40 KB frozen). ≈ **100–120 KB**.
  - Stage 2 — data_scientist (audit): + theorist's stage-1 report (~45 KB).
    ≈ **120–140 KB**.
  - Stage 3 — research_lead: + both prior reports. ≈ **140–160 KB**.
- **Disk**: ~1.0 MB. Running total: **~3.1 MB**.

### Step 3: P4 for alpha v1 — Complete (generation 1)

- **Graph**: P4-alpha = `current`/`exact_match` v1. Sibling edge P4→P3:
  P4's stored counterpart basis matches current P3 (both v1 gen-1) →
  `exact_match`. Sibling edge P3→P4: P3's stored counterpart basis was
  `absent` at launch (P4 didn't exist). Current P4 is now `present`. →
  `review_required` (P3 didn't account for P4 when it ran).
- **System behavior**: Empirical promoted. `counterpart_basis` stores P3's
  theory basis as seen at launch (v1, present).
- **Smooth?** ✅ Yes. The asymmetry is by design: P4 saw P3 (good), but P3
  didn't see P4 (expected, since P4 didn't exist yet). The graph shows this
  honestly.
- **Context per role (3 sequential stages)**:
  - Stage 1 — data_scientist: souls + playbook + P1 + P2 method + **P3 theory
    summary** (~40 KB) + P3 theory record + current_records (P1 + P2 + P3
    ≈ 80 KB frozen). ≈ **140–160 KB**.
  - Stage 2 — theorist (audit): + DS stage-1 report (~30 KB). ≈ **160–180 KB**.
  - Stage 3 — research_lead: + both. ≈ **180–200 KB**.
- **Disk**: ~600 KB. Running total: **~3.7 MB**.

### Step 4: P3 rerun — new theory generation 2 (same method v1)

The P4 experiments revealed numerical instabilities that change the theoretical
bounds. The researcher reruns P3 without changing the method definition.

- **Graph at launch**: P3 = gen-1 v1 `current`. P4 = gen-1 v1 `current`.
  Method identity is still v1 for both. The P3 rerun freezes both as
  `current_records`.
- **Graph after completion**: P3-alpha = gen-2 v1 `current`/`exact_match`.
  Sibling edge P3→P4: P3's new stored counterpart basis matches current P4
  (v1 gen-1) → `exact_match`. Sibling edge P4→P3: P4's stored counterpart
  basis still points to P3 gen-1. Current P3 is now gen-2. →
  `review_required` (P4's theory basis is outdated).
- **System behavior**: Theory promoted as generation 2. Gen-1 backup retained.
  The method identity hasn't changed (still v1), so the P2→P3 edge stays
  `exact_match`.
- **Smooth?** ✅ The system correctly detects the asymmetry. P4 now has a
  stale sibling basis. **But the user cannot clear this without rerunning
  P4** — there is no "acknowledge" mechanism to say "the new theory doesn't
  change my experiments."
- **Context per role (P3 rerun, 3 stages)**:
  - Stage 1 — theorist: previous inputs + P4 v1 summary (~20 KB) + P4 evidence
    index + prior P3 gen-1 summary (~40 KB, labeled historical). ≈ **150–180
    KB**.
  - Stage 2 — DS audit: + theorist report (~45 KB). ≈ **180–210 KB**.
  - Stage 3 — lead: + both. ≈ **200–230 KB**.
- **Disk**: ~1.0 MB. Running total: **~4.7 MB**.

### Step 5: Attempt P5 at this point

- **Graph check**: P3 = gen-2 v1 `current`. P4 = gen-1 v1 `current`. Method
  identity matches (both v1). But sibling edge P4→P3 = `review_required`.
- **System behavior**: `current_upstream_basis()` checks method identity match
  (passes: both v1) and record existence (passes: both present). It does
  **not** check sibling edge alignment for Phase 5 readiness. The
  `phase5_projection` validates frozen identities (method version + sha256
  match).
- **Smooth?** ⚠️ The launch **succeeds**, but the manuscript is assembled
  from a P4 whose stored counterpart theory basis is outdated. The graph will
  show the manuscript node with a `review_required` edge from P4. **This is a
  silent quality risk** — the user must notice the warning in the UI. There is
  no hard block.

### Step 6: P4 rerun — catch up to P3 gen-2 (same method v1)

- **Graph at launch**: P3 = gen-2 v1. P4 = gen-1 v1. Both current. Method v1.
  The P4 rerun sees P3 gen-2 theory.
- **Graph after completion**: P4-alpha = gen-2 v1 `current`. Sibling edge
  P4→P3 now matches (both gen-2, P4 saw P3 gen-2). Sibling edge P3→P4: P3's
  stored counterpart basis pointed to P4 gen-1. Current P4 is now gen-2. →
  `review_required` (P3 didn't see the new P4).
- **Smooth?** ✅ The system works, but reveals the **ping-pong problem**:
  each sibling rerun makes the other one stale. This is the exact issue the
  follow-up doc (Priority 3) describes. The semantic edge comparison is based
  on knowledge fragments (not raw file bytes), which prevents formatting-only
  ping-pong. But a genuine content change in either sibling will always make
  the other yellow until it is rerun.
- **Context per role (P4 rerun)**:
  - Stage 1 — DS: P3 gen-2 theory summary (~40 KB) + prior P4 gen-1 summary
    (~20 KB, historical) + evidence index. ≈ **160–190 KB**.
  - Other stages proportionally. ≈ 190–220 KB.
- **Disk**: ~600 KB. Running total: **~5.3 MB**.

### Step 7: P3 rerun again — generation 3

If the researcher reruns P3 again to catch up to P4 gen-2, the cycle
repeats: P3 gen-3 makes P4 gen-2 stale again.

**Does this converge?** Only if the content change in each rerun is decreasing
(a convergent refinement process). The semantic fragment comparison means that
if P3 gen-3's theory fragment is identical to P3 gen-2's, then the P4→P3 edge
stays `exact_match` even though the generation changed — because the semantic
content didn't change. **This is the key convergence mechanism.**

In practice: if the theorist's second rerun produces the same theoretical
conclusions (just reorganized or clarified), the knowledge fragment digest
stays the same, and the system detects no semantic change. The ping-pong stops.

## The ping-pong convergence mechanism

| P3 gen | P4 gen | P3→P4 edge | P4→P3 edge | Converged? |
|---|---|---|---|---|
| 1 | — | exact_match (P3 saw no P4; no P4 exists — both bases absent, `semantic_alignment` maps absent+absent to `exact_match`) | not_available (P4 missing) | — |
| 1 | 1 | review_required (P3 didn't see P4) | exact_match | No |
| 2 | 1 | exact_match (P3 saw P4 gen-1) | review_required (P4 saw P3 gen-1) | No |
| 2 | 2 | review_required (P3 saw P4 gen-1) | exact_match (P4 saw P3 gen-2) | No |
| 3 | 2 | exact_match (P3 saw P4 gen-2) | review_required (P4 saw P3 gen-2) | No |
| 3 | 3 | review_required | exact_match | No |
| ... | ... | ping-pong | ping-pong | No |
| N (same fragment as N-1) | M | exact_match (no semantic change) | depends | Maybe |

**Convergence requires**: the knowledge fragment of the rerun to be identical
to the prior one. If the theorist's conclusions didn't change (only the
exposition did), the fragment digest is the same, and the edge stays
`exact_match`.

**Anti-convergence scenario**: if each rerun genuinely changes the theory (new
bounds, corrected proof), the fragments differ every time, and the ping-pong
never converges. The user would need to accept the yellow state and proceed
anyway (which the system allows for P5, with a warning).

## Space summary

| Component | Size |
|---|---|
| P1 + P2 | ~2.1 MB |
| P3 gen-1 | ~1.0 MB |
| P4 gen-1 | ~0.6 MB |
| P3 gen-2 (rerun) | ~1.0 MB |
| P4 gen-2 (rerun) | ~0.6 MB |
| P5 (1 run, possible stale P4) | ~0.5 MB |
| Control + backups | ~1.2 MB |
| **Total** | **~7.0 MB** |

## Verdict

✅ **The sequential sibling workflow is correct.** P4 sees P3's results when
it launches after P3. The graph honestly tracks which sibling saw which
version.

⚠️ **The ping-pong problem is real but bounded.** Each rerun of one sibling
makes the other's counterpart basis stale. The semantic-fragment comparison
prevents formatting-only ping-pong, but genuine content changes will
propagate back and forth. The system provides no "reviewed, my result still
holds" disposition to break the cycle — the user must either rerun or accept
the yellow edge.

⚠️ **P5 can launch with a stale sibling edge.** The manuscript is assembled
from whatever P3 and P4 are current, even if they haven't seen each other's
latest work. The graph flags this, but there is no hard block. The user must
notice and judge the significance.
