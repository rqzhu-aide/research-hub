# Situation 05: Iterative Refinement Loop and Storage Growth

## Hypothesis

A researcher is doing iterative refinement on a single method (`method-alpha`)
over many cycles. This is the "worst case" for storage and context growth.

Cycle 1: P1 → P2 (alpha v1) → P3 v1 → P4 v1 → P5 v1.
Cycle 2: Researcher gets feedback on the manuscript. Reruns P2 (alpha v2 —
revised definition). Reruns P3 v2, P4 v2, P5 v2.
Cycle 3: P1 rerun (new literature). P2 rerun (alpha v3 — adjusted scope).
P3 v3, P4 v3, P5 v3.
Cycle 4: Researcher retires alpha entirely, creates `method-beta` from scratch.
P2 beta v1, P3 beta v1, P4 beta v1, P5 beta v1.

Total: 2 P1 runs, 4 P2 runs (3 alpha versions + 1 beta), 3 P3 alpha + 1 P3
beta, 3 P4 alpha + 1 P4 beta, 3 P5 alpha + 1 P5 beta = **24 phase runs**.

## Steps and evaluation

### Context size per role across cycles

The `_trusted_context` function selects **latest-only** per phase/method. This
means context does NOT grow quadratically. Each run sees at most:

- 1 current P1 summary (~25 KB)
- 1 current P2 method definition + summary (~35 KB)
- 1 current P3 theory summary (~40 KB) + P3 theory record
- 1 current P4 empirical summary (~20 KB) + P4 evidence index
- Frozen `current_records` copies of the above (~80–120 KB)
- Souls + playbooks + user direction (~10 KB)

**Per-role context by phase:**

| Phase | Stage 1 role | Est. context | Last stage role | Est. context |
|---|---|---|---|---|
| P1 (parallel, 2 rounds) | any role, round 1 | ~10 KB | any role, round 2 | ~40–50 KB |
| P2 (parallel, 2 rounds) | any role, round 1 | ~40 KB | any role, round 2 | ~70–90 KB |
| P3 (sequential, 3 stages) | theorist | ~120 KB | research_lead | ~180 KB |
| P4 (sequential, 3 stages) | data_scientist | ~140 KB | research_lead | ~200 KB |
| P5 (sequential) | research_lead | ~250 KB | — | — |

**Does context grow across cycles?** No. The latest-only selection means cycle
4's P3 theorist sees the same amount of context as cycle 1's — one P1 summary,
one P2 method, one P4 summary. The only difference is the `current_records`
snapshot may include stale records from the prior cycle, labeled as historical.

The one growth source: `_has_archived_method_summary()` allows the user to
opt into seeing archived P3 summaries. If enabled, each prior P3 generation
adds ~40 KB. After 3 alpha P3 runs, the theorist could see ~120 KB of
historical summaries.

### Context growth in the manifest

The manifest freezes `current_records` — compact copies of current canonical
files. These are bounded:

| Record | Max size |
|---|---|
| P1 literature synthesis | 5 MB |
| P1 reference index | 5 MB |
| P3 theory record | 256 KB |
| P3 theory manuscript | 20 MB |
| P3 knowledge fragment | 4 MB |
| P4 empirical synthesis | 4 MB |
| P4 evidence index | 4 MB |
| P4 knowledge fragment | 4 MB |
| P5 manuscript | 40 MB |
| P5 manuscript record | 512 KB |

In practice, these are much smaller. Project-004's actual data shows:
- P1 synthesis: 7 KB. Reference cards: 90 KB total.
- P2 method files: 2–3 KB each.
- P3/P4 round reports: 30–55 KB each. Summaries: 20–40 KB.
- Manifest + context snapshot per run: 84–248 KB.

### Storage growth per cycle

Each full cycle (P3 + P4 + P5) adds approximately:

| Component | Per cycle |
|---|---|
| P3 round outputs (3 stages × ~45 KB each) | ~135 KB |
| P3 summary + decision record + theory record | ~80 KB |
| P3 context snapshot (frozen copies) | ~250 KB |
| P4 round outputs (3 stages × ~32 KB each) | ~96 KB |
| P4 summary + decision + empirical record | ~60 KB |
| P4 context snapshot | ~250 KB |
| P5 output + summary + manuscript record | ~150 KB |
| P5 context snapshot | ~300 KB |
| Manifests + state growth | ~100 KB |
| **Per cycle** | **~1.4 MB** |

**After 4 cycles (24 runs):**

