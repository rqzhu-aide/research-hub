---
sidebar_position: 5
title: "Phase 4: Implementation & Experiments"
slug: /workflow/phase-4
---

# Phase 4: Implementation & Experiments

Phase 4 asks whether a selected Phase 2 method can be implemented correctly and
what its computational and empirical behavior supports, qualifies, or
contradicts. It produces executable code, diagnostic evidence, and an empirical
study whose design and deviations can be inspected.

## Before you launch

Phase 4 can begin directly after Phase 2. It does not require a Phase 3 run. The
Phase 4 launch form shows the Phase 2 method catalog as a read-only list. Retired
or invalid entries remain visible for context but cannot be selected. Choose an
active method to inspect its summary, mathematical definition, assumptions,
status, and version before launching.

The chosen method's `stable_id`, `version`, and `definition_sha256` are frozen
for the run. This tuple identifies the exact calculation. The run receives the
current Phase 3 theory when available and the cumulative Phase 4 package. The
new Phase 4 record states the exact Phase 3 semantic basis available at launch.
If Phase 3 is absent, that absence is recorded and empirical work proceeds from
the Phase 2 definition. A legacy record without an explicit basis stays yellow
until Phase 4 is rerun.

Each stage keeps its report, code, data, tables, figures, and other supporting
evidence inside its assigned run folder. Research Hub inventories and hashes
these files when the stage finishes. Later runs use the cumulative evidence index
to locate applicable artifacts instead of loading every older run folder. If the
method definition changes in a calculation-defining way, the version advances
and prior exact-method evidence is marked outdated. A later run records
recomputation or revalidation as a new current evidence entry instead of
reactivating the old evidence ID.

Code and scientific outputs, including figures, models, reports, results, and
tables, are always bound to the exact method version that produced them. Raw
source data and generic logs, protocols, or other infrastructure may remain
reusable only when the record states why they are mathematically independent of
the changed calculation. The team decides during a rerun whether the necessary
repair is small or substantial.

| Run mode | Scope | Main result |
|---|---|---|
| **Preliminary** | Initial implementation, focused diagnostics, and limited experiments that address the question you specify. | A working implementation, diagnostic evidence, and a bounded empirical assessment. |
| **Comprehensive** | Full implementation, benchmarking, uncertainty analysis, robustness checks, and sensitivity analysis. | A complete comparison study and a scientific audit of the method's empirical behavior. |

Preliminary and comprehensive are alternative scopes for a run. Either can be
launched directly. A comprehensive run does not require a preliminary run, and
a preliminary result is not treated as an automatic instruction to launch a
comprehensive study.

Before either run, use your instructions to identify the scientific question and
the evidence that would change your view. Specify as much of the following as
the selected scope permits:

- primary and secondary outcomes;
- data sources or simulation regimes;
- target populations, parameter settings, and exclusion rules;
- baselines and a fair tuning budget;
- sample size or number of simulation replications;
- random seeds or a seed-generation rule;
- uncertainty summaries and stopping rules;
- train, validation, and test separation;
- analyses that are confirmatory for this run and analyses that are exploratory.

At the start of the analyst stage, the Data Analyst records a **prespecified
protocol**. Research Hub seals this checkpoint before the main result work
continues. Here, prespecified means that the protocol is recorded before those
results are examined. It is not a public preregistration and should not be
represented as one.

Launching Phase 4 starts only this run. It does not make a scientific judgment
about the code or results, and it does not start Phase 3 or Phase 5.

## What the team does

Both scopes use the same fixed three-stage, cumulative discussion. The Data
Analyst performs the primary implementation and empirical work.

1. **Data Analyst.** Records the protocol, implements the selected method,
   verifies it on known-answer and failure cases, and conducts the diagnostics
   and experiments appropriate to the chosen scope. The analyst records data,
   code, settings, uncertainty, and every material protocol deviation.
