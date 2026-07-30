# Situation Analysis: Research Hub Behavioral Evaluation

Five realistic hypothetical use cases (each ≥8 runs) stress-testing the
versioned research record system (commit `d58ccba`, July 2026). Each traces
the system's behavior step by step, estimates context per role, projects
storage growth, and identifies design gaps.

Previous batch (situations 01–05) archived in `archived/`.

## Documents

| # | Situation | Runs | Core question |
|---|---|---|---|
| 06 | [The P3 Partial Trap](06-p3-partial-trap.md) | 10 | What happens when P3 can't reach Complete? |
| 07 | [Branch Abandonment & Replacement](07-branch-abandonment-replacement.md) | 15 | Can methods be retired and replaced cleanly? |
| 08 | [Literature Refresh Mid-Pipeline](08-literature-refresh-mid-pipeline.md) | 12 | Does a P1 rerun propagate correctly through the graph? |
| 09 | [Premature P4 with Scoping Errors](09-premature-p4-scoping-errors.md) | 11 | What happens when P4 runs in the wrong scope, or for the wrong method? |
| 10 | [Failed Runs & Recovery Loop](10-failed-runs-recovery-loop.md) | 9 | Does the system handle crashes, failures, and reruns? |
| 11 | [The Ten-Method P2 Catalog](11-ten-method-p2-catalog.md) | 17 | How does the system scale with many methods? |

## Issue summary

### Code bugs

None remaining — all bugs from the first batch (ISSUES.md #1–4) are fixed.

### Design gaps (by severity)

| Gap | Severity | Situations | ISSUES.md | Follow-up doc |
|---|---|---|---|---|
| **P3 Partial cannot promote or feed P5** — Partial theory outcome produces no current record, blocking manuscript assembly | High | 06 | New | Priority 3 |
| **Failed runs are invisible to reruns** — `failed` status excluded from `_CONTEXT_RESULT_STATUSES`, so reruns don't see what went wrong | High | 10 | New | Not tracked |
| **P4 replacement discards prior evidence** — each P4 promotion replaces the entire evidence index, losing findings from superseded runs | Medium | 07, 09 | #7 | Priority 3 |
| **No "acknowledge" disposition** — yellow edges can only be cleared by rerunning | Medium | 06, 08 | #5 | Priority 3 |
| **No P1→P3/P4 propagation** — new literature doesn't make existing theory/experiments yellow | Medium | 08 | #6 | Priority 2 |
| **Full-catalog P2 scales O(n)** — no subset review; 10 methods = ~300 KB context per role | Medium | 11 | New | Not tracked |
| **Sibling ping-pong** — rerunning P3 makes P4 stale and vice versa | Medium | 08, 09 | #8 | Priority 4 |
| **P5 doesn't gate on sibling alignment** — manuscript can be assembled from misaligned P3/P4 | Medium | 09 | #8 | Priority 3 |
| **Retired branches never garbage-collected** — accumulate indefinitely | Low | 07, 11 | #9 | Priority 6 |
| **Accidental runs create permanent artifacts** — no undo for wrong-method launches | Low | 09 | New | Not tracked |

### Context size by phase (estimated from project-004 data)

| Phase | Round/stage 1 | Final round/stage | Worst case |
|---|---|---|---|
| P1 (parallel) | ~10 KB | ~50 KB | ~150 KB (with 18+ refs) |
| P2 (parallel) | ~40 KB | ~90 KB | **~300 KB** (10 methods) |
| P3 (sequential) | ~120 KB | ~200 KB | ~230 KB (with P4 context) |
| P4 (sequential) | ~140 KB | ~200 KB | ~230 KB (comprehensive) |
| P5 (sequential) | ~250 KB | — | ~250 KB |

All within the 4 MB task-brief / 16 MB lead-prompt limits.

### Storage growth

| Scenario | Runs | Total storage | Dead weight |
|---|---|---|---|
| 06 (P3 Partial trap) | 10 | ~10 MB | ~2 MB (unpromoted P3 runs) |
| 07 (branch abandonment) | 15 | ~11.5 MB | ~4.5 MB (retired branches) |
| 08 (literature refresh) | 12 | ~8.7 MB | — |
| 09 (premature P4) | 11 | ~9.5 MB | ~0.8 MB (backup evidence) |
| 10 (failed runs) | 9 | ~7.4 MB | ~2.2 MB (failed/crashed runs) |
| 11 (ten-method catalog) | 17 | ~14.2 MB | ~5 MB (retired/undeveloped) |

Growth is linear at ~0.7–1.0 MB per run. The system adds ~0.3 MB of
unusable dead weight per failed/crashed/retired run.
