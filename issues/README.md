# Issue Analysis: Research Hub Behavioral Evaluation

Hypothetical use cases stress-testing the versioned research record system.
Each traces behavior step by step, estimates context per role, projects
storage growth, and identifies design gaps. Every mechanism claim is verified
against the code with file:line citations before inclusion.

`ISSUES.md` in this folder is the tracker of remaining open issues. Older
situation analyses and resolved-issue records are in `archived/` (not
tracked — retained locally for reference only).

## Documents

| # | Situation | Core question | Open issues |
|---|---|---|---|
| 08 | [Literature Refresh Mid-Pipeline](08-literature-refresh-mid-pipeline.md) | Does a P1 rerun propagate correctly through the graph? | #5, #6 |
| 11 | [The Ten-Method P2 Catalog](11-ten-method-p2-catalog.md) | How does P2 scale with many methods? | #14 |
| 17 | [Control-Dir Loss & Registry Divergence](17-control-dir-loss-and-registry-divergence.md) | What breaks when each storage part is lost? | #19-note (residual) |
| 20 | [The Uncorrectable Reference Card](20-p1-card-correction-retraction.md) | How is a wrong card fixed? | #22 |
| 22 | [Context Reduction](22-context-reduction-agent-runs.md) + [review](22-context-reduction-analysis.md) | Frozen context is ~193 KB re-read by every agent every round | — (analysis) |
| 23 | [Context Construction Plan](23-context-construction-plan.md) | Phase + role + run-specific context views; verification of the 22-analysis | — (plan, ready to implement) |

Archived July 30, 2026 (second maintenance cycle): 12 (#16 fixed —
promotion-time identity check), 13 (#17 disclosed), 15 (folded into #16),
16 (#18 fixed), 19 (#21 disclosed), 21 (folded into #19 fixes).

Archived July 30, 2026 (error-class round): 09 (#7 fixed — superseded
evidence visible downstream), 14 (#23 addressed — prior review cycle in
context), 18 (#20 fixed — project-scoped memory instructions).

## Verification standard

- Every mechanism claim cites file:line, checked against the current code.
- Scenario premises that turned out impossible are corrected in the doc's
  opening note (e.g., 12: mid-run bumps blocked by the single-active-run
  rule; 13: no user gate exists for the checkpoint).
- Size/context estimates are marked as estimates and grounded in observed
  project-004 data where possible.
