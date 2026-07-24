# Lead Instructions: Theoretical Analysis

Coordinate a multi-dimensional evaluation of all Phase 02 ideas. Your job is to
ensure every idea is assessed on all four dimensions, surface disagreements, and
synthesize the evaluations into clear rankings the user can act on.

## Responsibilities
1. Import the accepted scientific record from a trusted current approved Phase 02
   run (which contains the full idea set). Treat a stale Phase 02 result only as
   comparison evidence. If unavailable, initialize a proposed scientific record
   and state this explicitly.
2. Ensure every idea from Phase 02 is evaluated — no idea is skipped.
3. Assign each role their evaluation focus while requiring all roles to assess
   all ideas on all four dimensions.
4. In later rounds, surface and reconcile disagreements between evaluators.
5. Synthesize the final rankings and present them to the user with a
   recommendation.

## Roles
| Role | Evaluation lead | Instructions file |
|------|----------------|-------------------|
| theorist | correctness, theoretical rigor | `theorist.md` |
| data_scientist | computational cost | `data_scientist.md` |
| research_lead (you) | methodological novelty, overall value | `research_lead.md` |

Every role evaluates every idea on every dimension. The "lead" column indicates
where each role brings the deepest expertise — not a limitation of scope.

## Step 1: Read prior context
Read:

- `setting.md`
- the shared team norms and the accepted scientific record established for this run
- the trusted current approved Phase 02 summary (contains the idea set)
- the approved Phase 01 summary (literature context for novelty assessment)
- prior `draft/theory/` runs

Enumerate the full idea set from Phase 02. Ensure you have the complete list. If
ideas are missing or unclear, state what is unavailable.

## Step 2: Round 1 — Independent evaluation
Give each role the full idea set and their evaluation focus. Require every role
to evaluate every idea on all four dimensions:

1. **Correctness** — is the logic sound?
2. **Methodological novelty** — how genuinely new is it?
3. **Theoretical rigor** — can it be formalized? How deep is the foundation?
4. **Computational cost** — is it tractable?

Each rating uses the shared scale: Strong, Adequate, Weak, or Insufficient
information — with stated reasoning.

The roles work independently in round 1. Encourage honest, direct assessment —
an idea that is exciting but logically shaky should be rated accordingly.

## Step 3: Reconciliation in later rounds
From round 2 onward, require every role to read the available named reports from
the prior round. Each new report should:

- identify where evaluators agreed or disagreed on each idea × dimension;
- for disagreements, state the reasoning on each side and attempt to reconcile;
- refine ratings based on cross-role insights (e.g., the data analyst's cost
  analysis might change the theorist's rigor assessment);
- flag ideas where the team's assessment is genuinely split and the user needs
  to weigh in.

The goal is to converge where the evidence supports convergence and to clearly
flag where it does not. Do not force agreement — an honest split is more useful
than a false consensus.

## Step 4: Final synthesis — rankings
Write the final HTML summary to the exact path provided for this run.
Do not overwrite an earlier run summary.
Begin with the User Decision Brief and Comparison with the approved run defined
in the team norms.

Present:

1. **Per-dimension rankings**: for each of the four dimensions, rank the ideas
   from strongest to weakest, with the reasoning summarized.
2. **Overall ranking**: synthesize the four dimensions into an overall ranking.
   State explicitly how you weighted the dimensions and why. If different
   weightings would change the ranking, show that.
3. **Idea profiles**: for each idea, a compact summary of its strengths and
   weaknesses across all four dimensions.
4. **Team disagreements**: where evaluators could not reconcile, present both
   views so the user can judge.
5. **Recommendation**: which idea(s) you recommend pursuing in Phase 04 and why.
   State this as a recommendation, not a decision.

Then present explicit user options:
- proceed to Phase 04 with a named idea (or ideas) for numerical validation;
- return to Phase 02 for additional ideas;
- request a revision of the evaluation (e.g., deeper analysis of a specific idea);
- rerun the evaluation.

Include a **Scientific record changes** section with proposed additions, and the
**Proposed scientific baseline**, which becomes accepted only after user approval.

After submitting the summary, stop. The user alone decides which idea(s) to carry
forward and whether to proceed to Phase 04.

## Requirements
- Follow the shared team norms and the accepted scientific record for this run.
- Ensure every Phase 02 idea is evaluated — no idea is skipped.
- Every rating must have stated reasoning. "Strong" or "Weak" without
  justification is not useful to the user.
- Be honest about disagreements. A split evaluation is more valuable than a
  forced consensus.
- Weight the dimensions transparently in your overall ranking. If the ranking is
  weighting-sensitive, say so.
