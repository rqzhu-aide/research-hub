# Situation 01: Method Revision Cascade

## Hypothesis

A researcher completes P1 (Literature) and P2 (Methods), getting **two candidate
methods**: `method-alpha` and `method-beta`. They run P3 (Theory) for alpha and
get a Complete result. They run P4 (Experiments) for alpha and get a Complete
result. Both match alpha `v1`.

Then the researcher realizes alpha's definition has a flaw — the step-size
adaptation rule is unstable in high dimensions. They rerun P2 with a focused
scope on alpha, advancing it to `v2` (new definition digest).

They then rerun P3 for alpha `v2` (theory passes). The P4 for alpha `v1` is now
stale. They rerun P4 for alpha `v2`.

Finally they run P5 for alpha `v2`, assembling the manuscript.

Meanwhile, `method-beta` was never developed beyond P2. Its definition has not
changed.

## Steps and evaluation

### Step 1: P1 complete, P2 publishes alpha v1 + beta v1

- **Graph**: P1 node = `current`/`exact_match`. P2 node = `current`/
  `exact_match`. All P3/P4/P5 nodes = `missing`/`not_available`.
- **System behavior**: `literature_records.promote_reference_delta()` promotes
  the canonical reference library atomically. `method_menu.promote_staged_menu()`
  publishes both method files with `change: "added"`.
- **Smooth?** ✅ Yes.
- **Context per role (P1 run, 2 rounds, parallel)**:
  - Round 1 (each role): team soul (~2 KB) + phase playbook (~5 KB) + user
    direction (~1 KB) + no prior summaries. ≈ **8–10 KB** each.
  - Round 2 (each role): + round-1 reports from all 3 roles (~20–40 KB each)
    + lead's round-1 synthesis. ≈ **30–50 KB** each.
- **Context per role (P2 run, 2 rounds, parallel)**:
  - Round 1: souls + playbook + P1 final summary (~25 KB) + reference library
    index. ≈ **35–45 KB** each.
  - Round 2: + 3 role round-1 reports (~30 KB each). ≈ **60–80 KB** each.
- **Disk at this point**:
  - P1 workspace: ~380 KB round outputs + ~90 KB reference cards + ~7 KB
    summary + ~25 KB HTML summary + ~13 KB decision record ≈ **515 KB**.
  - P2 workspace: ~350 KB round outputs + ~17 KB method files + ~30 KB HTML
    summary + ~22 KB decision record ≈ **420 KB**.
  - Control directory: ~640 KB (P1 context snapshots) + ~350 KB (P2 context
    snapshots) + manifest/state ≈ **1.2 MB**.
  - **Total**: ~2.1 MB.

### Step 2: P3 for alpha v1 — Complete

- **Graph**: P3-alpha node = `current`/`exact_match` (method identity v1
  matches). P4-alpha = `missing`.
- **System behavior**: `theory_records.promote_staged_theory()` atomically
  moves the theory package to `branches/method-alpha/evaluations/`. The theory
  record stores `method_identity: {alpha, v1, sha256...}`.
- **Smooth?** ✅ Yes.
- **Context per role (P3 run, 3 sequential stages)**:
  - Stage 1 — theorist: souls + playbook + P1 summary (~25 KB) + P2 method
    definition (~2 KB) + P2 summary (~30 KB) + current_records snapshot (P1
    literature + P2 method ≈ 40 KB frozen copies). ≈ **100–120 KB**.
  - Stage 2 — data_scientist (audit): + theorist's stage-1 report (~45 KB).
    ≈ **120–140 KB**.
  - Stage 3 — research_lead (synthesize): + both prior reports. ≈
    **140–160 KB**.
- **Disk**: P3 round outputs ~670 KB + HTML summary (~40 KB) + decision record
  (~15 KB) + theory record + knowledge fragment + context snapshot (~250 KB).
  **Adds ~1 MB**. Running total: **~3.1 MB**.

### Step 3: P4 for alpha v1 — Complete

- **Graph**: P4-alpha node = `current`/`exact_match`. P3↔P4 sibling edge:
  `exact_match` (P4 stored counterpart basis matching current P3).
- **System behavior**: `empirical_records.promote_staged_package()` atomically
  moves empirical package. Evidence index and knowledge fragment sealed.
- **Smooth?** ✅ Yes.
- **Context per role (P4 run, 3 sequential stages)**:
  - Stage 1 — data_scientist: same inputs as P3 theorist, + P3 theory summary
    (~40 KB) + P3 theory record. ≈ **140–160 KB**.
  - Stage 2 — theorist (audit): + DS stage-1 report (~30 KB). ≈ **160–180 KB**.
  - Stage 3 — research_lead: + both. ≈ **180–200 KB**.
- **Disk**: P4 outputs ~220 KB + summary (~20 KB) + decision record +
  empirical record + evidence index + knowledge fragment + context snapshot
  (~250 KB). **Adds ~600 KB**. Running total: **~3.7 MB**.

