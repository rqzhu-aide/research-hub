# Situation 08: Literature Refresh Mid-Pipeline

## Scenario

A researcher completes P1 and P2 with one method, `method-alpha` v1. They run
P3 (Complete) and are about to run P4 when a relevant new paper appears on
arXiv. They rerun P1 to incorporate the new reference.

The new paper changes the novelty framing but does not affect alpha's
mathematical definition. The researcher runs P2 (focused on alpha) to record
the review. P2's outcome: the method definition is unchanged
(`reviewed_no_change`).

Then P4 runs, P5 assembly runs, and the paper_reviewer requests revisions
during P5 review-revision. The researcher must rerun P3 and P4 to address
the reviewer's concerns.

Total: 12 runs (2 P1, 2 P2, 3 P3, 3 P4, 2 P5).

## Step-by-step evaluation

### Step 1: P1 → P2 → P3 — standard, alpha v1

- P1 publishes reference library with 15 papers.
- P2 publishes alpha v1.
- P3 Complete, theory promoted.
- **Disk**: ~4.0 MB.

### Step 2: P1 rerun — new paper discovered

- **System behavior**: The reference delta mechanism works: the lead writes
  only new reference cards to `reference-delta/papers/`, and the canonical
  library is updated atomically. The 15 existing cards are preserved; 3 new
  cards are added. `literature-summary.md` is rewritten with the new framing.
- **Graph**: P1 node digests change (new synthesis + new collection hash).
  The P1→P2 edge becomes `review_required` because the Phase 2 literature
  basis (frozen at P2 launch time) no longer matches the current P1.
- **Context per role (P1 rerun, 2 rounds)**:
  - Round 1: souls + playbook + **current reference library** (18 cards × ~2
    KB = ~36 KB + ~7 KB summary) + prior P1 summary (~25 KB). ≈ **80–100 KB**.
  - Round 2: + 3 role reports (~30 KB each). ≈ **120–150 KB**.
- **Disk**: +500 KB. Running total: ~4.5 MB.

### Step 3: P2 focused rerun on alpha — reviewed_no_change

- **System behavior**: The lead reviews alpha against the new literature.
  Outcome: the definition is unchanged. Revision history records
  `change: "reviewed_no_change"` with the new P1 literature basis.
- **Graph**: P2-alpha node's literature basis updates to current P1. The
  P1→P2 edge returns to `exact_match`. Alpha's `definition_sha256` is
  unchanged, so P2→P3 and P2→P4 edges stay `exact_match`.
