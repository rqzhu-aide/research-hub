# Situation 07: Branch Abandonment and Method Replacement

## Scenario

A researcher completes P1 and P2, producing three methods: `method-alpha`,
`method-beta`, `method-gamma`.

They develop alpha fully: P3 Complete, P4 Complete, P5 assembly + review.
Then they develop beta partially: P3 Complete, P4 Partial (one experiment
failed due to numerical instability).

After reviewing both manuscripts, the researcher decides alpha is the most
promising direction but realizes the core idea can be reformulated more
elegantly. They want to **retire** alpha and beta, create a new method
`method-delta` derived from alpha's framework but with a cleaner formulation.

They run P2 (full catalog) to add delta. Then they develop delta: P3 Complete,
P4 Complete, P5 assembly + review.

Meanwhile gamma was never developed. The researcher also wants to clean up by
retiring gamma.

Total: 15 runs (2 P1, 2 P2, 3 P3, 3 P4, 3 P5, plus 2 method retirements).

## Step-by-step evaluation

### Step 1: P1 → P2 (3 methods)

Standard. Disk: ~2.5 MB.

### Step 2: Full alpha pipeline (P3, P4, P5 assembly, P5 review)

- P3-alpha Complete → theory promoted.
- P4-alpha Complete → empirical promoted.
- P5-alpha assembly → manuscript assembled. `paper_review: {kind: "assembly"}`.
- P5-alpha review-revision → paper_reviewer reviews. Manuscript promoted
  generation 2. `paper_review: {kind: "review_only"}`.
- **Smooth?** ✅ Standard pipeline.
- **Context per role (P5 assembly)**: all current records frozen. ~250 KB.
- **Context per role (P5 review)**: frozen manuscript snapshot (~2 MB max,
  realistically ~50–100 KB). ~200 KB.
- **Disk after alpha**: ~5.0 MB.

### Step 3: Partial beta pipeline (P3 Complete, P4 Partial)

- P3-beta Complete → theory promoted.
- P4-beta Partial → empirical promoted (Partial is eligible for P4). Evidence
  index records the failed experiment with `unresolved` disposition.
- **Smooth?** ✅ P4 Partial promotion works. The empirical record carries the
  Partial outcome and unresolved evidence count.
- **Disk after beta**: ~6.5 MB.

### Step 4: Retire alpha and beta

- **System behavior**: `method_menu` sets `status: "retired"` on the catalog
  entries. The entries remain in the registry with their revision histories.
  The branch folders (`branches/method-alpha/`, `branches/method-beta/`) stay
  on disk.
- **Graph**: Retirement is enforced at the UI and launch layers, not the
  lookup layer: `_current_method()` resolves any catalog entry by stable_id
  regardless of status, so a retired branch's graph can still be built for
  history views. But the branch picker shows retired methods with
  `method-status-retired`, the "Use for following phases" option is removed,
  and the launch route rejects a retired `method_branch`. Retirement also
  marks the branch's current heads stale ("retired by the user").
- **Smooth?** ✅ Retirement works as designed. But:
  - **Retired branches are never garbage-collected.** Alpha's full pipeline
    (theory, empirical, manuscript, all backups) stays on disk indefinitely.
    Beta's partial pipeline too.
  - The current records for alpha and beta (theory, empirical, manuscript)
    remain in their canonical directories. No mechanism removes them.
- **Disk**: No reduction. Still ~6.5 MB.

### Step 5: P2 full-catalog rerun — add method-delta

- **System behavior**: The staged catalog includes alpha (retired), beta
  (retired), gamma (unchanged), and delta (new). The promotion:
  - Alpha stays retired. Its provenance is preserved.
  - Beta stays retired.
  - Gamma gets `change: "reviewed_no_change"` in its revision history.
  - Delta gets `change: "added"`.
- **Critical question**: does a full-catalog P2 rerun change gamma's
  `definition_sha256`? No — `reviewed_no_change` means the definition didn't
  change. Only the literature review provenance is updated.
- **Smooth?** ✅ But note: the P2 rerun makes gamma's P2 edge
  `review_required` if the P1 literature basis changed since gamma's original
  P2 run (it hasn't in this scenario, so it stays `exact_match`).

### Step 6: Full delta pipeline (P3, P4, P5 assembly, P5 review)

- P3-delta Complete, P4-delta Complete, P5-delta assembly, P5-delta review.
- All standard. Method identity is delta v1.
- **Smooth?** ✅ Fresh branch, no cross-contamination from alpha/beta.
- **Disk after delta**: ~9.0 MB.

### Step 7: Retire gamma

- Gamma had no P3/P4/P5 runs. Only the P2 method file exists.
- Retirement sets `status: "retired"` on the catalog entry.
- **Smooth?** ✅ Clean retirement.

## Issues identified

### 🟡 Issue A: Retired branches are permanent storage dead weight

After retiring alpha (full pipeline: P3, P4, P5×2) and beta (P3, P4 Partial),
all their artifacts remain on disk:

| Component | Alpha | Beta |
|---|---|---|
| Theory records + backups | ~200 KB | ~200 KB |
| Empirical records + backups | ~200 KB | ~150 KB |
| Manuscript records + backups | ~300 KB | — |
| Round outputs (all runs) | ~1.0 MB | ~0.7 MB |
| Context snapshots | ~1.0 MB | ~0.5 MB |
| HTML summaries + decisions | ~200 KB | ~100 KB |
| **Per retired branch** | **~2.9 MB** | **~1.65 MB** |

Total dead weight from retirements: ~4.5 MB — roughly half the project's
9 MB. The follow-up doc (Priority 6) identifies this but provides no timeline.

### 🟡 Issue B: P2 full-catalog rerun provenance for unchanged methods

When the P2 full-catalog rerun runs, gamma (unchanged) gets
`change: "reviewed_no_change"`. This is correct and doesn't change the
definition digest. But the P2 run's `phase_two_literature_basis` is updated
to the current P1 generation. If the P1 literature hasn't changed, this is a
no-op. If it has, gamma's P2 edge becomes `review_required` even though the
method definition didn't change — and there's no way to clear it without
rerunning P2 in focused mode for gamma.

### 🟢 Observation: No cross-contamination between branches

Delta's development is completely clean. The `_trusted_context` function
filters by `stable_id`, and `current_context_records` loads only for the
selected method. Delta's agents never see alpha's or beta's theory or
experiments. This is correct by design.

## Space summary

| Component | Size |
|---|---|
| P1 (2 runs) | ~1.0 MB |
| P2 (2 runs: 3+1 methods) | ~1.0 MB |
| Alpha full pipeline (P3+P4+P5×2) | ~3.0 MB |
| Beta partial pipeline (P3+P4) | ~1.5 MB |
| Delta full pipeline (P3+P4+P5×2) | ~3.0 MB |
| Gamma (P2 only, retired) | ~0.05 MB |
| Control + state | ~2.0 MB |
| **Total** | **~11.5 MB** |

Of this, ~4.5 MB (39%) is retired-branch dead weight with no cleanup path.

## Verdict

✅ **The retirement mechanism works correctly.** Methods are retired cleanly,
branches are preserved for provenance, and new methods develop without
contamination.

⚠️ **Storage accumulates from retired branches with no GC.** After two full
retirements, nearly half the project's disk usage is dead weight. This is
manageable at current scale (~12 MB) but would become problematic in a
long-running project with many method iterations.

⚠️ **The P2 full-catalog yellow cascade** can affect unchanged methods if P1
literature changed, with no way to clear it for individual methods without
focused P2 runs.
