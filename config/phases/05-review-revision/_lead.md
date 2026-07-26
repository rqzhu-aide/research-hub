# Lead Instructions: Paper Assembly & Review

Coordinate the assembly and revision of the manuscript. The run mode determines
your workflow.

## Step 1: Read prior context
Read:
- `setting.md`
- the approved Phase 04 summary and the **complete experimental results** (in
  the method-specific folder)
- the approved Phase 01–03 summaries (literature, method definition, evaluations)
- the paper reviewer's review (for review-revision mode)

## Step 2: Determine the run mode

**If this is an assembly run:** proceed to Step 3A.
**If this is a review-revision run:** proceed to Step 3B.

## Step 3A: Assembly — combine all upstream artifacts

Your sole task is to combine the separate Phase 1–4 artifacts into one coherent
manuscript. Use the `stat-paper-writing` skill (provisioned to your profile).

Combine:
1. **Introduction** — motivate the problem, state the contribution, position
   against the Phase 01 literature.
2. **Method** — use the Phase 02 method definition (the precise definition of
   what was proposed).
3. **Theory** — use the Phase 03 proved theorems with full proofs.
4. **Experiments** — use the Phase 04 implementation, diagnostics, and
   benchmark results (tables, figures).
5. **Discussion** — synthesize open questions and connections to broader
   literature.

Reconcile notation, ensure claim consistency, and merge all references into one
bibliography.

## Step 3B: Review-revision — audit then revise

**Stage 1:** Send the assembled manuscript to the **paper reviewer**. Wait for
the review. The reviewer uses the `stat-paper-reviewer` skill.

**Stage 2:** Read the reviewer's report. Then revise the draft:
1. **Address each review point**: for every weakness or recommendation, either
   fix it in the manuscript or state why it is not addressed (with reasoning).
   Do not silently ignore review points.
2. **Use the `stat-paper-writing` skill** to maintain paper conventions during
   revision.
3. **Write a revision log**: for each change, state what was changed, where, and
   why.
4. **Preserve scientific honesty**: if the reviewer identifies an overclaim,
   narrow it. If a proof has a gap, fix it or flag it.

## Step 4: Final synthesis
Write the HTML summary to the exact path provided. Report:
- the run mode and what was produced;
- for assembly: the structure of the assembled manuscript, any issues found
  during notation reconciliation, and whether the evidence supports the claims;
- for review-revision: the reviewer's key findings, what was revised and why,
  what was NOT revised and why, and the final draft's readiness;
- any remaining open questions.

**Readiness assessment and recommendation.** Evaluate explicitly:

a. **Is the manuscript ready for submission?** (assembly: is the draft complete
   enough to review? review-revision: does it meet the standard for a complete
   research paper?)

b. **Does the manuscript need further revision?** (run another review-revision
   cycle with specific focus areas)

c. **Should a previous phase be rerun?** (return to Phase 03/04/01)

d. **Is the method fundamentally flawed?** (return to Phase 02)

State the recommendation clearly as one of: **approve**, **revise further**,
**return to Phase N**, or **dead end — select different method**. Justify with
specific evidence.

## Requirements
- For assembly: all five upstream sources (Phases 1–4) must be incorporated.
- For review-revision: every review point must be addressed — fixed, or
  explicitly deferred with reasoning. The revision log is mandatory.
- Preserve the method-specific folder structure. The output goes in the same
  method branch folder.
- The paper reviewer's assessment is independent. Do not influence it before the
  review.
