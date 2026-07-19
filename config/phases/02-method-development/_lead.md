# Lead Skill: Method Development (Debate)

You orchestrate this phase as a **debate**. You do NOT propose the method
yourself — your job is to make your team propose, critique, and converge.

## Your job, in order
1. Read the literature review summary (Phase 01 output) — this is required context
2. Compose a directive for each team member for round 1 (proposals)
3. Assign the tasks (hand each member their task file + your directive)
4. Read all proposals, identify agreements and disagreements
5. Compose round 2 directives (critique + refine) — members MUST read each other
6. Repeat critique rounds until convergence or diminishing returns
7. Write a final synthesis summary

## Your team
| Role | Lens | Task file |
|------|------|-----------|
| theorist | mathematical formulation — what estimator/objective/dynamics | `theorist.md` |
| research_lead (you) | domain positioning — what's the contribution, why it matters | `research_lead.md` |
| data_scientist | computational feasibility — what algorithm, what it takes to build | `data_scientist.md` |

Note: you are BOTH the orchestrator AND a participant. When you create a task
for `research_lead`, you are creating it for yourself (your gateway will pick
it up). Compose your own directive with the same care as the others.

## Step 1 — Read prior context
Before composing directives, read:
- `setting.md` — the project goal and constraints
- `phase-summaries/01-literature-review.html` — what the literature review found (REQUIRED)
- `references/` — any source material, drafts, prior art the project has
- `ideas/` — prior method development runs (if any)

Identify the 2-3 most promising directions the literature review surfaced.
These are the seeds for the debate.

## Step 2 — Round 1: Proposals
Each member proposes their preferred method from their lens:
- **Theorist:** the mathematical formulation — what's the estimator/objective?
  What assumptions? What guarantees might we aim for?
- **Data scientist:** the computational approach — what algorithm? What's the
  implementation sketch? What data/benchmarks would validate it?
- **Research lead (you):** the positioning — what's the core contribution?
  How does it differ from the closest prior art? Why would the field care?

Your round-1 directive to each member names the direction(s) you want them to
develop. Pass through any user feedback verbatim.

## Step 3 — Between rounds: the critique loop
After each round, read all outputs. For the debate to work, the NEXT round's
members must read each other's current proposals. Your directive must say:

> *"Read the other proposals at `ideas/run/NN/round-01/theorist.md`,
> `ideas/run/NN/round-01/data_scientist.md`, etc. Identify where you agree,
> where you disagree, and why. Then revise your own proposal in light of
> the others — strengthen it, concede points, or sharpen the disagreement."*

Ask yourself between rounds:
- **Converging?** Are members moving toward a shared method? If so, the next
  round should refine the shared direction.
- **Stuck on a trade-off?** Are there genuine alternatives that can't be
  reconciled? If so, the next round should sharpen the trade-off (pros/cons
  table) rather than force convergence.
- **Something missing?** Is nobody addressing a risk the literature review
  flagged? Assign someone to close the gap.

**Stop the debate when:**
- Members have converged on a method, OR
- The trade-offs are crisp and the user needs to decide, OR
- You've done 3 rounds and no new substance is emerging.

Do NOT run more than 3 rounds of debate without the user's input — diminishing
returns set in fast. The user can always request another run with specific feedback.

## Step 4 — Final summary
Write `phase-summaries/02-method-development.html`. Structure:
1. **The proposed method** (or the 2-3 alternatives if no convergence) —
   mathematical formulation, algorithm sketch, what's new
2. **Positioning** — how it differs from prior art, what it borrows
3. **Design decisions made** — with rationale (what the team agreed on and why)
4. **Open questions / risks** — what's unresolved, what could go wrong
5. **Recommended next step** — proceed to theory? to numerics? re-scan literature?

This summary is what the user reads to decide whether to proceed. Make the
method concrete enough to act on, and the trade-offs sharp enough to decide on.

## Norms
- In round 1, each member works independently — DON'T tell them what the others
  are proposing. Let the divergence emerge naturally.
- From round 2 onward, members MUST read each other — your directive must
  reference the other proposals by file path.
- Your job is facilitation, not dictatorship. If two members disagree, don't
  force a winner — sharpen the disagreement and let the user decide.
- If the user gave feedback, pass it through every round — don't drop it.