| Cycles | Workspace | Control dir | Backups | Total |
|---|---|---|---|---|
| Cycle 1 (alpha v1) | ~2.5 MB | ~2.5 MB | — | ~5.0 MB |
| Cycle 2 (alpha v2) | +1.4 MB | +1.4 MB | +0.3 MB | ~8.1 MB |
| Cycle 3 (alpha v3 + P1 rerun) | +2.4 MB | +1.4 MB | +0.3 MB | ~12.2 MB |
| Cycle 4 (beta v1, fresh) | +1.4 MB | +1.4 MB | — | ~15.0 MB |

### Bounded vs. unbounded growth

**Bounded** (by design):
- Context per role: ~250 KB max (latest-only selection). ✅
- Current records snapshot: ~1 MB max (bounded file sizes). ✅
- Knowledge fragments: 4 MB max per phase. ✅
- Evidence index: 4 MB max, 2,000 entries max. ✅
- Graph cache: 512 KB max. ✅

**Linear growth** (expected, not problematic):
- Round outputs: accumulate per run, one folder per run. ~500 KB per phase run.
- Decision records: ~15 KB each, one per run.
- HTML summaries: ~25 KB each, one per run.
- Context snapshots: ~250 KB per run (frozen copies of current records).

**Potential concern** — sealed context copies:
- Each run's `.context/` directory contains frozen copies of the current
  records at launch time. With 24 runs, that's ~6 MB of duplicated context.
- The design doc notes this: "context growth becomes approximately linear
  rather than quadratic" — O(nS) instead of O(n²S). This is correct and
  manageable.
- The follow-up doc (Priority 6) identifies content-addressed reuse as future
  work to eliminate duplicate copies.

**Retirement impact**:
- When alpha is retired, its branch folder stays on disk. The method menu entry
  gets `status: "retired"`. The branch vanishes from the picker but its sealed
  artifacts (theory, empirical, manuscript) remain.
- This means retired branches consume disk indefinitely. No GC exists.

### Step-by-step smoothness

| Step | Smooth? | Notes |
|---|---|---|
| Cycle 1: P1→P2→P3→P4→P5 | ✅ | Standard pipeline |
| P1 rerun (new literature) | ⚠️ | Makes P2 yellow for all methods. No "acknowledge" to clear |
| P2 alpha v2→v3 | ✅ | Version advance enforced. Prior versions backed up |
| P3/P4 rerun for new versions | ✅ | Latest-only context. Stale labeled historical |
| P5 rerun | ✅ | Phase5 projection validates frozen basis |
| Method retirement (alpha) | ✅ | Branch preserved, vanishes from picker |
| New method (beta) creation | ✅ | Fresh branch, no cross-contamination |
| Archived P3 summary inclusion | ✅ | Optional, opt-in per launch |

## Space summary (after all 4 cycles)

| Component | Size |
|---|---|
| P1 workspace (2 runs + reference library) | ~1.5 MB |
| P2 workspace (4 runs: 3 alpha + 1 beta) | ~1.5 MB |
| P3 alpha workspace (3 runs) + P3 beta (1 run) | ~3.0 MB |
| P4 alpha workspace (3 runs) + P4 beta (1 run) | ~2.5 MB |
| P5 alpha workspace (3 runs) + P5 beta (1 run) | ~2.0 MB |
| Control: manifests + contexts | ~5.0 MB |
| Control: current-results + journals | ~0.5 MB |
| Backups (superseded theory/empirical/manuscript) | ~1.5 MB |
| Retired alpha branch (preserved) | ~2.0 MB |
| **Total** | **~19.5 MB** |

## Verdict

✅ **Context growth is well-controlled.** The latest-only selection ensures each
role sees a bounded amount of context regardless of how many cycles have run.
The manifest's frozen `current_records` are compact copies, not full
manuscripts.

⚠️ **Storage grows linearly** at ~1.4 MB per phase run. After 24 runs, the
project is ~20 MB. This is manageable for local storage but has no GC or
compaction path.

⚠️ **The P1→P2 yellow cascade** remains the main friction point. Each P1 rerun
makes all methods yellow on their P2 edge, and the only way to clear it is to
rerun P2 (full-catalog scope to clear all methods). After 3 cycles of
iterative refinement, the user may need to rerun P2 three times just to clear
yellow states, even if the method definitions didn't change.

⚠️ **Retired branches consume disk indefinitely.** No archival or pruning path
exists. A project with many retired methods will accumulate storage with no
cleanup mechanism.
