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
reports. Every role also reads the canonical current Phase 3 record, when one
exists, and the current cumulative Phase 4 synthesis, evidence index, and
knowledge fragment named in the run prompt.

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
the study. Note: the checkpoint is a tamper-evident seal, not a pause — the run
continues to the result stage automatically once the protocol is sealed, and
the user is not asked to approve it mid-run. A sealed checkpoint cannot be
amended; the only way to change the protocol is to cancel and rerun. Record
every later deviation and its reason. Exploratory analyses are allowed when
labeled as exploratory.

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
definition digest. Work only on that object. Another active method requires a
separate launch, and the Phase 2 catalog is read-only here.

The exact basis for every implementation and method-dependent computation is
the tuple `stable_id`, `version`, and `definition_sha256`. Matching the stable
ID alone is not enough. After a calculation-defining Phase 2 revision, earlier
scientific outputs and method implementations remain historical and are not
current evidence for the new version. The team judges the required repair or
recomputation during a user-initiated rerun.

Read the canonical current same-branch records enumerated in the run prompt. A
current Phase 3 result can supply proved predictions and assumptions. The Phase
4 evidence index supplies all retained artifacts and their current disposition;
its synthesis supplies the compact current interpretation; and its knowledge
fragment supplies the current empirical statements, their dependencies, and
their links to evidence. Do not reconstruct the empirical record from old run
summaries.

On a rerun, extend or repair the cumulative evidence by correcting a bug,
revalidating evidence after a calculation-defining version change, completing a
diagnostic, extending the study, strengthening uncertainty quantification,
adding a missing baseline, testing a failure regime, or addressing a theory and
experiment discrepancy. Existing artifacts remain immutable at their recorded
paths. You may update their disposition, but a non-current evidence ID never
returns to `current`. Revalidation or replacement creates a new run-local
evidence entry with a new ID.

## Files and outputs

Write all outputs under the exact run output root, normally
`branches/<stable_id>/draft/sections/run/NN/`:

- `round-01/<role>.md`, `round-02/<role>.md`, and `round-03/<role>.md` contain
  the ordered stage reports.
- Code, data summaries, figures, and reproducibility files live under the same
  run root at the exact paths recorded in the reports.
- Write the HTML summary to the exact path provided for this run.
- The research lead must leave the complete current synthesis at the exact path
  `empirical-synthesis.md` and the complete evidence index at the exact path
  `evidence-index.json` in the run output root.
- The research lead must also leave the complete structured empirical record at
  the exact path `knowledge-fragment.json` in the run output root.

Research Hub prepares all three run-root files from the verified current
package. The data analyst and theorist read them and report proposed changes.
They do not edit the run-root package. The research lead is its sole finalizer.

The evidence index is cumulative:

- retain every existing `evidence_id` and its immutable artifact identity;
- add one entry for each new artifact, with its project-relative path, SHA-256,
  size, source run ID, run scope, `evidence_type`, status, status reason, and
  whether it depends on the method definition;
- use only `current`, `outdated`, `superseded`, `withdrawn`, or `unresolved` as
  evidence statuses;
- classify code and scientific outputs of type `figure`, `model`, `report`,
  `result`, or `table` as method-dependent and bind them to the exact method
  identity;
- classify raw source `data`, generic `log`, `protocol`, or `other`
  infrastructure as reusable only when the status reason states why it is
  mathematically independent of the method calculation;
- when the method version changed, leave every exact-method prior entry
  `outdated`;
- if this run revalidates or replaces outdated evidence, append a new `current`
  entry whose artifact and `source_run_id` belong to this run, and mark the old
  entry `superseded` when the new evidence replaces it;
- never relabel an `outdated`, `unresolved`, `superseded`, or `withdrawn`
  evidence ID as `current`;
- do not repeat work already represented by `current` evidence unless a named
  scientific reason requires a new measurement.
- after rewriting `empirical-synthesis.md`, update the index's `synthesis`
  SHA-256 and byte size while leaving its exact path as
  `empirical-synthesis.md`.

Rewrite `empirical-synthesis.md` as a compact account of what the current method
does empirically. State the applicable evidence, outdated or unresolved
evidence, negative results, and changes from this run. It is not a chronological
run history.

Rewrite `knowledge-fragment.json` as the complete current set of empirical
statements and evidence links. Preserve the prepared method identity,
generation, and source run ID. Set `coverage` to `complete` for either a
Complete or Partial scientific outcome. Include every evidence ID exactly once
with the same status used in `evidence-index.json`. Reassess carried statements
when the method version changed, and retain only statements that describe
the current state of knowledge. Keep `lead_summary` compact and focused on the
method's fundamental empirical behavior, changes that affect user decisions,
and unresolved questions.

A valid Complete or Partial package becomes the branch's current empirical
package. A Failed or invalid run leaves the previous package current.

The final report states three judgments separately: whether the package matches
the exact current method, whether outdated or unresolved evidence requires
research attention, and whether the run's scientific outcome is Complete,
Partial, or Failed. None of these judgments substitutes for another.

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
  same exact `stable_id`, `version`, and `definition_sha256`;
- defer further work.

Phase 4 does not launch another phase and does not choose the user's next action.

## Files in this folder

- `_lead.md`: coordination and final synthesis instructions.
- `data_scientist.md`: prespecification, implementation, and experiment
  instructions.
- `theorist.md`: implementation and result audit instructions.
- `research_lead.md`: evidence reconciliation and recommendation instructions.
