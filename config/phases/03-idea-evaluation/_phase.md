# Phase: Theoretical Development

## Goal
Develop the **actual theoretical results** for the method selected in Phase 2 —
not just evaluate or rank ideas, but **carry out the proofs**. The theorist
derives the main theorems, lemmas, and rate bounds. The data analyst audits
computability: what is feasible to implement and what the computational cost
looks like. The lead synthesizes the mathematical results into a coherent
theoretical framework.

This phase produces **concrete mathematical deliverables**: proved theorems with
full proofs, stated assumptions, and clear scope. A proof sketch or a rating of
"the path is clear" is **not** a deliverable.

## Role division — who does the heavy lifting

| Role | Primary responsibility | Audit responsibility |
|------|----------------------|---------------------|
| **Theorist** | **Derive and prove** all main results: rate bounds, invariance, convergence | Audit the data analyst's computability claims |
| **Data Analyst** | **Assess** computational cost, implementation feasibility, numerical stability | Audit the theorist's proofs for gaps and unstated assumptions |
| **Research Lead** | **Synthesize** the theoretical framework, position the contribution, write the narrative | Ensure completeness — every claim has support |

Everyone evaluates from their own perspective, but the **theorist writes the proofs**
and the **data analyst writes the cost analysis**. The debate rounds are for
cross-checking, not for dividing proof work.

## Study structure
**Debate pattern.** All three roles work independently in round 1.

- **Round 1**: Theorist derives the main results independently. Data analyst
  assesses computability independently. Lead identifies the contribution
  structure independently.
- **Round 2+**: Cross-check round. The data analyst audits the theorist's proofs
  for missing assumptions or gaps. The theorist audits the analyst's cost claims
  for accuracy. The lead reconciles and identifies what remains unresolved.

## Required mathematical deliverables

The theorist **must** produce, at minimum:

1. **Main theorem(s)** — the central result(s) of the method. Full statement
   with all assumptions. Full proof — every step justified, no "the proof is
   standard."
2. **Supporting lemmas** — any intermediate results needed for the main theorem.
3. **Rate bound** (if applicable) — an explicit, quantitative bound on the key
   quantity (spectral gap, contraction rate, mixing time, asymptotic variance).
   The bound must be stated as a theorem with a proof, not as a conjecture.
4. **Invariance proof** (if applicable) — verification that the method preserves
   the target distribution, with all divergence corrections computed.
5. **Discretization analysis** (if applicable) — what happens when the
   continuous-time dynamics are discretized. Step-size conditions, error bounds.
6. **Scope and limitations** — explicit statement of where the results hold and
   where they break. Counterexamples where possible.

If a result cannot be proved, it must be stated as a **conjecture** with the
specific gap identified. "Near-certain" or "the path is clear" are not acceptable
— either prove it or conjecture it with the gap stated.

## Required computational assessment

The data analyst **must** produce, at minimum:

1. **Computational cost analysis** — per-step cost (time and memory) as a
   function of N (particles) and d (dimension). Compare to baselines.
2. **Implementation feasibility** — what is needed to implement this? What
   libraries, what data structures, what preprocessing?
3. **Numerical stability** — what can go wrong numerically? Conditioning,
   overflow, step-size restrictions.
4. **Audit of theorist's proofs** — read the proofs and identify any missing
   assumptions, unjustified steps, or gaps. This is a mathematical audit, not a
   re-derivation.

## Prior information
Requires a current Phase 02 summary approved by the user (contains the method
definition and the idea set). Phase 01 (literature review) is also provided for
positioning. The user may specify which idea to focus on in the run-start form;
if not, the lead selects based on Phase 2 outcomes.

**On rerun:** the prior Phase 03 run is provided as **comparison evidence** —
"here is what was proved before, and what remains open." The new run must
**improve on it**, not merely repeat it:

- **Close gaps**: if the prior run left conjectures or unstated gaps, the new run
  should attempt to close them — prove the conjectured results or state the
  gap more precisely.
- **Strengthen bounds**: if the prior rate bound was loose, derive a tighter one.
- **Extend scope**: if the prior proof held only under restrictive assumptions,
  relax them or identify what additional assumptions are needed.
- **Fix errors**: if the prior proof had gaps the audit identified, correct them.
- **Deepen the analysis**: if the prior cost analysis was incomplete, fill in
  the missing computations.

The prior run's proofs and assessments are starting material, not a constraint.
The new run should read them carefully and build on them. Re-proving the same
result from scratch without improvement is not useful.

## Files and outputs
Write all outputs under `evaluations/run/NN/`:

- `round-01/<role>.md`, `round-02/<role>.md`, ...: per-round reports
- Write the HTML summary to the exact path provided for this run.

Each role report begins with Complete, Partial, or Failed as defined in the team
norms.

## What the user decides
The user starts every run. After the theoretical development, the lead presents
the proved results, the assessment, and a recommendation. The user decides:

- to proceed to Phase 04 (Implementation & Experiments) with the proved method;
- to return to Phase 02 for additional method development;
- to request a revision (e.g., prove a specific result more rigorously);
- or to rerun with a different focus.

## Files in this folder
- `_lead.md`: instructions for the research lead.
- `theorist.md`: proof-development instructions.
- `data_scientist.md`: computational assessment instructions.
- `research_lead.md`: contribution positioning instructions.
