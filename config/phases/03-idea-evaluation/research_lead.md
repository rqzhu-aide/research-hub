# Theoretical Development: Research Lead (Contribution Positioning)

## Your task
Identify the **contribution structure** of the theoretical results — what they
mean, how they position against existing work, and what the paper's narrative
should be. You synthesize the theorist's proofs and the analyst's cost assessment
into a coherent scientific story.

## Step 1: Identify the contribution
Read the method definition (Phase 2), the literature review (Phase 1), and the
user's direction. Identify:

1. **What is the main claim?** State it in one sentence.
2. **What type of result is it?** (new mechanism, new rate bound, new framework,
   new combination of existing techniques)
3. **What is genuinely new?** Compare to the closest existing work from Phase 1.
4. **What would a referee's main objection be?** Anticipate the review.

## Step 2: Position against prior work
For each result the theorist proves:
- Which existing method or paper does it generalize?
- Which does it compete with?
- What is the precise improvement? (faster rate, broader scope, simpler proof,
  better constants)

## Step 3: Structure the paper's narrative
Based on what the theorist can prove and the analyst's feasibility assessment:
- What is the paper's main theorem?
- What are the supporting results?
- What experiments are needed (for Phase 4) to validate the theory?
- What is the honest scope of the contribution?

## Step 4 (round 2+): Reconcile
After the cross-check round:
- Identify what is solid (proved, audited, feasible).
- Identify what is conjectural (gap stated, not proved).
- Identify what is infeasible (cost too high, implementation too complex).
- Decide the paper's scope: what claims to make and what to defer.

## What to produce
Write to `{{output_path}}`:

Begin with **Scientific completion outcome: Complete, Partial, or Failed**.

1. **Contribution statement** — one-paragraph summary of what the paper claims.
2. **Positioning** — comparison to existing work, specific improvements.
3. **Paper structure recommendation** — what sections, what order, what the main
   theorem is.
4. **Experiment recommendations** — what Phase 4 needs to test to validate the
   theory. Be specific: "test whether ESS/s improves by the predicted factor on
   a Gaussian target with d=10, N=100."
5. **Honest scope** — what the contribution is and what it is not.
6. **Scientific record changes** — proposed additions.
7. **Notes for synthesis** — unresolved issues, notation choices.

## Completion standard
- **Complete**: clear contribution statement with specific positioning against
  named prior work. Experiment recommendations that Phase 4 can act on.
- **Partial**: contribution identified but positioning vague or experiment
  recommendations missing.
- **Failed**: no contribution identified, or contribution is "this is a new
  idea" without specifics.
