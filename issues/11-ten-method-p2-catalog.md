# Situation 11: The Ten-Method P2 Catalog

## Scenario

A researcher completes P1 (broad survey of interacting particle systems) and
P2 produces **ten candidate methods**. This is a brainstorming-heavy P2 with
many ideas generated.

The researcher develops **three** of these methods (alpha, beta, gamma) to
varying degrees:
- Alpha: P3 Complete, P4 Complete, P5 assembly + review. Full pipeline.
- Beta: P3 Complete, P4 Partial (insufficient compute). Incomplete.
- Gamma: P3 only (Complete). No P4 yet.

The remaining **seven** methods are undeveloped (P2 only).

Then a new paper appears. The researcher reruns P1. The new paper changes
the landscape: it subsumes two of the seven undeveloped methods and provides
a new benchmark relevant to alpha.

The researcher reruns P2 (full catalog) to review all ten methods against
the new literature. Three methods are marked as subsumed (effectively dead).
One method's definition is revised (advances to v2). The rest are
`reviewed_no_change`.

The researcher then reruns P4 for alpha (new benchmark) and P3+P4 for the
revised method.

Total: 17 runs (2 P1, 2 P2, 4 P3, 4 P4, 2 P5, 3 retirements).

## Step-by-step evaluation

### Step 1: P1 → P2 (10 methods)

- **System behavior**: P2 publishes 10 method files with a registry of 10
  entries. Each method has a stable_id, version v1, and definition_sha256.
- **Context per role (P2, 2 rounds, parallel)**:
  - Round 1: souls + playbook + P1 summary (~25 KB) + reference library
    (~90 KB). ≈ **120–140 KB** per role. The lead must assign research
    questions covering 10 candidate methods — a heavy cognitive load.
  - Round 2: + 3 role reports. Each report evaluates multiple methods.
    ≈ **200–250 KB** per role.
- **Disk**: P1 ~500 KB + P2 ~800 KB (10 method files + larger round
  outputs). Running total: ~2.5 MB.

### Step 2: Alpha full pipeline

- P3-alpha Complete, P4-alpha Complete, P5-alpha assembly + review.
- **Smooth?** ✅ Standard.
- **Disk**: +3.0 MB. Running total: ~5.5 MB.

### Step 3: Beta partial (P3 Complete, P4 Partial), gamma partial (P3 Complete)

- **Smooth?** ✅ Both work. Beta's Partial P4 is promoted. Gamma has no P4.
- **Disk**: +2.5 MB. Running total: ~8.0 MB.

### Step 4: P1 rerun — new paper

- **System behavior**: Reference delta adds 1 new card, updates synthesis.
  P1 generation advances.
- **Graph**: P1→P2 edge becomes `review_required` for **all 10 methods**.
- **Context per role (P1 rerun)**: +18 reference cards as context + prior
  summary. ≈ **100–130 KB**.
- **Disk**: +500 KB. Running total: ~8.5 MB.

### Step 5: P2 full-catalog rerun — review all 10 methods

- **System behavior**: The lead reviews all 10 methods against the new
  literature. This is a substantial task. The staged catalog includes all 10
  entries with updated provenance.
- **Outcomes**:
  - Alpha: `reviewed_no_change` (definition unchanged, new benchmark noted).
  - Beta: `reviewed_no_change`.
  - Gamma: `reviewed_no_change`.
  - Methods δ, ε: `status: "retired"` (subsumed by new paper).
  - Method ζ: `definition_revised` → v2 (new definition digest).
  - Methods η, θ, ι, κ: `reviewed_no_change`.
- **Smooth?** ⚠️ The full-catalog review is expensive. Every method gets
  reviewed, even the 7 undeveloped ones. The agents must evaluate each
  method's relevance to the new paper, even for methods nobody plans to
  develop.
- **Context per role (P2 full-catalog, 2 rounds)**:
  - Round 1: 10 method definitions (~20 KB) + P1 new summary + reference
    library. ≈ **150–180 KB** per role.
  - Round 2: + 3 role reports (each evaluating 10 methods, likely ~40–50 KB
    each). ≈ **250–300 KB** per role. **This approaches the heavy end of
    context.**
- **Graph after P2 promotion**:
  - Alpha, beta, gamma: P1→P2 edge returns to `exact_match` (reviewed_no_change
    with updated literature basis).
  - δ, ε: retired. Excluded from graph.
  - ζ: P2→P3 and P2→P4 edges don't exist yet (no runs). The method is v2.
  - η, θ, ι, κ: `exact_match`.
- **Disk**: +800 KB. Running total: ~9.3 MB.

### Step 6: P4-alpha rerun — new benchmark

- **System behavior**: P4 launches with alpha v1 (definition unchanged). The
  frozen context includes updated P1 synthesis + P3-alpha theory. The
  data_scientist adds the new benchmark. Complete. Empirical promoted gen-2.
