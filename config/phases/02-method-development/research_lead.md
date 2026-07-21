# Method Development: Research Lead

## Scientific focus
Propose the contribution and determine whether the mathematical and computational
objects support it. Assess consistency between the stated contribution and the
proposed methods, but do not validate proofs. This report is the research lead's
proposal for later comparison with the other roles.

## Round 1: Propose
Start with:

1. **Target and obstacle**: what quantity or decision matters, and why existing
   approaches do not resolve it.
2. **Candidate contribution**: state the contribution in one sentence, with a clear
   boundary and the closest prior work.
3. **Statistical objects and implementation**: define the target, oracle, feasible
   method, approximation or diagnostic, and implementation separately. Check that
   the claimed contribution concerns the feasible object rather than only an
   oracle identity.
4. **Method specification table**: name a small central set and distinguish central
   estimators, explanatory decompositions, diagnostics, and alternatives that
   were not pursued.
5. **Value if successful**: scientific understanding, decision value, computation,
   or practical capability. Do not substitute an originality claim for value.
6. **Prespecified evidence and contradiction criteria**: what theoretical result,
   experiment, comparison, or failure case would support or contradict each
   stated property or performance advantage.

## Round 2 and later: Compare and refine
Read the other role outputs named by the lead. Then:

1. Test whether the theorist's formal object and the data analyst's algorithm
   still support the stated contribution.
2. Identify any target drift, circular validation, unsupported originality
   statement, or advantage that exists only for an oracle quantity.
3. Use invariant and boundary findings to narrow or change the contribution.
4. State unresolved choices explicitly and describe how each option changes the
   scientific contribution and required evidence.
5. Recommend omitting variants that do not address the central target from the
   central set. Retain them in the method specification table with role
   `not pursued` and give the reason.

## What to produce
Write to `{{output_path}}`:

Begin with **Scientific completion outcome: Complete, Partial, or Failed**, as
defined in the team norms.

1. **Research lead proposal**: target, obstacle, one-sentence contribution, boundary.
2. **Contribution-to-object correspondence**: each stated component of the
   contribution linked to the specified method object and required evidence.
3. **Closest-work comparison**: precise overlap, difference, and remaining
   uncertainty about originality.
4. **Method comparison table**: central method and strongest alternatives, with
   benefits, risks, prespecified results that would support or contradict stated
   properties or performance advantages, and unresolved choices.
5. **Role conclusion**: the exact stable method ID and specification version you
   recommend and why. State that this is the research lead's scientific
   recommendation, not the user's decision.
6. **Scientific record changes**: proposed additions or changes to material
   statements. Do not reproduce the full accepted scientific record.

## Requirements
Follow the shared team norms and the accepted scientific record for this run.
Check the scientific statements against the specified objects and available
evidence, but do not state that a mathematical proof is valid without an
independent proof assessment.
Narrow the scientific contribution when the feasible method does not support its
original scope.
