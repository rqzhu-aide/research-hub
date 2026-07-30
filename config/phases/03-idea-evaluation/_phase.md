# Phase: Theoretical Development

## Goal
Develop rigorous theoretical results for one method explicitly chosen by the
user from the published Phase 2 catalog. Phase 2 is the prerequisite for this
phase. Phase 4 is a sibling phase, not a prerequisite: either phase may be
launched first for the same method branch.

The theorist derives the main mathematical results. The data analyst then tests
the proofs and assumptions against computational feasibility. The research lead
finally reconciles both reports into a defensible theoretical account.

This phase must produce concrete mathematical results: precise statements,
complete proofs when available, explicit assumptions, quantitative bounds, and
an honest account of unresolved gaps. A proof sketch or a judgment that a proof
"should work" is not a proved result.

## Role division and order

| Stage | Role | Primary responsibility |
|------|------|------------------------|
| 1 | **Theorist** | Derive theorems, lemmas, rate bounds, invariance results, and scope conditions |
| 2 | **Data Analyst** | Audit the proofs and quantify computational cost, feasibility, and numerical stability |
| 3 | **Research Lead** | Reconcile the mathematical and computational findings, position the contribution, and summarize unresolved issues |

The stages are sequential. The data analyst reads the theorist's current-stage
report before writing. The research lead reads both current-stage reports
before synthesizing. This is an ordered, cumulative scientific discussion, not
three independent assessments.

Each role reads the canonical current same-branch records supplied in the run
prompt. By default, the current Phase 3 theory manuscript and current Phase 4
empirical synthesis are the scientific starting point. Archived Phase 3 run
summaries are included only when the user explicitly selects that context option
at launch. Treat any included archive as background and never let it override a
newer current record. A current Phase 4 result may reveal a numerical failure,
implementation constraint, or useful conjecture. It may guide the theory, but
it does not replace a proof.

Each run also receives frozen Phase 3 and Phase 4 knowledge fragments when they
exist. These fragments are read-only launch evidence. They express the current
statements, dependencies, and unresolved questions with stable scientific
identifiers. Specialists cite those identifiers and propose changes in their
stage reports. Only the Stage 3 research lead writes the prepared run-root
`knowledge-fragment.json`.

## Required mathematical work

The theorist must address, when relevant:

1. **Main theorems.** State every assumption and give a complete proof. Each
   assumption should have a clear role in the argument.
2. **Supporting lemmas.** State and prove the intermediate results required by
   the main theorem.
3. **Rate bounds.** Give an explicit quantitative bound for the relevant
   convergence, estimation, optimization, or generalization quantity and
   compare it with an appropriate baseline.
4. **Invariance or identification.** Verify the claimed stationary,
   invariance, identifiability, or estimability property under stated
   conditions.
5. **Approximation or discretization.** State the numerical scheme, tuning or
   step-size conditions, and the resulting approximation error when the method
   requires them.
6. **Scope and failure cases.** State where the result applies, where it does
   not apply, and provide a counterexample when one is available.

If a result cannot be proved, label it as a conjecture and identify the exact
step, missing assumption, or mathematical tool needed to resolve it.

## Required computational assessment

The data analyst must address, when relevant:

1. **Computational complexity.** Give time and memory costs in the natural
   problem dimensions and compare them with appropriate baselines.
2. **Implementation feasibility.** Identify the operations, data structures,
   numerical solvers, and preprocessing required by the mathematical method.
3. **Numerical stability.** Examine conditioning, tuning restrictions,
   finite-precision behavior, and relevant low-sample or high-dimensional
   regimes.
4. **End-to-end statistical cost.** Relate per-iteration cost to the number of
   iterations, samples, or observations needed to attain a stated error or
   precision target.
5. **Proof audit.** Identify missing assumptions, unsupported inference steps,
   scope mismatches, and dimensional or asymptotic inconsistencies in the
   theorist's report.

The analyst should cite the exact theorem, equation, or proof step at issue. A
general expression of doubt is not an audit finding.

## Prior information and reruns

At launch, the user chooses one active method. The run freezes its stable ID,
version, canonical definition, and definition digest. Work only on that scientific
object. The Phase 2 catalog is read-only here. Another method requires a
separate launch.

The exact object of every proof and calculation is the tuple `stable_id`,
`version`, and `definition_sha256`. Matching the stable ID alone is not enough.
If Phase 2 advances the version after a calculation-defining change, work for
the earlier version remains historical. On a user-initiated rerun, verify every
carried theorem, lemma, assumption, and complexity result against the new
definition. Retain it only when the argument still applies; otherwise repair,
narrow, replace, or withdraw it. Do not transfer a proof merely because the two
versions appear similar.

Read the canonical current records enumerated in the run prompt. Read archived
Phase 3 summaries only when the prompt states that the user selected
`include_archived_summaries`. Preserve source status and distinguish proved
results, empirical findings, conjectures, interpretations, and unresolved
disagreements.

On a rerun, update the complete current theory manuscript by closing a proof gap,
strengthening a bound, relaxing an assumption, correcting an error, extending
the scope, or answering a discrepancy raised by Phase 4. The result is a
self-contained replacement, not a patch or an additional proof fragment. Prior
run files are immutable records and must not be edited.

The new knowledge fragment is likewise a complete checkpoint of the current
scientific account, not a change log. Preserve a stable statement ID when the
scientific statement remains the same. Revise its fields when its support,
scope, assumptions, or wording changes. Do not carry a withdrawn or superseded
statement as current.

## Files and outputs

Write all outputs under the exact run output root, normally
`branches/<stable_id>/evaluations/run/NN/`:

- `round-01/<role>.md`, `round-02/<role>.md`, and `round-03/<role>.md` contain
  the ordered stage reports.
- Write the HTML summary to the exact path provided for this run.
- The research lead must write the complete replacement theory manuscript to
  the exact path `theory-manuscript.md` in the run output root.
- The research lead must also write the complete current scientific checkpoint
  to `knowledge-fragment.json` in the run output root.

Research Hub prepares both run-root files from the verified current package when
the method identity matches. For a first run or revised method definition, it
prepares new templates. A Complete valid run atomically replaces the branch's
current Phase 3 package. An incomplete or invalid run leaves the previous
current theory package unchanged.

Before a Complete submission, `knowledge-fragment.json` must have complete
coverage, preserve its prepared identity fields, include every current
scientific statement and its dependencies, and give a compact lead summary of
the fundamental points, decision-relevant changes, and unresolved questions. A
Partial result may retain named scientific gaps, but its fragment must still be
structurally complete and state the current support and uncertainty explicitly.

Each report begins with Complete, Partial, or Failed as defined in the team
norms.

## What the user decides

The user starts every run and decides what happens after the lead presents the
results. The user may:

- launch or rerun Phase 4 for the same method, whether Phase 4 has run before or
  not;
- rerun Phase 3 to address a named theorem, assumption, or disagreement;
- launch Phase 3 or Phase 4 for another active method;
- rerun Phase 2 if the catalog definition itself must change;
- defer further work on the method.

Phase 3 does not launch Phase 4 and does not choose the user's next action.

## Files in this folder

- `_lead.md`: coordination and final synthesis instructions.
- `theorist.md`: proof-development instructions.
- `data_scientist.md`: proof-audit and computational-assessment instructions.
- `research_lead.md`: contribution and reconciliation instructions.