- **Graph**: P4-alpha gen-2 `current`. Sibling edge P3→P4 becomes
  `review_required` (P3 saw P4 gen-1, now P4 is gen-2).
- **Disk**: +600 KB. Running total: ~9.9 MB.

### Step 7: P3-zeta v2 — Complete, P4-zeta v2 — Complete

- **System behavior**: Fresh branch for ζ v2. P3 Complete, P4 Complete.
  Standard pipeline.
- **Context per role**: ~100–200 KB (standard, fresh branch).
- **Disk**: +1.6 MB. Running total: ~11.5 MB.

### Step 8: P5-zeta assembly + review

- **Smooth?** ✅ Standard. Manuscript assembled for ζ v2.
- **Disk**: +500 KB. Running total: ~12.0 MB.

## Issues identified

### 🟡 Issue A: Full-catalog P2 review scales linearly with method count

With 10 methods, the P2 rerun is a heavy operation. Every role must evaluate
every method, even undeveloped ones. The round-2 context reaches ~250–300 KB
per role — approaching the limits of what agents can usefully process.

The `focused_method` scope exists for reviewing a single method, but there's
no middle ground: you can review one method or all methods. If three methods
need review (alpha needs the benchmark, ζ needs revision, and gamma needs a
freshness check), the user must either run three separate focused P2 runs or
one expensive full-catalog run.

### 🟡 Issue B: Retired methods in full-catalog P2 still consume review effort

When the P2 full-catalog rerun runs, the agents evaluate all 10 methods,
including the 7 undeveloped ones. The two subsumed methods (δ, ε) are reviewed
and then retired — but the review effort was spent. The system can't know in
advance which methods will be retired; it discovers this during the review.

### 🟡 Issue C: No batch operations for multi-method workflows

The researcher developed three methods to varying degrees, then decided to
retire two and revise one. Each operation (retire, revise, review) is a
separate P2 run or manual catalog edit. There's no batch "retire these two,
revise this one, confirm the rest" operation.

### 🟡 Issue D: P5-alpha from stale P3 + fresh P4

**Correction (2026-07-30): this issue is withdrawn.** The claim that P5
allows the launch was wrong — `phase_five_branch_readiness` aggregates the
sibling counterpart edges into the P3/P4 graph nodes and the launch path
hard-blocks on any non-`exact_match` node (`launch_manifest.py:1719-1768`,
`launch_run.py:851-858`; covered by
`test_phase_five_readiness_rejects_yellow_p3_or_p4_alignment`). After P4-alpha
gen-2, P5-alpha is **blocked** until P3 is rerun (or the fragment content
converges). The misalignment is enforced, not just flagged.

~~After P4-alpha gen-2 (Step 6), P3-alpha is still gen-1. The sibling edge shows
`review_required`. If the researcher runs P5-alpha at this point (without
rerunning P3), the manuscript is assembled from P3 gen-1 + P4 gen-2 — a theory
that predates the latest experiments. The system allows this launch (method
identity matches), but the graph flags the misalignment.~~

## Space summary

| Component | Size |
|---|---|
| P1 (2 runs) | ~1.0 MB |
| P2 (2 runs: 10 methods + full catalog review) | ~1.6 MB |
| Alpha (P3+P4×2+P5×2) | ~3.5 MB |
| Beta (P3+P4 Partial) | ~1.5 MB |
| Gamma (P3 only) | ~1.0 MB |
| Zeta (P3+P4+P5×2) | ~3.0 MB |
| Retired δ, ε + undeveloped η,θ,ι,κ | ~0.1 MB |
| Control + state | ~2.5 MB |
| **Total** | **~14.2 MB** |

~5 MB of this is from methods/branches that are retired or undeveloped but
cannot be cleaned up.

## Context size summary (worst case: P2 full-catalog round 2)

| Role | Context source | Size |
|---|---|---|
| Souls (×3) | Team + role definitions | ~6 KB |
| Phase playbook | Full P2 lead/role instructions | ~5 KB |
| P1 summary | Literature review HTML | ~25 KB |
| Reference library | 19 cards × ~2 KB | ~38 KB |
| Method catalog | 10 definitions × ~2 KB | ~20 KB |
| Round-1 reports (×3) | Each evaluates 10 methods | ~40–50 KB each |
| **Total per role** | | **~250–300 KB** |

This is within the 4 MB task-brief limit but at the upper end of what agents
can process effectively in a single round.

## Verdict

⚠️ **The ten-method catalog exposes scaling friction in P2.** The
full-catalog review is O(n) in method count, with no way to review a subset
short of running multiple focused P2 runs. At 10 methods, the context per
role reaches ~300 KB — manageable but heavy.

⚠️ **Retired and undeveloped methods are permanent storage dead weight** with
no cleanup path.

⚠️ **Multi-method workflows lack batch operations.** Retiring, revising, and
confirming methods each require separate operations.

✅ **The branch isolation works at scale.** Despite 10 methods and multiple
development stages, each method's theory/experiments are cleanly separated.
No cross-contamination occurs.
