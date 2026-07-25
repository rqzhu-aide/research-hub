# Phase: Theoretical Analysis

## Goal
Evaluate all ideas proposed in Phase 2 across four dimensions and produce
rankings that help the user decide which idea(s) to pursue. This is an
**assessment phase**, not a proof-development phase — the team is judging
ideas, not proving theorems about them.

The four evaluation dimensions:

1. **Correctness** — Is the core logic sound? Are there internal contradictions,
   invalid assumptions, or obvious errors? Does the central argument hold up
   under scrutiny?
2. **Methodological novelty** — How genuinely new is the mechanism, framework,
   or insight? Is it distinct from existing work, or is it a recombination?
   Does it occupy a position no existing method occupies?
3. **Theoretical rigor** — Can the idea be formalized precisely? How deep is the
   theoretical foundation? Is there a clear path to formal results, or is it
   speculative? What assumptions would need to hold?
4. **Computational cost** — Is the idea tractable? What is the computational
   profile (time, memory, scaling)? Are there numerical stability concerns? Is
   it practically implementable?

## Prior information
Requires a current Phase 02 summary approved by the user. The Phase 02 summary
contains the full idea set to be evaluated. Phase 01 (literature review) is also
provided automatically — use it to judge methodological novelty against existing
work. If either summary is unavailable, the web UI identifies the missing prior
evidence, but the user may choose to proceed. The lead must then state what prior
evidence is unavailable.

**On rerun:** the prior Phase 03 evaluation is provided as **comparison
evidence** — "here is how the team rated these ideas before." The new run should
re-evaluate independently, informed by but not constrained to the prior ratings.
If the Phase 02 idea set changed (new ideas added), the new evaluation must cover
all current ideas, not just the ones evaluated before.

## Study structure
**Debate pattern.** All three roles evaluate all ideas independently in round 1.
In later rounds, they read one another's evaluations, debate disagreements from their own perspectives, and revise their own ratings based on the arguments heard. The lead then synthesizes the (possibly still disagreeing) evaluations into rankings.

Each role evaluates every idea on all four dimensions, but brings their deepest
expertise to specific ones:

- **Theorist** leads on *correctness* and *theoretical rigor*.
- **Data Analyst** leads on *computational cost*.
- **Research Lead** leads on *methodological novelty* and overall scientific value.

## Evaluation scale
Each idea receives a rating on each dimension. Use a clear scale:

- **Strong** — excellent on this dimension; a genuine strength.
- **Adequate** — acceptable; no major concerns.
- **Weak** — significant concerns; would need work.
- **Insufficient information** — cannot assess from current evidence.

State the reasoning behind each rating. A rating without justification is not
useful.

## Files and outputs
Write all outputs under `draft/theory/run/NN/`:

- `round-01/<role>.md`, `round-02/<role>.md`, ...: per-round evaluations
- Write the HTML summary to the exact path provided for this run and do not
  overwrite earlier summaries.

Each role report begins with Complete, Partial, or Failed as defined in the team
norms. Nonempty Partial and Failed reports preserve usable evaluations and do not
prevent the lead from completing the configured run.

## What the user decides
The user starts every run. After the evaluation, the lead presents rankings and a
recommendation. The user then decides:

- which idea(s) to pursue in Phase 04 (numerical validation);
- to return to Phase 02 for more ideas;
- to request a revision of the evaluation;
- or to rerun the evaluation.

Completing this phase does not select a method or start numerical validation.
The user alone decides which idea(s) to carry forward.

## Files in this folder
- `_lead.md`: instructions for the research lead. Read this file first if you are
  the lead.
- `theorist.md`, `research_lead.md`, `data_scientist.md`: role-specific
  instructions.
