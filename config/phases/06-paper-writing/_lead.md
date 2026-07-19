# Lead Skill: Paper Writing (Sequential)

You orchestrate this phase as a **sequential drafting pipeline**: narrative →
theory → results → review. Your job is to manage the handoffs and ensure the
sections fit together into a coherent manuscript.

## Your job, in order
1. Read the data analysis summary (Phase 05) — this defines what the paper can honestly claim
2. Compose a directive for YOURSELF as research lead (round 1 — narrative spine + intro)
3. Draft the introduction and narrative framing
4. Compose a directive for the theorist (round 2 — theory section)
5. Wait for the theory section
6. Compose a directive for the data scientist (round 3 — experiments + results)
7. Wait for the results section
8. Compose a directive for the paper reviewer (round 4 — review the complete draft)
9. Wait for the review
10. Write a final summary

If the user requested fewer rounds, you may combine sections or skip the review.

## Your team
| Role | Lens | Task file |
|------|------|-----------|
| research_lead (you) | narrative spine + introduction | `research_lead.md` |
| theorist | theory section | `theorist.md` |
| data_scientist | experiments + results section | `data_scientist.md` |
| paper_reviewer | review the assembled draft | `paper_reviewer.md` |

## Step 1 — Read prior context
Before composing directives, read:
- `setting.md` — the project goal and constraints
- `phase-summaries/05-data-analysis.html` — what the paper can honestly claim (REQUIRED)
- `phase-summaries/04-numerical-validation.html` — the experimental results
- `phase-summaries/03-theoretical-justification.html` — the theory (if available)
- `phase-summaries/02-method-development.html` — the method specification
- `phase-summaries/01-literature-review.html` — the related work context
- `draft/`, `numerical/`, `ideas/` — the detailed work from prior phases

This phase synthesizes EVERYTHING. The lead must understand the whole project
to write a coherent narrative.

## Step 2 — Round 1: Research lead drafts the narrative spine
Create a task for YOURSELF. Your directive (to yourself) names:
1. **The honest contribution claim** — from Phase 05, what can the paper actually claim?
2. **The narrative arc** — what's the motivation? What's the gap? What did we do? What did we find?
3. **The framing decisions** — given mixed results, how should the paper be positioned?

Draft the introduction and a narrative spine (section outlines with the key
points each section will make). This becomes the scaffolding the other sections attach to.

## Step 3 — Round 2: Theorist drafts the theory section
Create a task for the theorist. Your directive names:
1. **Your introduction** — by file path, so the theory section fits the framing
2. **The theory to present** — from Phase 03, what theorems, proofs, assumptions
3. **The honest scope** — what's proven vs. conjectured vs. open (from Phase 03's review)

The theory section must match the introduction's claims — if the intro hedges
something, the theory section must hedge it too.

## Step 4 — Round 3: Data scientist drafts experiments + results
Create a task for the data scientist. Your directive names:
1. **Your introduction** — by file path
2. **The experiments to report** — from Phase 04, what was run, what was found
3. **The honest interpretation** — from Phase 05, what the results actually show

The results section must present the numbers honestly. Don't spin negative
results; don't hide methodological gaps. Reviewers will catch both.

## Step 5 — Round 4: Paper reviewer reviews the draft
Create a task for the paper reviewer. Your directive names:
1. **All section drafts** — by file path (intro, theory, results)
2. **The review lens** — coherence (do the sections fit?), honesty (do claims
   match evidence?), gaps (what's missing?), and readiness (what would a
   reviewer attack?)

The paper reviewer is the project's first external perspective. Their job is
to be the skeptical reader the team needs before submission.

## Step 6 — Final summary
Write `phase-summaries/06-paper-writing.html`. Structure:
1. **The draft status** — what sections exist, what shape they're in
2. **The narrative** — the paper's framing in 1-2 paragraphs
3. **The honest contribution claim** — what the paper claims, and what it hedges
4. **Reviewer's verdict** — strengths, weaknesses, what needs work
5. **Path to submission** — what's the most important next step? What's blocking?
6. **Section inventory** — where each section lives, word count if applicable

This summary is what the user reads to decide whether to iterate on the draft
or move toward submission.

## Norms
- **Sequential means handoffs.** Do not create round-2's task before round-1's
  output exists. Each section builds on the previous one.
- **Honesty over spin.** The paper must match Phase 05's honest assessment. If
  the results don't support a claim, the paper doesn't make it.
- **The reviewer is an ally, not an enemy.** Their criticism makes the paper
  stronger. Surface weaknesses before submission, not during review.
- **A draft is a draft.** Don't over-polish. Get the structure and framing
  right first; prose polish comes later.
- If the user gave feedback, pass it through every round — especially framing decisions.
