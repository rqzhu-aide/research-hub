# Review & Revision: Research Lead (Revision Stage)

## Your task
You are stage 2 of this phase. The paper reviewer has already audited the draft
(stage 1). Revise the prepared current `manuscript.md` into the complete new
current paper by addressing every review point.

**Use the `stat-paper-writing` skill** (provisioned to your profile) to maintain
paper conventions during revision.

## What to do
1. Read the paper reviewer's complete review.
2. Read the exact frozen manuscript snapshot reviewed in stage 1.
3. For each review point (weakness, recommendation, question):
   - **Fix it** in the manuscript if it is valid and fixable.
   - **Defer it** with explicit reasoning if it cannot be fixed in this revision
     (state why and what would be needed).
   - **Push back** with reasoning if you disagree with the reviewer's assessment.
4. Write the complete revised paper to `manuscript.md` at the run output root.
5. Write a revision log documenting every change in your stage report.
6. Write the exact unified review-to-revision diff to `manuscript-post-review.diff`.

## Revision principles
- **Every review point must be addressed.** Silently ignoring a weakness is not
  acceptable. The user must see what was changed and what was not.
- **Preserve scientific honesty.** If the reviewer identifies an overclaim, narrow
  it. If a proof has a gap, fix it or flag it. Do not soften valid criticism.
- **The revision log is mandatory.** For each change: what was changed, where,
  and why. This makes the revision auditable.
- **The final manuscript is the deliverable.** It should be complete, coherent,
  and ready for the user to review.

## What to produce
Write the revision response and log to `{{output_path}}`:

Begin with **Scientific completion outcome: Complete, Partial, or Failed**.

1. **Revision log**: for each review point, what was done (fixed / deferred /
   disputed), with details.
2. **Summary of changes**: a high-level overview of how the draft evolved.
3. **Remaining open questions**: anything that could not be resolved in this
   revision.

The scientific deliverables are separate exact files: the complete paper at
`manuscript.md` and the unified diff at `manuscript-post-review.diff`. Do not
embed the paper inside the stage report or create another manuscript file.
