# Phase: Theoretical Analysis

## Goal
Determine the estimand targeted by the selected method, whether it is identified
under the stated statistical model, observed-data structure, design, and
assumptions, the mathematical mechanism underlying the method's behavior, and
the conditions under which it succeeds or fails. Assess each theoretical
statement using the shared support vocabulary.

The analysis should characterize the target, bias, approximation, or structural
boundary. A convergence statement that assumes the essential error terms vanish
does not provide an adequate explanation.

## Prior information
A standard theory plan normally uses an approved, current Phase 02 run. The web UI
indicates when that information is missing or out of date, but the user may
choose to continue. In that case, the lead must state the exact method ID,
version, and specification analyzed. For each methodological statement whose
correspondence cannot be established, preserve the stable ID and `Current`
formulation state when its
accepted wording and scope are unchanged, and propose only warranted changes to
assessment status, evidential basis, source provenance, or uncertainty. Use
formulation state `Proposed` only for a new or materially reworded statement.
Assess unavailable correspondence as `Not assessable` under Scientific record
changes for this run.

For a standard theory plan, read the approved Phase 02 **Method selection for
downstream study** and use its exact stable method ID and version. Do not infer a
selection from a recommendation, ranking, or method table. If no exact selection
is recorded, state that the method selection is missing. Analyze a method
supplied explicitly by the user for this run only after identifying its exact ID
and version and disclosing that it is not the recorded Phase 02 selection. An
audit-only plan instead uses only its selected frozen source as defined below.

For a rerun, import the accepted scientific record from a trusted, current
approved Phase 03 result. A stale Phase 03 result is comparison only. When no
trusted Phase 03 record exists, use a user-approved, current Phase 02 record.
Otherwise initialize a proposed scientific record and state that no approved
baseline is available. Role reports propose changes to the scientific record.
The final summary provides one consolidated set of Scientific record changes
and a Proposed scientific baseline without
modifying an earlier approved summary.

## Study structure
**Sequential, with one plan selected by the user before launch.** The web UI
offers exactly three plans:

1. **Standard theory, 3 stages**: the theorist drafts the analysis, the research
   lead assesses its relation to the research claims, and the theorist revises
   the analysis.
2. **Standard theory plus audit, 4 stages**: run the same three stages, then ask
   the paper reviewer to audit the exact final theorist artifact.
3. **Audit existing theory only, 1 stage**: ask the paper reviewer to audit an
   existing sealed final theorist artifact selected by its source run ID. Do not
   repeat or revise the theory in this plan.

The selected plan is frozen for the run. Begin each stage only after the
preceding role has returned a nonempty report declaring Complete, Partial, or
Failed. A nonempty Partial or Failed report does not block the next configured
stage. Use its supported content and mark conclusions that depend on missing
work as Not assessable. A missing or unreadable artifact is a technical failure,
not a scientific Failed outcome; do not begin the next stage. Do not reorder,
parallelize, add, or remove stages from the selected plan.

For either audit plan, a separate paper reviewer receives a frozen copy of the
exact final theory artifact, its SHA-256, and only the sealed mathematical
evidence authorized for that audit. The audit scope identifies the selected
statement IDs and exact wording, proof locations, assumptions, dependency
sources, and recorded hashes. The reviewer does not receive a prior
research-lead preference as mathematical evidence, assesses the mathematical
target before its mapping to scientific claims, and does not edit the theory.
The audit-only run reports an audit-scoped outcome and then stops for the user's
decision.

## Required theoretical analysis
- Begin with the scientific questions to be answered, not with a target number of
  theorems.
- State the dependency structure among the results before writing the proofs.
- State the mathematical role of every assumption and determine whether an
  assumption already implies the conclusion of interest.
- For every mathematical result, record logical status, result type, assumptions,
  and scope as defined in the shared norms. Assign the associated scientific
  statement one assessment status from the shared vocabulary.
- Identify the indispensable lemmas and proof steps for the principal result and
  separate them from supplementary results.
- Examine boundary cases and construct counterexamples where possible.
- Do not conceal a proof gap by changing a definition, estimand, or assumption.
- Distinguish statements about the oracle, population quantity, feasible
  estimator, and finite numerical implementation.
- In a standard theory run, identify central results for which a later
  independent proof audit would materially affect the scientific conclusion.
  The research lead does not certify proofs.
- Follow the shared team norms and accepted scientific record for this run.

## Folder
All outputs land in `draft/theory/run/NN/`:

- `round-01/theorist.md`: initial theory and proof draft
- `round-02/research_lead.md`: assessment of results, the proposed contribution,
  and prior theory
- `round-03/theorist.md`: revised theory and updated scientific assessments
- `round-04/paper_reviewer.md`: independent audit after a standard three-stage
  theory run, when that plan is selected
- `round-01/paper_reviewer.md`: independent audit of an existing sealed final
  theorist artifact, when the audit-only plan is selected
- Write the HTML summary to the path provided for this run and preserve that
  version unchanged after submission.

## Files in this folder
- `_lead.md`: instructions for coordinating the selected three-stage,
  four-stage, or audit-only plan.
- `theorist.md`: instructions for theoretical analysis and proofs.
- `research_lead.md`: instructions for evaluating the relation between results
  and research claims.
- `paper_reviewer.md`: instructions for either independent proof-audit plan.

## Expected scientific output
The phase summary reports:

1. a small set of results tied to explicit scientific questions;
2. the dependency structure among the results and the indispensable lemmas and
   proof steps for the principal result;
3. the role and necessity of each assumption and the regimes it excludes;
4. logical status, result type, assumptions, scope, and assessment status
   recorded as distinct properties;
5. counterexamples or boundary cases that define the scope of each claim;
6. explicit options to approve, revise, rerun, narrow the method, or return to
   literature review;
7. when selected by the user, the independent audit findings for the exact
   final theory artifact and an audit-scoped completion outcome; otherwise,
   central results for which a later audit may be useful, with exact statement
   IDs and proof locations.

The user starts every run and makes every approval or rerun decision. Completing
this phase does not constitute independent proof checking unless the user
selected and completed an audit plan. Even then, the audit applies only to the
named results and recorded checks. Audit Complete means that all prespecified
checks for those results were performed, not that the whole theory was certified
or that no defect exists. In a four-stage run, a Partial or Failed audit normally
makes the phase outcome Partial while preserving usable theory. In an audit-only
run, Complete, Partial, and Failed describe only the specified audit work and do
not reclassify unaudited results. The phase never
starts numerical validation automatically. The final summary begins with the
User Decision Brief and places the Comparison with the approved run and phase
completion outcome next. It includes the consolidated Scientific record changes
and complete Proposed scientific baseline defined in the team norms.
