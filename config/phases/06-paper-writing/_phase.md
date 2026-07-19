# Phase: Paper Writing

## Goal
Compile the project's findings into a coherent manuscript. Turn the theory,
experiments, and analysis into a paper — introduction, method section, results,
discussion — that honestly represents what the project found.

## Gating
**Requires Phase 05 (Data Analysis) to be complete.** The lead reads the data
analysis summary before composing directives — the paper's framing must match
what the results actually support, not what the team originally hoped.

## Pattern
**Sequential.** This is a drafting pipeline with a review stage:
1. Research lead drafts the narrative spine + introduction (round 1)
2. Theorist drafts the theory section, grounded in the intro's framing (round 2)
3. Data scientist drafts the experiments + results section (round 3)
4. Paper reviewer reviews the complete draft for coherence, gaps, and honesty (round 4)

For fewer rounds, the lead may combine sections or skip the review stage.
For more rounds, the reviewer's feedback flows back to section authors.

## Folder
All outputs land in `draft/run/NN/`:
- `round-01/research_lead.md` — narrative spine + introduction
- `round-02/theorist.md` — theory section
- `round-03/data_scientist.md` — experiments + results section
- `round-04/paper_reviewer.md` — review of the complete draft
- Summary goes to `phase-summaries/06-paper-writing.html`

The assembled manuscript (if the lead chooses to compile one) goes in `draft/`.

## Files in this folder
- `_lead.md` — how the research_lead runs a drafting pipeline. **Read first.**
- `research_lead.md` — narrative spine + introduction protocol
- `theorist.md` — theory section protocol
- `data_scientist.md` — experiments + results section protocol
- `paper_reviewer.md` — review protocol

## What success looks like
By the end of this phase, the project should have:
1. A coherent draft manuscript (or section-by-section drafts) with a clear narrative
2. Honest framing — claims match what the results support (per Phase 05)
3. A review that identifies what's strong, what's weak, and what needs work
4. A clear path to submission (or a clear statement of what's blocking)

The goal is a draft, not a finished paper. Polishing happens after the user
reviews and decides what to prioritize.