2. **Theorist.** Reads the analyst's report and artifacts, checks correspondence
   with the frozen method definition, examines whether assumptions and
   theoretical predictions apply to the implemented procedure, and investigates
   discrepancies, edge cases, and possible counterexamples.
3. **Research Lead.** Reads both reports, integrates the empirical and
   theoretical assessments, distinguishes confirmatory from exploratory
   findings, and states what the evidence supports, contradicts, or leaves
   unresolved.

All three roles receive the frozen method, current theory manuscript when
available, and current cumulative empirical package. Within the current run,
each later stage receives the reports from earlier stages. The lead preserves
material objections, responses, protocol deviations, and unresolved
disagreements. If an earlier role needs to respond again, carry the issue into a
rerun with focused instructions.

### Preliminary scope

The analyst emphasizes a correct working implementation, known-answer tests,
invariant checks, reproducibility checks, numerical diagnostics, and focused
experiments. The summary states what has been learned within this limited scope
and what remains necessary for broader conclusions.

### Comprehensive scope

The analyst emphasizes a full comparison study with relevant baselines,
repeated measurements, uncertainty, sensitivity analyses, and robustness
checks. Existing same-branch code or evidence may be reused only when its
identity and relevance are clear. The comprehensive report does not assume that
a preliminary run exists.

## Evidence you should receive

The evidence should be sufficient for another researcher to understand what was
run, reproduce the main analysis where access permits, and judge whether the
reported comparisons answer the stated question.

### Implementation and provenance

- executable code that corresponds to the selected method version;
- dependency and environment information;
- commands or scripts used to produce the main results;
- data origin, version, access conditions, preprocessing, and derived variables;
- a record of code changes and protocol deviations that affect interpretation.

### Design and diagnostics

- known-answer cases, invariants, unit tests, and numerical stability checks;
- the sampling or simulation unit and the intended unit of inference;
- sample-size or replication rationale;
- seeds and independent replications;
- missing-data handling, exclusions, and sensitivity analyses;
- separation of training, tuning, validation, and evaluation data to prevent
  leakage;
- baseline definitions, tuning procedures, compute budgets, and stopping rules
  that make comparisons fair.

### Results and uncertainty

- measured results rather than placeholders or expected values;
- effect estimates, variability, uncertainty intervals, Monte Carlo error, or
  other summaries appropriate to the design;
- raw or minimally processed result tables that support the figures;
- negative, null, unstable, and failed results;
- a comparison between theoretical predictions and empirical behavior, with
  discrepancies investigated rather than hidden.

For biological studies, the record should additionally distinguish biological
from technical replication, identify the experimental unit, address batches and
known confounders, and avoid treating repeated measurements on the same
biological unit as independent samples.

## How to read the status

The Phase 4 page reports three different scientific questions separately:

1. **Method applicability:** does the current package use the exact current
   `stable_id`, version, and definition digest?
2. **Research attention:** how many evidence entries are outdated or unresolved
   and therefore need reanalysis, revalidation, or an explicit limitation?
3. **Scientific outcome:** did the authorized Phase 4 work finish as Complete,
   Partial, or Failed under the selected scope?

A package can match the current method and still contain weak, negative, or
inconclusive evidence. A Complete run can still require research attention, and
a Partial run can contain valid current results. Read these fields separately
before deciding whether to rerun.

## Scientific standards and application checks

The items above are **scientific completion standards for the agents**. They
define what a credible Phase 4 result should contain. A technical run can finish
even when one of these scientific standards is not met, so you must review the
evidence.

Research Hub separately freezes and hashes the declared launch inputs, prompt,
and manifest, and records submitted artifacts. The shipped Phase 4
configuration enables a protocol checkpoint: the analyst's protocol is sealed
before the main result work proceeds. The checkpoint is a machine-sealed
provenance record, not a user approval gate — the run proceeds to the result
stage automatically once the protocol is sealed, and a sealed checkpoint
cannot be amended. To change a protocol, cancel the run and launch a new one. The checkpoint, its declared protocol
files, and the protocol-stage report are also frozen for later same-branch
work. Inspect the protocol and every reported deviation when judging the run.
The checkpoint establishes the identity and sequence of the recorded protocol;
it does not establish that the study design is scientifically adequate.

