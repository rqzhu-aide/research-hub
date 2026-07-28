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

The chosen method's stable identity, version, and content digest are frozen for
the run. Work is stored in the same durable branch that Phase 3 uses for that
method. Available results and discussion from earlier Phase 3 and Phase 4 runs
on the exact same branch are supplied as prior evidence. If no Phase 3 result is
available, the empirical work proceeds from the Phase 2 definition and labels
any theoretical interpretation that remains unresolved.

Each stage keeps its report, code, data, tables, figures, and other supporting
evidence inside its assigned run folder. Research Hub inventories and hashes
these files when the stage finishes. Later Phase 3 and Phase 4 runs on the same
branch receive frozen copies rather than untracked working files.

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

All three roles receive the frozen method and available results and discussion
from earlier Phase 3 and Phase 4 runs on the same branch. Within the current run,
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

## Scientific standards and application checks

The items above are **scientific completion standards for the agents**. They
define what a credible Phase 4 result should contain. A technical run can finish
even when one of these scientific standards is not met, so you must review the
evidence.

Research Hub separately freezes and hashes the declared launch inputs, prompt,
and manifest, and records submitted artifacts. The shipped Phase 4
configuration enables a protocol checkpoint: the analyst's protocol is sealed
before the main result work proceeds. The checkpoint, its declared protocol
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
- Does the code implement the exact Phase 2 method definition and version selected
  for this branch?
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

A completed Phase 4 run remains a separate scientific record. Read its summary,
role reports, protocol, deviations, and supporting artifacts before deciding
whether its evidence is adequate for your intended use.

Completed, intact results and discussion may be supplied to later Phase 3 and
Phase 4 runs on the same method branch. This makes prior work available for
comparison and extension. It does not certify the implementation or establish
that every statistical or scientific claim is valid.

### Rerun Phase 4

Start another Phase 4 run when the study needs a correction, extension, or
different scope. Examples include a failed diagnostic, missing baseline, unfair
tuning comparison, revised uncertainty calculation, different dataset or
parameter regime, new replication design, or changed implementation.

State the required changes in the new run instructions and identify which prior
results remain useful. Research Hub creates a new record and preserves the
earlier code, results, reports, and discussion. It does not place corrections
into a separate revision queue.

### Return to an earlier phase

Return to Phase 3 when the evidence exposes a mathematical inconsistency or an
assumption that needs further analysis. Return to Phase 2 when the method itself
must be redesigned. You decide when to start either run.

## Use in Phase 5

Phase 5 requires an intact completed result from each of Phases 1 through 4. The
Phase 3 and Phase 4 results must both match the selected method's stable ID,
version, and definition digest. Phase 4 alone does not start Phase 5 or make the
branch ready for manuscript assembly.

For artifact names, run records, and branch layout, see
[Files and records](../reference/files-and-records).
