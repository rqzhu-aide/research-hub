# Phase: Method Development

## Goal
Turn the literature evidence into a small, explicit set of methods the user can
choose to develop. Begin with the target and obstacle, not with a preferred
formula or technology.

For every candidate, define and distinguish:

- target estimand or scientific quantity;
- oracle procedure or quantity defined using information unavailable to the
  feasible method;
- feasible estimator or procedure;
- approximation or diagnostic quantities;
- the implementation and the quantity computed at each step.

Maintain a method specification table with a stable method ID and explicit
specification version. A method ID always denotes the same estimand,
mathematical definition, and algorithmic variant. Record each code implementation
and code version separately. Also record object type separately from its role in
the current proposal. Keep the central set small. Retain methods
that are not pursued in the table with role `not pursued` and state why they were
set aside.

## Prior information
This phase normally uses a current Phase 01 summary approved by the user. If that
summary is unavailable, the web UI identifies the missing prior evidence, but
the user may choose to proceed. The lead must then state what prior evidence is
unavailable. If an affected originality or prior-work statement is carried
forward unchanged from an accepted Phase 02 baseline, preserve its stable ID and
`Current` formulation state and propose only the warranted changes to assessment
status, evidential basis, source provenance, or uncertainty. Use formulation
state `Proposed` only for a new or materially reworded statement. Assess a
statement whose required evidence is unavailable as `Not assessable`, and record
the proposed changes under **Scientific record changes** for this run. For a
rerun, use a trusted
current approved Phase 02 result as the scientific baseline. Otherwise use a
current Phase 01 summary
approved by the user. Treat a stale Phase 02 result only as comparison evidence.
If neither current source is available, initialize a proposed scientific record
and say so explicitly. Role reports include a **Scientific record changes**
section. The final summary provides one consolidated **Scientific record
changes** section and the **Proposed scientific baseline**, which becomes
accepted only after user approval. It does not alter an earlier accepted record
before that decision.

## Study structure
Each role proposes a method independently in round 1. In later rounds, the roles
read and evaluate one another's proposals. The lead identifies agreement and
clearly distinguishes unresolved alternatives for the user. Attempt the number
of rounds selected by the user. Each role report begins with Complete, Partial,
or Failed as defined in the team norms. Partial and Failed reports preserve
usable work in a nonempty report and do not prevent the configured run from
continuing.

## Required scientific checks
Before recommending a method, the team must examine:

1. simple invariants and dimensional checks;
2. direct or indirect information leakage, inappropriate reuse of evaluation
   data, and use of target information;
3. circularity, including use of the method's own output or a data-dependent
   estimate derived from it as the reference for evaluating that method;
4. boundary cases and counterexamples;
5. mismatch between the mathematical object and its implementation;
6. prespecified results that would support or contradict each stated property or
   performance advantage.

## Files and outputs
Write all outputs under `ideas/run/NN/`:

- `round-01/<role>.md`, `round-02/<role>.md`, ...: proposals and comparisons
- Write the HTML summary to the exact path provided for this run and do not
  overwrite earlier summaries.

## Files in this folder
- `_lead.md`: instructions for the research lead.
- `theorist.md`, `research_lead.md`, `data_scientist.md`: role-specific
  instructions.

## Expected result
The phase summary reports:

1. a precise target and obstacle;
2. a method specification table with object definitions and implementation
   sketches;
3. a small central method set plus clearly identified alternatives that were not
   pursued;
4. one proposed **Method selection for downstream study**, stated by exact
   stable method ID and version and kept distinct from acceptance of the complete
   proposed scientific baseline;
5. prespecified evidence and contradiction criteria for each stated property or
   performance advantage of a central method;
6. unresolved design choices stated explicitly;
7. explicit options to approve, revise, rerun, designate an alternative for
   selection before approval, or
   return to literature review.

The final summary begins with the User Decision Brief and Comparison with the
approved run defined in the team norms. Follow the shared team norms and the
accepted scientific record for this run. Completing this phase reports the
proposed methods and names one proposed downstream selection. It does not make
or approve that selection on the user's behalf, and it does not start theory or
numerical studies. The user decides whether to approve the complete proposed
baseline and the separately named method ID and version.