The run-record checks protect provenance. They do not establish that:

- the implementation is mathematically correct;
- the sample size is adequate;
- replications are independent;
- uncertainty is estimated correctly;
- leakage is absent;
- baselines are fair;
- missingness is ignorable;
- a biological design supports the stated unit of inference;
- the scientific conclusions are valid.

Those judgments remain part of your review and, where appropriate, independent
human review.

## Review checklist

Before using the result, ask:

- Was the protocol recorded before the main results, and are all deviations
  identified with reasons?
- Does the code implement the exact Phase 2 stable ID, version, and definition
  digest selected for this branch?
- Do known-answer tests and failure tests cover the main implementation risks?
- Are data provenance, preprocessing, exclusions, and missingness documented?
- Are sample size, seeds, replications, and uncertainty appropriate to the
  sampling or simulation process?
- Is the evaluation split protected from training and tuning decisions?
- Are baselines compared under comparable information, tuning effort, stopping
  rules, and computational resources?
- Are figures traceable to measured result tables and executable analysis?
- Are negative and inconclusive results reported with the same care as favorable
  results?
- When theory and experiment disagree, does the report distinguish a coding
  error, finite-sample behavior, discretization, assumption failure, and a
  possible theoretical gap?
- In biological work, is the experimental unit correct, are biological and
  technical replicates separated, and are batch effects and confounding
  considered?

## How to use the result

A valid Complete or Partial Phase 4 run updates the branch's cumulative
`evidence-index.json` and compact current `empirical-synthesis.md`. Read those
current records with the new run's summary, role reports, protocol, deviations,
and supporting artifacts before deciding whether the evidence is adequate.

The evidence index retains every evidence identity and its current disposition.
Current entries can be reused without repeating completed work. Outdated,
superseded, withdrawn, or unresolved entries remain visible but are not treated
as current support. The synthesis states what the present method currently
supports rather than narrating every run.

### Rerun Phase 4

Start another Phase 4 run when the study needs a correction, extension, or
different scope. Examples include a failed diagnostic, missing baseline, unfair
tuning comparison, revised uncertainty calculation, different dataset or
parameter regime, new replication design, or changed implementation.

State the required changes in the new run instructions. The team starts from the
current evidence index, preserves existing evidence IDs and immutable artifact
fields, adds new evidence under new IDs, and updates dispositions with reasons.
A non-current evidence ID cannot return to current. Revalidation or replacement
therefore appends a new run-local entry and may mark the older entry
`superseded`.
A valid result atomically updates the index and synthesis. Failed or invalid
output leaves the current package unchanged.

When Phase 2 advances the method version after a calculation-defining change,
Phase 4 marks earlier exact-method evidence outdated. This includes all earlier
code and scientific outputs. Rerun the
diagnostics or experiments needed to establish whether those results still
apply. Record any successful recomputation or revalidation under a new evidence
ID; do not relabel the outdated entry as current. Raw data and generic
infrastructure may remain current only when their mathematical independence
from the changed calculation is recorded explicitly.

### Return to an earlier phase

Return to Phase 3 when the evidence exposes a mathematical inconsistency or an
assumption that needs further analysis. Return to Phase 2 when the method itself
must be redesigned. You decide when to start either run.

## Use in Phase 5

Phase 5 requires a usable current result from each of Phases 1 through 4. A
current Phase 4 result may be Complete or Partial, and so may Phase 3 — a
Partial theory feeds Phase 5 with its stated limitations carried forward. Phase 3 and Phase 4 must match the selected method and each other's
recorded semantic basis. The Phase 4 package can have no outdated or unresolved
evidence. Phase 4 alone does not make the branch ready or start Phase 5.

For artifact names, run records, and branch layout, see
[Files and records](../reference/files-and-records).
