# Phase: Implementation and Experiments

## Goal

Implement one method explicitly chosen by the user from the published Phase 2
catalog and determine how it behaves empirically. Phase 2 is the prerequisite.
Phase 3 is a sibling phase, not a prerequisite: the user may run Phase 4
directly after Phase 2, before or after any Phase 3 run for the same method.

The data analyst does the primary empirical work. The theorist then audits the
implementation and interprets the results relative to the mathematical
definition and any available same-branch theory. The research lead finally
reconciles both reports into an honest empirical conclusion.

This phase must produce runnable code, recorded diagnostics, measured results,
and a reproducibility record. A description of experiments that were not run is
not an empirical result.

## Role division and order

| Stage | Role | Primary responsibility |
|------|------|------------------------|
| 1 | **Data Analyst** | Prespecify the study, implement the method, run the selected scope, and report measured results |
| 2 | **Theorist** | Audit correspondence between definition, code, assumptions, and results |
| 3 | **Research Lead** | Reconcile the empirical and mathematical assessments and summarize unresolved issues |

The stages are sequential. The theorist reads the analyst's current-stage
report, code references, and results. The research lead reads both current-stage
reports. Every role also reads the frozen prior Phase 3 and Phase 4 summaries
and discussion reports from the same method branch that are named in the run
prompt.

## Run scope

The two run modes change the scope of the empirical study only. They use the
same method-selection rule, the same three roles, and the same stage order.
Either mode may be launched directly after Phase 2. A comprehensive run does
not require a preliminary run.

### Preliminary study

A preliminary study establishes whether the method can be implemented and
whether its basic numerical behavior is scientifically credible. It should
include:

- a runnable implementation or a clearly isolated implementation extension;
- known-answer, invariant, unit, and reproducibility checks appropriate to the
  method;
- a small, focused empirical study in the most informative settings;
- measured values and uncertainty where replication is meaningful;
- a clear account of failures and constraints.

A preliminary study need not conduct a full benchmark suite, broad sensitivity
analysis, or publication-scale experiment.

### Comprehensive study

A comprehensive study develops the full empirical evidence needed for a paper.
It should include:

- a verified implementation, built directly from the Phase 2 definition or from
  an available same-branch implementation;
- strong and relevant baselines;
- prespecified primary and secondary outcomes;
- multiple scientifically relevant settings and stress tests;
- scaling and sensitivity analysis;
- uncertainty estimates and robustness checks;
- tables, figures, and a complete reproducibility record.

When a prior preliminary or comprehensive implementation is available, audit it
and build on it. Do not require such a prior run and do not repeat it without a
scientific reason.

## Prespecification

The data analyst owns the study protocol because the analyst works first. Before
examining the main results, record:

1. scientific questions and hypotheses;
2. primary and secondary outcomes;
3. datasets, targets, or simulation settings;
4. baselines and tuning rules;
5. sample sizes, replications, random seeds, and stopping rules;
6. uncertainty measures and planned comparisons;
7. results that would support, weaken, or contradict each claim.

Complete the protocol checkpoint before executing the result-producing part of
the study. Record every later deviation and its reason. Exploratory analyses
are allowed when labeled as exploratory.

## Required empirical work

The data analyst must provide, at the scope appropriate to the selected mode:

1. **Runnable implementation.** Record code paths and exact execution commands.
2. **Diagnostic evidence.** Report actual values, expected behavior, tolerances,
   and pass or fail conclusions.
3. **Empirical results.** Report measurements, uncertainty, and comparison with
   relevant baselines when the scope includes them.
4. **Failure analysis.** Record convergence failures, numerical instability,
   infeasible settings, and negative results.
5. **Reproducibility.** Record data provenance, preprocessing, random seeds,
   software versions, hardware when relevant, and commands.

The theorist must then assess:

1. whether the code implements the frozen Phase 2 mathematical definition;
2. whether the experimental settings satisfy the assumptions of any available
   same-branch Phase 3 results;
3. whether measured behavior is consistent with, outside the scope of, or in
   tension with those theoretical results;
4. whether a discrepancy is most plausibly due to theory, approximation,
   implementation, finite-sample behavior, or study design.

If no Phase 3 result exists, the theorist audits structural consistency with the
Phase 2 definition and labels unproved mathematical explanations as conjectures.

## Prior information and reruns

The run freezes the method's stable ID, version, canonical definition, and
content digest. Work only on that object. Another active method requires a
separate launch, and the Phase 2 catalog is read-only here.

Read all frozen prior same-branch Phase 3 and Phase 4 summaries and discussion
reports enumerated in the run prompt. A prior Phase 3 result can supply proved
predictions and assumptions. A prior Phase 4 result can supply code, empirical
findings, failures, and open design questions. Preserve disagreements and source
status rather than blending incompatible conclusions.

On a rerun, improve the scientific evidence by correcting a bug, completing a
diagnostic, extending the study, strengthening uncertainty quantification,
adding a missing baseline, testing a failure regime, or addressing a theory and
experiment discrepancy. Prior run files are sealed records and must not be
edited.

## Files and outputs

Write all outputs under the exact run output root, normally
`branches/<stable_id>/draft/sections/run/NN/`:

- `round-01/<role>.md`, `round-02/<role>.md`, and `round-03/<role>.md` contain
  the ordered stage reports.
- Code, data summaries, figures, and reproducibility files live under the same
  run root at the exact paths recorded in the reports.
- Write the HTML summary to the exact path provided for this run.

Each report begins with Complete, Partial, or Failed as defined in the team
norms.

## What the user decides

The user starts every run and decides what happens after the lead presents the
findings. The user may:

- rerun Phase 4 with preliminary or comprehensive scope;
- run or rerun Phase 3 for the same method to address a mathematical question;
- launch Phase 3 or Phase 4 for another active method;
- rerun Phase 2 when the canonical method definition must change;
- proceed to Phase 5 only after both Phase 3 and Phase 4 have completed for the
  same method identity;
- defer further work.

Phase 4 does not launch another phase and does not choose the user's next action.

## Files in this folder

- `_lead.md`: coordination and final synthesis instructions.
- `data_scientist.md`: prespecification, implementation, and experiment
  instructions.
- `theorist.md`: implementation and result audit instructions.
- `research_lead.md`: evidence reconciliation and recommendation instructions.