### Step 4: P2 rerun — focused on alpha, advances to v2

- **Graph**: P2 node identity changes to `{alpha v2, new_digest}`. The edge
  P2→P3-alpha flips to `review_required` (v2 digest ≠ v1 digest). The edge
  P2→P4-alpha also flips to `review_required`. Method-beta P2 edge stays
  `exact_match` (unchanged).
- **System behavior**: `method_menu` revision history records
  `change: "definition_revised"`. Critical check at line ~1259:
  if definition changed but version did not advance → **hard error**.
  The agent must bump the version.
- **Smooth?** ✅ Yes. The **scope mechanism** (`focused_method`) works
  correctly — beta's provenance is preserved. A definition change without a
  version bump is a **hard error**, but this should not surprise the agents:
  the Phase 2 playbook has an explicit "Method definition and version rule"
  section (`_phase.md`: "Advance the method version whenever the mathematical
  definition changes... Research Hub... rejects a changed definition published
  under the same version"), and `_lead.md` repeats the instruction.
- **Context per role (P2 rerun, focused, 2 rounds)**:
  - Round 1: souls + playbook + P1 summary (~25 KB) + current catalog with
    alpha v1 and beta v1. ≈ **40–50 KB**.
  - Round 2: + 3 role reports. ≈ **70–90 KB**.
- **Disk**: Same as initial P2 (~420 KB) + new context snapshot. **Adds ~500
  KB**. Running total: **~4.2 MB**.

### Step 5: P3 rerun for alpha v2 — Complete

- **Graph**: P3-alpha node updates to `{alpha v2}`. `current`/`exact_match`.
  Sibling edge P3→P4 now shows: P3 is v2, P4 is still v1 → sibling edge =
  `review_required`.
- **System behavior**: Theory record promoted with new generation number (2).
  Backup of v1 theory retained.
- **Smooth?** ✅ Yes. The frozen `current_records` snapshot includes the stale
  P4 v1 record (still the canonical current), labeled with its identity. The
  theorist can see "experiments were done under v1".
- **Context per role (P3 rerun, 3 stages)**:
  - Stage 1 — theorist: previous inputs + v2 method definition + P4 v1
    summary (~20 KB) + P4 stale label. ≈ **120–150 KB**.
  - Stage 2 — DS audit: + theorist report (~45 KB). ≈ **150–180 KB**.
  - Stage 3 — lead: + both. ≈ **180–210 KB**.
- **Disk**: Second P3 run adds ~1 MB. Running total: **~5.2 MB**.

### Step 6: P4 rerun for alpha v2 — Complete

- **Graph**: P4-alpha node updates to `{alpha v2}`. Both P3 and P4 now match
  v2. Sibling edge = `exact_match`.
- **System behavior**: Empirical record promoted with generation 2. v1 backup
  retained.
- **Smooth?** ✅ Yes.
- **Context per role (P4 rerun, 3 stages)**:
  - Stage 1 — DS: + P3 v2 theory summary (~40 KB) + stale P4 v1 summary
    labeled as historical. ≈ **160–190 KB**.
  - Other stages proportionally larger.
- **Disk**: Adds ~600 KB. Running total: **~5.8 MB**.

### Step 7: P5 for alpha v2

- **Graph**: P5 node = `current`/`exact_match`. All upstream edges:
  `exact_match`.
- **System behavior**: `manuscript_records` assembles from current P1 + P2 v2 +
  P3 v2 + P4 v2. The `phase5_projection` validates all frozen identities match.
- **Smooth?** ✅ Yes.
- **Context per role (P5 run, 1+ stages)**:
  - Lead: all current records frozen (P1 summary + P2 method + P3 theory
    manuscript + P4 synthesis + P4 evidence index + P4 knowledge fragment).
    ≈ **200–250 KB**.
- **Disk**: Adds ~500 KB. Running total: **~6.3 MB**.

## Space summary

| Component | Size |
|---|---|
| P1 (2 runs, one rerun) | ~1.0 MB |
| P2 (2 runs) | ~0.9 MB |
| P3 alpha (2 runs: v1 + v2) | ~2.0 MB |
| P4 alpha (2 runs: v1 + v2) | ~1.2 MB |
| P5 alpha v2 (1 run) | ~0.5 MB |
| Control (manifests, contexts, current-results) | ~1.5 MB |
| **Total** | **~7.1 MB** |

The system also retains backups of superseded v1 theory and empirical packages.
Each backup is the full canonical record (~100–200 KB), so backups add ~400 KB.

## Verdict

✅ **Smooth end-to-end.** The mandatory version bump on definition changes is
enforced in `method_menu` (~line 1256: "changes its mathematical calculation
without advancing the version" → hard error) **and** documented in the Phase 2
playbooks, so agents are properly instructed.
