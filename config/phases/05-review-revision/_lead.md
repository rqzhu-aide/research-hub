# Lead Instructions: Paper Assembly & Review

Coordinate the assembly and revision of the manuscript. The run mode determines
your workflow.

## Step 1: Read prior context

Read:

- `setting.md`;
- the intact, completed Phase 1 literature result;
- the intact, completed Phase 2 method-development result and its published
  canonical definition selected for this run;
- the intact, completed Phase 3 theory and discussion reports for the selected
  method;
- the intact, completed Phase 4 empirical results and discussion reports for
  the same method identity;
- the paper reviewer's report for review-revision mode.

Verify that all required results from Phases 1 through 4 are present, readable,
and pass their integrity checks. Then verify that the Phase 3 and Phase 4
results match the same stable ID, version, and definition digest selected for
the Phase 5 run. If any result is missing, corrupt, or mismatched, stop and
report the exact problem. Do not assemble theory and experiments from different
branches or method versions.

## Step 2: Determine the run mode

**If this is an assembly run:** proceed to Step 3A.
**If this is a review-revision run:** proceed to Step 3B.

## Step 3A: Assembly

Your sole task is to combine the separate Phase 1 through Phase 4 artifacts
into one coherent
manuscript. Use the `stat-paper-writing` skill (provisioned to your profile).

Combine:
1. **Introduction**: motivate the problem, state the contribution, position
   against the Phase 01 literature.
2. **Method**: use the Phase 02 method definition (the precise definition of
   what was proposed).
3. **Theory**: use the Phase 03 proved theorems with full proofs.
4. **Experiments**: use the Phase 04 implementation, diagnostics, and
   benchmark results (tables, figures).
5. **Discussion**: synthesize open questions and connections to broader
   literature.

Reconcile notation, ensure claim consistency, and merge all references into one
bibliography.

## Step 3B: Review and revision

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
**return to Phase N**, or **dead end: select different method**. Justify with
specific evidence.

## Requirements

- Assembly requires intact, completed results from Phases 1 through 4. The Phase
  3 and Phase 4 results must match the same stable ID, version, and definition
  digest selected for the Phase 5 run.
- For review-revision, address every review point by fixing it, deferring it with
  reasoning, or disputing it with evidence. The revision log is mandatory.
- Preserve the method-specific folder structure. The output goes in the same
  method branch folder.
- The paper reviewer's assessment is independent. Do not influence it before the
  review.
