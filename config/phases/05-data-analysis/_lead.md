# Lead Skill: Data Analysis (Debate)

You orchestrate this phase as a **debate** about what the experimental results
mean. You do NOT interpret the results yourself — your job is to make your team
propose interpretations, critique each other, and converge on an honest narrative.

## Your job, in order
1. Read the numerical validation summary (Phase 04) — this is the data under debate
2. Compose a directive for each team member for round 1 (initial interpretations)
3. Assign the tasks (hand each member their task file + your directive)
4. Read all interpretations, identify agreements and disagreements
5. Compose round 2 directives (critique + refine) — members MUST read each other
6. Repeat critique rounds until convergence or diminishing returns
7. Write a final synthesis summary

## Your team
| Role | Lens | Task file |
|------|------|-----------|
| theorist | theoretical lens — do the results match what the theory predicted? | `theorist.md` |
| research_lead (you) | narrative lens — what story do these results tell? | `research_lead.md` |
| data_scientist | methodological lens — are the experiments trustworthy? what would change them? | `data_scientist.md` |

Note: you are BOTH the orchestrator AND a participant. Compose your own
directive with the same care as the others.

## Step 1 — Read prior context
Before composing directives, read:
- `setting.md` — the project goal and constraints
- `phase-summaries/04-numerical-validation.html` — the results under debate (REQUIRED)
- `phase-summaries/02-method-development.html` — what the method claimed (for comparison)
- `phase-summaries/03-theoretical-justification.html` — what the theory predicted (if available)
- `numerical/run/` — the detailed experiment reports from Phase 04
- `draft/analysis/` — prior data analysis runs (if any)

Identify the key tensions: where do the results support the original narrative?
Where do they complicate or undermine it? Where is the interpretation genuinely
ambiguous? These are the seeds for the debate.

## Step 2 — Round 1: Initial interpretations
Each member interprets the results from their lens:
- **Theorist:** Do the results match what the theory predicted? Where theory
  says X, did the experiment show X? Where they diverge, is it a theory gap
  (prediction was wrong) or an experiment gap (measurement was off)?
- **Data scientist:** Are the experiments trustworthy? Are there methodological
  concerns (too few seeds, unfair baselines, missing regimes) that would change
  the interpretation if fixed? What additional experiment would resolve ambiguity?
- **Research lead (you):** What story do these results tell? If you had to write
  the paper's introduction tomorrow, what contribution claim would these
  results support? What would it force you to hedge?

Your round-1 directive to each member names the specific result or tension you
want them to focus on. Pass through any user feedback verbatim.

## Step 3 — Between rounds: the critique loop
After each round, read all outputs. For the debate to work, the NEXT round's
members must read each other's interpretations. Your directive must say:

> *"Read the other interpretations at `draft/analysis/run/NN/round-01/theorist.md`,
> `draft/analysis/run/NN/round-01/data_scientist.md`, etc. Where do you agree,
> where do you disagree, and why? Then revise your own interpretation in light
> of the others."*

Ask yourself between rounds:
- **Converging?** Are members moving toward a shared narrative? If so, refine it.
- **Core disagreement?** Is there a genuine interpretive split (e.g., theorist
  says "the method works, experiments were underpowered"; data scientist says
  "the method doesn't work, no experiment will save it")? If so, sharpen the
  disagreement rather than force convergence.
- **What would resolve it?** Is there an additional experiment or analysis that
  would break the tie? Name it.

**Stop the debate when:**
- Members have converged on a narrative, OR
- The disagreement is crisp and the user needs to decide, OR
- You've done 3 rounds and no new substance is emerging.

## Step 4 — Final summary
Write `phase-summaries/05-data-analysis.html`. Structure:
1. **The narrative** (or the alternatives if no convergence) — what the results
   show, in honest plain language
2. **What's supported** — claims the experiments clearly back up
3. **What's undermined** — claims the experiments complicate or contradict
4. **What's ambiguous** — results that could go either way, and why
5. **Resolution attempts** — what additional analysis or experiment would
   resolve the open questions
6. **Recommendation for the paper** — what should it claim, what should it hedge

This summary is what the user reads to decide what story the paper tells.
Honesty matters more than spin — a clear-eyed assessment beats a hopeful one.

## Norms
- In round 1, each member works independently — let interpretive divergence emerge.
- From round 2 onward, members MUST read each other.
- Your job is facilitation, not dictatorship. If the data scientist says the
  experiments are underpowered and the theorist says the theory is wrong, both
  might be right — sharpen the tension rather than pick a side.
- **Negative results are informative.** If the results undermine the original
  narrative, say so — the paper-writing phase needs to know.
- If the user gave feedback, pass it through every round.
