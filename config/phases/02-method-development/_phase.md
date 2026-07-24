# Phase: Method Development

## Goal
Propose genuinely new ideas — new insights, frameworks, or mechanisms — that
occupy a unique position distinct from any method in the literature. This is a
**creative brainstorm**, not a validation step. The literature review is the
backdrop that makes the novelty legible; it is not the material to recombine.

Each member proposes **multiple ideas** from their scientific perspective. The
bar is: new, innovative, and logically reasonable. Full validation belongs in
later phases — Phase 2 is where the team thinks broadly and takes intellectual
risks.

## What makes an idea worth proposing
A candidate idea should have:

1. **A new mechanism, insight, or framework** — not a marginal improvement or
   a recombination of existing techniques. The novelty is in *how* the idea
   works, not just *what* it targets.
2. **A unique position** — articulate why no existing method occupies this
   space. What does this idea enable that prior work structurally cannot?
3. **Logical coherence** — the core logic holds up under scrutiny. Assumptions
   are stated, the central claim is internally consistent, and the idea is
   defensible in principle. A full proof or implementation is **not** required
   at this stage.
4. **A clear target and obstacle** — what scientific quantity or decision
   matters, and why do existing approaches fail to resolve it?

## When this phase may be run
Requires a current Phase 01 summary approved by the user. If that summary is
unavailable, the web UI identifies the missing prior evidence, but the user may
choose to proceed. The lead must then state what prior evidence is unavailable.

**On rerun:** the prior Phase 02 run is provided as **comparison evidence** —
"here is what the team proposed before." The new run should generate **fresh
ideas**, not merely refine the prior set. Ideas from the prior run may be
extended, combined, or replaced. The team should think broadly again, informed
by (but not constrained to) what was proposed before.

## Study structure
Each role proposes multiple ideas independently in round 1, working from their
scientific perspective (theoretical, computational, contribution-level). In
later rounds, the roles read one another's ideas and may combine, refine, or
identify connections — but the goal is to **enrich the idea set**, not to
converge on a single method.

## What the lead recommends
After the brainstorm, the lead's synthesis does **not** select one method.
Instead, the lead organizes the full idea set and recommends one of two paths
for the user to decide:

1. **Return to Phase 01** for a deeper literature review — if the ideas would
   benefit from more related knowledge (e.g., to sharpen the unique position
   or check for closer related work in an unfamiliar area).
2. **Proceed to Phase 03** to validate the ideas — if the ideas are
   sufficiently developed and the user wants to pursue theoretical or numerical
   validation of one or more candidates.

The user makes this decision. The lead recommends; the user decides.

## Files and outputs
Write all outputs under `ideas/run/NN/`:

- `round-01/<role>.md`, `round-02/<role>.md`, ...: idea proposals and cross-reactions
- Write the HTML summary to the exact path provided for this run and do not
  overwrite earlier summaries.

Each role report begins with Complete, Partial, or Failed as defined in the team
norms. Nonempty Partial and Failed reports preserve usable ideas and do not
prevent the lead from completing the configured run.

## Files in this folder
- `_lead.md`: instructions for the research lead. Read this file first if you are
  the lead.
- `research_lead.md`, `theorist.md`, `data_scientist.md`: role-specific
  instructions.
