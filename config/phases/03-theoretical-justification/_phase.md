# Phase: Theoretical Justification

## Goal
Develop the mathematical proofs, bounds, and guarantees that make the proposed
method rigorous. Turn the method sketch from Phase 02 into theorems — what can
be proven, what must be assumed, and where the theory has limits.

## Gating
**Requires Phase 02 (Method Development) to be complete.** The lead reads the
method development summary before composing directives — you can't prove a
method that hasn't been specified. May also reference Phase 01's literature
review for related theoretical results to lean on.

## Pattern
**Sequential.** This is a handoff pipeline, not a parallel scan or a debate:
1. Theorist drafts the core proofs (round 1)
2. Research lead reviews for positioning, novelty claims, and gaps (round 2)
3. Theorist revises based on the review (round 3, if requested)

Each member takes the previous one's output as input. The lead creates tasks
one at a time — do NOT create them all at once.

## Folder
All outputs land in `draft/theory/run/NN/`:
- `round-01/theorist.md` — initial proof draft
- `round-02/research_lead.md` — review with positioning concerns
- `round-03/theorist.md` — revised proofs (if 3 rounds)
- Summary goes to `phase-summaries/03-theoretical-justification.html`

## Files in this folder
- `_lead.md` — how the research_lead runs a sequential theory pipeline. **Read first.**
- `theorist.md` — the proof-writing protocol
- `research_lead.md` — the review protocol (positioning, novelty, gaps)

## What success looks like
By the end of this phase, the project should have:
1. A main theorem (or theorem cluster) stating what's proven and under what assumptions
2. Tight assumptions — nothing assumed that isn't needed
3. Honest scope — what the theory covers, what it doesn't, what's conjectural
4. Positioning vs. existing theoretical results (from the literature review)

If a desired guarantee can't be proven, that's a valid outcome — but the lead
must state precisely what's proven, what's conjectured, and what's open.
