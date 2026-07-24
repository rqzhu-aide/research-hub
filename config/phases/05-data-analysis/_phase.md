# Phase: Review & Revision

## Goal
Review the draft produced in Phase 4 and revise it into a final, publication-ready
manuscript. The **paper reviewer** audits the draft using the `stat-paper-reviewer`
skill and provides structured review comments and revision recommendations. The
**research lead** then revises the draft accordingly to produce the final version.

This is a **sequential** two-stage process: review first, then revise.

## Skill requirement
- **Paper reviewer** uses the `stat-paper-reviewer` skill (provisioned to the
  profile) to produce a structured, rigorous review.
- **Research lead** uses the `stat-paper-writing` skill (provisioned to the
  profile) when revising, to maintain paper conventions.

## Method-specific folders
Phase 5 operates on the same method-specific folder created in Phase 4. The
reviewer reads the draft from the method's folder and writes review comments
there. The lead writes the revised final draft to the same folder. This keeps
each method's paper — draft, review, and final — self-contained.

## Prior information
Requires a current Phase 04 summary approved by the user (the combined draft).
The reviewer reads the draft, not just the summary — the full manuscript is the
object of review. The reviewer also reads the Phase 01–03 context for
positioning and theory grounding.

## Study structure
**Sequential, 2 stages:**

1. **Review** (paper_reviewer): read the complete draft, produce a structured
   review covering soundness, clarity, significance, and originality. Identify
   weaknesses, missing elements, and specific revision recommendations ranked by
   priority.
2. **Revise** (research_lead): address each review point, revise the draft, and
   produce the final manuscript. State what was changed, what was not changed
   (and why), and what remains open.

## Files and outputs
Write all outputs in the **same method-specific folder** as the Phase 4 draft:

- `round-01/paper_reviewer.md`: structured review with revision recommendations
- `round-02/research_lead.md`: final revised manuscript + revision log
- Write the HTML summary to the exact path provided for this run.

## Files in this folder
- `_lead.md`: instructions for the research lead (revision stage).
- `paper_reviewer.md`: instructions for the paper reviewer (review stage).
- `archive-v1-debate/`: the prior debate-pattern design, archived for reference.

## What the user decides
The user starts every run. After the final draft is produced, the user decides
whether to approve it, request further revision, or rerun. The final draft is
the deliverable — it can be packaged and sent as a complete paper.
