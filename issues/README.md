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
| 08 | [Literature Refresh Mid-Pipeline](08-literature-refresh-mid-pipeline.md) | Does a P1 rerun propagate correctly through the graph? | #5, #6, #8 |
| 09 | [Premature P4 with Scoping Errors](09-premature-p4-scoping-errors.md) | Wrong scope, or wrong method? | #7, #8 |
| 11 | [The Ten-Method P2 Catalog](11-ten-method-p2-catalog.md) | How does P2 scale with many methods? | #14 |
| 14 | [The P5 Review-Revision Loop](14-p5-review-revision-loop.md) | Is the review cycle honest and bounded? | #23 |
| 17 | [Control-Dir Loss & Registry Divergence](17-control-dir-loss-and-registry-divergence.md) | What breaks when each storage part is lost? | #19-note (residual) |
| 18 | [Two Projects, Shared Hermes Profiles](18-multi-project-shared-profiles.md) | What isolates concurrent projects — and what leaks? | #20 |
| 20 | [The Uncorrectable Reference Card](20-p1-card-correction-retraction.md) | How is a wrong card fixed? | #22 |

Archived July 30, 2026 (second maintenance cycle): 12 (#16 fixed —
promotion-time identity check), 13 (#17 disclosed), 15 (folded into #16),
16 (#18 fixed), 19 (#21 disclosed), 21 (folded into #19 fixes).

## Verification standard

- Every mechanism claim cites file:line, checked against the current code.
- Scenario premises that turned out impossible are corrected in the doc's
  opening note (e.g., 12: mid-run bumps blocked by the single-active-run
  rule; 13: no user gate exists for the checkpoint).
- Size/context estimates are marked as estimates and grounded in observed
  project-004 data where possible.
