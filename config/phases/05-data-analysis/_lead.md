# Lead Instructions: Review & Revision

Coordinate a two-stage review-and-revise cycle. The paper reviewer audits the
Phase 4 draft; you then revise it into the final manuscript.

## Step 1: Read prior context
Read:
- `setting.md`
- the approved Phase 04 summary and the **complete combined draft** (in the
  method-specific folder)
- the approved Phase 01–03 summaries (literature, method brainstorm, evaluation)
- the paper reviewer's review (once stage 1 completes)

## Step 2: Stage 1 — dispatch the review
Send the complete draft to the **paper reviewer**. The reviewer uses the
`stat-paper-reviewer` skill to produce a structured review covering:

- **Soundness**: are claims well-supported? Are proofs correct? Are baselines fair?
- **Clarity**: is the paper well-written? Could an expert reproduce it?
- **Significance**: does this matter to the community?
- **Originality**: new insights, not just incremental combination?

The reviewer provides:
- ranked weaknesses (most critical first)
- specific revision recommendations
- missing references or comparisons
- an overall assessment and score

Wait for the reviewer's report before proceeding to stage 2.

## Step 3: Stage 2 — revise the draft
Read the reviewer's report. Then revise the draft:

1. **Address each review point**: for every weakness or recommendation, either
   fix it in the manuscript or state why it is not addressed (with reasoning).
   Do not silently ignore review points.
2. **Use the `stat-paper-writing` skill** (provisioned to your profile) to
   maintain paper conventions during revision.
3. **Write a revision log**: for each change, state what was changed, where, and
   why. This makes the revision auditable.
4. **Preserve scientific honesty**: if the reviewer identifies an overclaim,
   narrow it. If a proof has a gap, fix it or flag it. Do not soften valid
   criticism to make the paper "look better."
5. **Produce the final manuscript**: the revised draft is the deliverable. It
   should be a complete, coherent paper.

## Step 4: Final synthesis
Write the HTML summary to the exact path provided. Report:
- the reviewer's key findings (top weaknesses, overall assessment);
- what was revised and why;
- what was NOT revised and why;
- the final draft's readiness for submission;
- any remaining open questions.

Present explicit user options: approve the final draft, request further revision
(specific points), rerun the review, or proceed to Phase 6 (if used for
additional finalization).

## Requirements
- Do not skip review points. Every weakness or recommendation must be addressed
  — fixed, or explicitly deferred with reasoning.
- The revision log is mandatory. The user must be able to see what changed and why.
- Preserve the method-specific folder structure from Phase 4. The final draft
  goes in the same folder as the draft and review.
- The paper reviewer's assessment is independent. Do not influence it before the
  review. You revise based on the review; you do not edit the review.
