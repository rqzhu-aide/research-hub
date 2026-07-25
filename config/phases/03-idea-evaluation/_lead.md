# Lead Instructions: Theoretical Development

Coordinate the theoretical development phase. Your job is to ensure the theorist
produces actual proved results (not ratings or sketches), the data analyst
provides a rigorous computability assessment, and the mathematical output is
synthesized into a coherent framework.

## Step 1: Read prior context
Read:
- `setting.md`
- the approved Phase 02 summary (method definitions and idea set)
- the approved Phase 01 summary (literature context)
- prior `evaluations/` runs

Identify the method to develop. If the user named one in the run-start form, use
it. If not, select based on Phase 2 outcomes and state the choice clearly.

## Step 2: Round 1 — independent development
Dispatch three independent tasks:

1. **Theorist**: derive and prove the main results for the selected method.
   Give them the full method definition and all prior context. They must produce
   actual theorems with full proofs — see `theorist.md` for deliverable
   requirements.

2. **Data analyst**: assess computational cost, implementation feasibility, and
   numerical stability. See `data_scientist.md`.

3. **You (research lead)**: identify the contribution structure — what the
   proved results mean, how they position against existing work, what the paper's
   narrative should be. See `research_lead.md`.

All three work independently. They do not wait for each other.

## Step 3: Debate round — cross-check
From round 2 onward, each role reads the others' work:

- The **data analyst audits the theorist's proofs**: are assumptions missing? Are
  steps unjustified? Is the scope correctly stated? This is a mathematical audit.
- The **theorist audits the analyst's cost claims**: is the per-step cost
  accurate? Are the numerical stability concerns correctly identified?
- The **lead reconciles**: identifies what is solid, what is conjectural, what
  needs more work. Flags unresolved disagreements for the user.

## Step 4: Final synthesis
Write the HTML summary to the exact path provided. Present:

1. **Proved results**: list each theorem with its statement, assumptions, and
   proof status (proved / conjectured with gap stated).
2. **Rate bound**: the key quantitative result, if applicable.
3. **Computational assessment**: cost, feasibility, stability.
4. **Cross-check outcomes**: what the audit found, what was revised.
5. **Open questions**: results that could not be proved, with the specific gap.

6. **Readiness assessment and recommendation.** Evaluate explicitly:

   a. **Is the theory sufficient to proceed to Phase 04?** Can the analyst
      implement the method and design experiments from what was proved? If yes,
      recommend proceeding and state what Phase 04 should test first.

   b. **Does the theory need improvement before Phase 04?** If the proofs are
      incomplete, the rate bound is loose, or the scope is unclear, recommend
      rerunning this phase with a specific focus (e.g., "close the gap in the
      invariance proof," "tighten the rate bound," "extend to non-Gaussian
      targets"). State exactly what needs to be proved.

   c. **Should a previous phase be rerun?** If the method definition from Phase 02
      is unclear, or the literature review from Phase 01 missed relevant work,
      recommend rerunning that phase with a specific focus (e.g., "Phase 02
      should clarify the interaction structure," "Phase 01 should survey
      non-reversible MCMC").

   d. **Is this method a dead end?** If the proofs reveal a fundamental obstacle
      (e.g., the interaction cannot preserve the invariant, the rate bound is
      worse than the baseline, the assumptions are unrealistic), recommend
      returning to Phase 02 to select a different method. State why this method
      is not viable.

   State the recommendation clearly as one of: **proceed**, **improve theory**,
   **return to Phase N**, or **dead end — select different method**. Justify with
   specific evidence from the proofs and cost analysis.

## Requirements
- The theorist MUST produce actual proofs. A run where the theorist only writes
  ratings or proof sketches is a Failed run, even if the ratings are insightful.
- The data analyst MUST produce an actual cost analysis with specific numbers
  (big-O, memory, comparison to baselines), not general statements.
- Every mathematical claim must be either proved (with a real proof) or stated
  as a conjecture with the gap identified.
- The cross-check is mandatory. If the data analyst's audit finds a gap in the
  theorist's proof, the theorist must either close it or restate as conjecture.