- **Smooth?** ✅ This is the designed "convergence without method edit"
  mechanism from the follow-up doc (Priority 2, acceptance criterion: "a
  Phase 2 no-change review records the new literature basis and clears the
  corresponding yellow state").
- **But**: the P3 and P4 nodes were **not** directly affected by the P1
  change (no P1→P3/P4 edges exist). They remain `current`/`exact_match`. This
  is by design, but it means:
  - The new paper might change how the theory positions itself relative to
    prior work (novelty claims, related work section).
  - The new paper might introduce a benchmark that P4 should have tested.
  - **The system does not detect this.** The theory and experiments are
    considered fully current even though the research landscape shifted.
- **Context per role (P2 focused, 2 rounds)**: ~40–90 KB.
- **Disk**: +500 KB. Running total: ~5.0 MB.

### Step 4: P4 — Complete (preliminary)

- **System behavior**: P4 launches with current P1 (updated), P2 alpha v1
  (reviewed_no_change), P3 theory (Complete). The data_scientist sees the new
  references in the frozen P1 context. The experiments run and produce a
  Complete package.
- **Smooth?** ✅ The P4 run is clean. The frozen `current_records` snapshot
  includes the updated P1 synthesis and reference index, so the data_scientist
  is aware of the new paper.
- **Context per role (P4, 3 stages)**: ~140–200 KB.
- **Disk**: +600 KB. Running total: ~5.6 MB.

### Step 5: P5 assembly

- **Smooth?** ✅ All records current. Manuscript assembled.
- **Disk**: +500 KB. Running total: ~6.1 MB.

### Step 6: P5 review-revision — reviewer requests changes

- **System behavior**: The paper_reviewer reviews the assembled manuscript
  and requests revisions. The reviewer's output includes specific critiques:
  "The convergence proof in Section 3 needs tighter bounds" and "The
  experiments should include a comparison against [new benchmark from the
  recent paper]."
- **Smooth?** ⚠️ The review-revision run itself works. But the revision
  requests point to **both** P3 (tighter bounds) and P4 (new benchmark). To
  address them, the researcher must rerun P3 and P4. The system has no
  mechanism to link the reviewer's specific critiques to phase-level reruns
  — the researcher must manually decide which phases to rerun.
- **Disk**: +300 KB. Running total: ~6.4 MB.

### Step 7: P3 rerun — tighter bounds (Complete)

- **System behavior**: P3 reruns with the same method v1. The theorist
  produces tighter bounds. New theory promoted as generation 2.
- **Graph**: P3 gen-2 is `current`. Sibling edge P4→P3 becomes
  `review_required` (P4's stored counterpart basis points to P3 gen-1).
- **Context per role**: ~150–230 KB (includes P4 summary + prior P3 as
  historical).
- **Disk**: +1.0 MB. Running total: ~7.4 MB.

### Step 8: P4 rerun — new benchmark (Complete)

- **System behavior**: P4 reruns with current P3 gen-2 theory. The
  data_scientist adds the new benchmark comparison. New empirical promoted
  as generation 2.
- **Graph**: P4 gen-2 is `current`. Sibling edge P3→P4: P3's stored
  counterpart basis now points to P4 gen-1, but current P4 is gen-2. →
  `review_required`. **Ping-pong.**
- **Context per role**: ~160–220 KB.
- **Disk**: +600 KB. Running total: ~8.0 MB.

### Step 9: P5 assembly rerun

- **System behavior**: `current_upstream_basis()` checks P3 and P4 method
  identity match (both v1 — method definition unchanged). Both present.
  Launch succeeds. New manuscript assembled as generation 2.
- **Smooth?** ✅ But the manuscript is assembled from P3 gen-2 + P4 gen-2,
  which haven't seen each other's latest rerun (sibling ping-pong from Step
  8). The graph will show `review_required` on the sibling edge.
- **Disk**: +500 KB. Running total: ~8.5 MB.

## Issues identified

### 🟡 Issue A: No P1→P3/P4 direct propagation

The new paper (Step 2) potentially affects both theoretical positioning and
experimental benchmarks. But the graph has no P1→P3 or P1→P4 edges. After the
P2 `reviewed_no_change`, the P3 and P4 records appear fully `exact_match`
(green), even though the research landscape has shifted. The system relies
entirely on the Phase 2 review to determine whether P3/P4 are affected — and
the Phase 2 review only checks the method definition, not the downstream
scientific content.

**The researcher must manually judge** whether P3/P4 need reruns based on the
new literature. The system provides no signal.

### 🟡 Issue B: P5 review-revision doesn't link to phase reruns

When the paper_reviewer requests changes that require P3 and P4 work, the
system records the review output but doesn't create any actionable link to
the phases that need rerunning. The researcher must read the review, decide
which phases to rerun, and launch them manually. This is reasonable for a
human-in-the-loop system, but the graph doesn't track "P5 review found issues
that require P3 rerun" as a structured state.

### 🟡 Issue C: Sibling ping-pong after review-driven reruns

Steps 7–8 produce the ping-pong pattern: P3 gen-2 makes P4 stale, P4 gen-2
makes P3 stale. The system requires the researcher to accept yellow edges
and proceed, or to rerun again hoping for convergence (identical knowledge
fragment digests).

## Space summary

| Component | Size |
|---|---|
| P1 (2 runs) | ~1.0 MB |
| P2 (2 runs: initial + focused) | ~1.0 MB |
| P3 alpha (2 runs: gen-1 + gen-2) | ~2.0 MB |
| P4 alpha (2 runs: gen-1 + gen-2) | ~1.2 MB |
| P5 (3 runs: assembly + review + rerun) | ~1.5 MB |
| Control + state | ~2.0 MB |
| **Total** | **~8.7 MB** |

## Verdict

✅ **The literature refresh mechanism is well-designed at the P1→P2 level.**
The reference-delta system, the `reviewed_no_change` provenance, and the
graph edge updates all work correctly for clearing the P1→P2 yellow state
without a method edit.

⚠️ **But the gap is P1→P3/P4.** New literature can shift novelty claims and
experimental benchmarks without changing the method definition. The system
has no mechanism to detect or signal this. The researcher must manually
judge whether P3/P4 need reruns — the graph shows everything green.

⚠️ **Review-driven reruns produce sibling ping-pong**, requiring either
convergence (stable knowledge fragments) or acceptance of yellow edges.
