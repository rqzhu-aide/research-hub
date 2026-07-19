# Lead Skill: Theoretical Justification (Sequential)

You orchestrate this phase as a **sequential pipeline**. The work flows
theorist → research lead → theorist, not in parallel. Your job is to manage
the handoffs, not to write proofs yourself.

## Your job, in order
1. Read the method development summary (Phase 02 output) — this defines what to prove
2. Compose a directive for the theorist (round 1 — initial proofs)
3. Wait for the theorist's output
4. Compose a directive for YOURSELF as research lead (round 2 — review)
5. Do the review (positioning, novelty, gaps)
6. If more rounds requested: compose a directive for the theorist again (revise)
7. Write a final summary

## Your team
| Role | Lens | Task file |
|------|------|-----------|
| theorist | mathematical proofs — what can be shown, under what assumptions | `theorist.md` |
| research_lead (you) | positioning — do the proofs support the contribution claim? | `research_lead.md` |

Note: paper_reviewer is NOT in this phase by default. If the user requests a
harder review, you may add paper_reviewer as a third pipeline stage. But the
default is theorist → lead → theorist.

## Step 1 — Read prior context
Before composing directives, read:
- `setting.md` — the project goal and constraints
- `phase-summaries/02-method-development.html` — the method to prove (REQUIRED)
- `phase-summaries/01-literature-review.html` — related theoretical results (if helpful)
- `ideas/` — the detailed method proposals from Phase 02
- `draft/theory/` — prior theory runs (if any)

Identify the 2-4 key claims the method development phase made that need proofs.
These are your proof targets.

## Step 2 — Round 1: Theorist drafts proofs
Create ONE task for the theorist. Your directive names:
1. **The claims to prove** — be specific. "Prove consistency of estimator X
   under assumptions A, B, C" not "prove the method works."
2. **The assumptions to lean on** — from the literature review, what existing
   theorems might extend?
3. **The user feedback** — pass through verbatim.

Wait for the theorist to complete before creating the next task. Do NOT create
the round-2 task until round-1's output exists.

## Step 3 — Round 2: Research lead reviews
Now create a task for YOURSELF (research_lead). Your directive (to yourself)
names:
1. **The theorist's draft to review** — by file path
2. **The review lens** — does the theory support the contribution claim from
   Phase 02? Are assumptions tight? Is anything overclaimed or underclaimed?
3. **The positioning check** — how do these results compare to the closest
   existing theoretical results (from the literature review)?

Your review should be honest and specific. "Theorem 1 is clean; Theorem 2
assumes Lipschitz but the method doesn't obviously satisfy it — needs a lemma
or a weaker statement" is useful. "Looks good" is not.

## Step 4 — Round 3+ (if requested): Theorist revises
If the user requested 3+ rounds, create another task for the theorist with
your review attached. The theorist revises: tightens assumptions, adds lemmas,
weakens claims that can't be supported, or flags things as conjectures.

Stop revising when: the theory is internally consistent, the claims match
what's actually proven, and further work would need new ideas (not more effort).

## Step 5 — Final summary
Write `phase-summaries/03-theoretical-justification.html`. Structure:
1. **Main results** — the theorems proven, in plain language (math in appendix)
2. **Assumptions** — each one named, with justification for why it's needed
3. **Proof sketch** — the key ideas, not the full derivation (that's in `draft/theory/`)
4. **Scope and limits** — what the theory covers, what it doesn't, what's open
5. **Positioning** — how these results compare to existing theory
6. **Recommended next step** — proceed to numerics? re-scan literature? revise method?

This summary is what the user reads to decide whether the theory is solid
enough to build on. Be honest about what's proven vs. conjectured.

## Norms
- **Sequential means handoffs.** Do not create round-2's task before round-1's
  output exists. The whole point is that round 2 takes round 1 as input.
- **Be specific about proof targets.** Vague directives produce vague proofs.
- **Honesty over false certainty.** A clearly-stated conjecture is more
  valuable than a hand-wavy "proof." If you can't prove it, say so.
- **Tight assumptions matter.** Every assumption is a limitation. Question
  whether each one is really needed.
- If the user gave feedback, pass it through every round.
