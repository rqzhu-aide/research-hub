# Situation Analysis: Research Hub Behavioral Evaluation

Five hypothetical use cases stress-testing the versioned research record system
(commit `d077722`, July 2026). Each traces the system's behavior step by step,
estimates context size per role, and projects storage growth.

**Accuracy pass (July 30, 2026)**: all mechanism claims verified against the
code at `d077722`. Corrections applied: Situation 01 (P2 playbooks *do*
document the version-bump rule), Situation 02 (`branch_graph_version` is an
optimistic-concurrency check, not a yellow-edge acknowledgement), Situation 03
(ping-pong table row 1 edge statuses), Situation 04 (the recovery bug's window
is pre-prepare, not post-prepare; its impact is project-wide, not one stuck
run). Situations 02–05's remaining claims and all size estimates are unchanged.

## Documents

| # | Situation | Core question |
|---|---|---|
| 01 | [Method Revision Cascade](01-method-revision-cascade.md) | Does a method version change propagate cleanly through P3→P4→P5? |
| 02 | [Multi-Branch Divergence](02-multi-branch-divergence.md) | Can multiple methods coexist, and what happens when P1 reruns shift the landscape? |
| 03 | [Sequential Siblings](03-sequential-siblings-rerun-asymmetry.md) | When P3 is rerun after P4, does P4 become stale? Does it ping-pong? |
| 04 | [Crash Recovery](04-crash-recovery.md) | Does the system recover from crashes during promotion? |
| 05 | [Iterative Refinement Loop](05-iterative-refinement-storage-growth.md) | How do context and storage grow over many cycles? |

## Cross-cutting findings

### What works well

1. **Method identity propagation** — exact (stable_id, version, sha256)
   triplets frozen into every record. A definition change is always detected.
2. **Atomic promotion** — staging → sealing → atomic rename → fsync, with
   backup retention and journal-based recovery.
3. **Latest-only context** — `_trusted_context` selects one current run per
   phase/method. Context stays bounded (~100–250 KB per role) regardless of
   history length.
4. **Sibling sequential workflow** — P3 and P4 can run in either order. The
   second one sees the first's results. The graph honestly tracks the
   asymmetry.
5. **Partial results carry forward** — a Partial P4 doesn't block downstream;
   it's visible with its limitations.

### Design gaps (common across situations)

| Gap | Severity | Situations | Status in follow-up doc |
|---|---|---|---|
| **No "acknowledge" disposition** — user cannot clear a yellow edge without rerunning the phase | High | 01, 02, 03, 05 | Priority 3 (not yet implemented) |
| **P4 replacement, not accumulation** — each P4 rerun replaces all prior evidence | Medium | 02, 05 | Priority 3 (cumulative P4 package) |
| **No direct P1→P3/P4 edges** — new literature doesn't make existing theory/experiments yellow | Medium | 02, 05 | Priority 2 (literature propagation) |
| **P5 doesn't hard-block on sibling yellow edges** — manuscript can be assembled from a P3/P4 pair where one hasn't seen the other's latest rerun | Medium | 03 | Priority 3 (separate alignment dimensions) |
| **Sibling ping-pong** — rerunning P3 makes P4 stale and vice versa; converges only if semantic content stabilizes | Medium | 03 | Priority 4 (semantic coverage contract) |
| **Crash recovery wedges the project on an interrupted first promotion** — reconcile-on-load re-raises `_sync()` failure every time the project is opened, until manual `mkdir` repair | High | 04 | Bug (failing test at HEAD; theory untested), not yet fixed |
| **No storage GC** — retired branches and sealed contexts accumulate indefinitely | Low | 05 | Priority 6 (storage lifecycle) |

### Context size summary

Typical context received by a single role agent (one round/stage):

| Phase | Round/stage 1 | Final round/stage | Notes |
|---|---|---|---|
| P1 (parallel) | ~10 KB | ~50 KB | Grows with reference library size |
| P2 (parallel) | ~40 KB | ~90 KB | Includes P1 summary + reference library |
| P3 (sequential) | ~120 KB | ~200 KB | Includes P1+P2+P4 current records |
| P4 (sequential) | ~140 KB | ~200 KB | Includes P1+P2+P3 current records |
| P5 (sequential) | ~250 KB | — | All P1–P4 current records frozen |

These are well within the 4 MB task-brief limit (`MAX_TASK_BRIEF_BYTES`) and
the 16 MB lead-prompt limit (`MAX_LEAD_PROMPT_BYTES`).

### Storage growth summary

| Scenario | Runs | Total storage |
|---|---|---|
| Situation 01 (single method, 2 versions) | 9 | ~7 MB |
| Situation 02 (3 methods, P1 rerun) | 11 | ~7 MB |
| Situation 03 (sequential siblings, reruns) | 7 | ~7 MB |
| Situation 04 (crashes + recovery) | 6 | ~5 MB |
| Situation 05 (4 iterative cycles) | 24 | ~20 MB |

Growth is linear at ~0.7–1.4 MB per phase run. No quadratic explosion.
