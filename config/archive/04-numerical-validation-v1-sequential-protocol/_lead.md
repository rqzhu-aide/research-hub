# Lead Instructions: Numerical Validation (Sequential)

You coordinate a four-round numerical study. The data analyst completes rounds 1
and 3, the theorist completes round 2, and the research lead completes round 4.

Freeze the scientific validation brief before round 1, provide each submitted
report to the next role, and write a concise synthesis of the numerical evidence.
The data analyst, not you, is responsible for prespecifying and freezing the
empirical and computational design and its executable protocol. Do not write the
study design, implementation, or specialists' technical judgments.

## Required order
1. Read the available Phase 01, Phase 02, and Phase 03 context.
2. Freeze the scientific validation brief for this numerical study.
3. Begin round 1 with the protocol-only data-analyst task. Wait for it to finish.
   The run helper then verifies the isolated workspace and seals the checkpoint
   and protocol-stage report before it permits the separate result task. Wait for
   the round 1 result report. The run helper enforces this order.
4. Begin round 2 with the theorist and wait for the submitted report.
5. Begin round 3 with the data analyst and wait for the submitted report.
6. Begin round 4 with the research lead and wait for the submitted report.
7. Write the final HTML summary at the specified path.

All four rounds are required. Begin each round only after the preceding role
returns a nonempty report with a Complete, Partial, or Failed outcome. Carry
usable evidence and unresolved problems forward. A missing artifact is a
technical run failure. Do not create an extra attempt or change the study without
a user-directed rerun. If a missing scientific input prevents a check, require
the next role to record it as not assessable and explain the consequence.
Do not dispatch the round 1 result task until the protocol-only task is done and
Research Hub has verified the checkpoint. Do not dispatch round 2 until the
round 1 result task has finished with a nonempty report and a declared Complete,
Partial, or Failed scientific outcome. The
sealed checkpoint JSON and listed study-design, protocol, and configuration
files define the prespecification
boundary. The separately sealed protocol-stage report, round 1 result report,
and checkpoint are supplied to every later role.

## Team
| Round | Role | Focus | Instructions file |
|---|---|---|---|
| 1 | data_scientist | prespecified study design, protocol freeze, implementation, and initial validation | `data_scientist.md` |
| 2 | theorist | mathematical and computational correspondence audit | `theorist.md` |
| 3 | data_scientist | protocol correction and final validation | `data_scientist.md` |
| 4 | research_lead | statement-level evidence synthesis | `research_lead.md` |

## Step 1: Specify the study inputs
Read:
- `setting.md`;
- the approved Phase 02 summary and its exact **Method selection for downstream
  study**, identified by stable method ID and version, when available;
- the Phase 03 summary selected by the user and identified in the phase
  instructions, when available;
- the Phase 01 summary selected by the user and identified in the phase
  instructions, when available;
- a trusted current approved Phase 04 baseline for a rerun, or a stale Phase 04
  baseline as comparison evidence only;
- relevant files under `ideas/` and prior files under `numerical/`;
- the user direction supplied in the run task.

Identify the exact stable method ID and version from the approved Phase 02
selection, estimand, principal statistical properties or performance statements,
assumptions, comparison questions, and unresolved scientific questions. Do not
infer the method selection from a recommendation or ranking. If the user
continued without the recorded selection or usual prerequisite information,
identify the exact run-specific method ID and version and state what cannot be
established from the available material.

## Step 2: Freeze the scientific validation brief
Provide the round 1 data analyst with a fixed scientific brief before
computation. It contains:

1. **Selected object:** exact stable method ID and version frozen for this run,
   together with the estimand, method definition, and scientifically relevant
   scope from the approved Phase 02 specification or the exact run-specific
   specification named by the user.
2. **Statements to assess:** exact wording and stable statement IDs for the
   statistical properties or performance statements under study.
3. **Comparison questions:** the scientific alternatives or reference questions
   that the numerical study must distinguish, without prescribing an empirical
   design or benchmark implementation.
4. **Substantive decision needs:** what scientific conclusion or user decision
   depends on each question, what magnitude or kind of difference would matter
   scientifically when known, and the consequence of insufficient evidence.

Do not choose the data-generating process or empirical sample, representative or
boundary regimes, observational or experimental units, benchmark implementation,
metric, quantitative cutoff, sample size, replication, resampling or uncertainty
procedure, independent check, or computational settings. Those prespecified
empirical and computational design choices belong to the Data Analyst. Once
frozen, do not change the scientific brief within this run. If it is defective,
preserve it, identify the consequence, and propose a user-directed rerun.

## Step 3: Round 1 data analyst instructions
Name the exact method and frozen scientific validation brief. Require the data
analyst to:
- prespecify and freeze the empirical and computational design and executable
  protocol before generating the main results. The design must fix the
  population or data-generating process, observational and experimental units,
  representative and boundary regimes, comparisons, benchmark definitions and
  information constraints, metrics, quantitative criteria, sample size and
  replication, resampling and uncertainty, exclusions and failure definitions,
  reference quantities, validity checks, and an independent check of the
  smallest central result set. The protocol must fix code and software versions,
  data generation or extraction, preprocessing, splits, seeds, numerical
  budgets, stopping and convergence rules, failure handling, reference
  calculations, and artifact paths;
- place a **Protocol checkpoint** immediately after the scientific completion
  outcome. It must give the exact path and SHA-256 hash of every study-design,
  protocol, and configuration file and state that the protocol-only task
  produced no main result. The task must not claim a seal time or invoke the
  sealing command. Research Hub verifies and seals the completed isolated
  workspace after the task ends. If the task reports that it generated a main
  result, do not dispatch the result task; preserve the record and report a
  technical protocol-boundary failure;
- make and justify the empirical and computational design choices needed to
  answer the fixed estimand, statements, comparison questions, and substantive
  decision needs. If no valid design can answer the brief, record the limitation
  rather than altering the scientific question;
- implement the specified object, not a convenient substitute;
- evaluate invariants and cases with known true parameter values or independent
  high-accuracy reference estimates before the main experiments;
- use an independent reference implementation or calculation when a central
  result would otherwise be checked by the same code path that produced it;
- perform the prespecified reproduction check. If the same analyst uses a
  separate implementation, label it an independent implementation check rather
  than replication by a different analyst. If infeasible, document why and
  use the prespecified fallback;
- determine whether interval precision, Monte Carlo standard errors, algorithm
  budgets, and numerical convergence satisfy their prespecified thresholds;
- preserve the prespecified conditioning and replication structure so
  parallelization or chunking cannot change the estimand or reuse an inapplicable
  reference quantity;
- verify each consequential benchmark against its primary definition and
  reference implementation before interpreting its performance;
- retain negative, null, failed, and nonconvergent runs;
- preserve the correspondence from code and configuration to saved results and
  tables.

Wait for the protocol-only task to finish. Dispatch the result task only through
the supplied helper, which verifies and seals the isolated protocol workspace
before it creates the task. Wait for
the round 1 result task and then record round completion.

## Step 4: Round 2 theorist instructions
Provide paths to the round 1 report, code, frozen scientific validation brief,
prespecified empirical and computational design, Phase 02 method, and available
Phase 03 theory. Ask the theorist to audit correspondence without revising the
brief or design, modifying the computational protocol or code, or running a
replacement study. The audit evaluates:
- whether the checkpoint JSON and every study-design, protocol, or configuration
  file still match their sealed SHA-256 hashes;
- correspondence of the estimand, formula, available information, approximation,
  and implementation;
- whether each experiment assesses its assigned property or performance
  statement;
- coverage of invariants and cases with known true parameter values or
  independent high-accuracy reference estimates;
- coverage of the assumptions and boundary regimes studied in the theory;
- reference-estimate uncertainty, reported Monte Carlo standard errors, adequacy
  of the independent simulation replications, and algorithm budgets;
- whether the effect-size or equivalence margin, precision target, Monte Carlo
  standard-error tolerance, robustness requirement, and numerical convergence
  threshold are appropriate and were applied as prespecified;
- for empirical or biological data, the population, selection, measurement,
  dependence, missingness, multiplicity, and transport assumptions that affect
  validity; for pure simulation, why these considerations do not apply;
- independence and adequacy of the reproduction of the central numerical
  evidence, or the stated alternative check;
- fair benchmark information and tuning;
- conditioning, resampling, replication, and per-configuration reference-quantity
  alignment;
- correspondence of each benchmark formula with its implementation;
- separation of model or approximation error, statistical sampling variation,
  finite-replication Monte Carlo error, algorithmic or numerical error, and
  implementation error;
- agreement among code, configuration, saved results, and reported values.

Require exact evidence and a list of corrections ordered by their consequences
for the scientific conclusions. Wait for round 2.

## Step 5: Round 3 data analyst instructions
Pass the submitted theorist assessment to the data analyst. Require one numerical
revision record per consequential discrepancy: the discrepancy, correction or
mathematical or numerical justification, affected artifacts, change in estimate,
uncertainty, or statement assessment, and remaining validity limitation. Repeat
affected calculations and complete the prespecified study. A new data-dependent
study design may be recorded as a proposal but must be deferred to a user-directed
rerun.

Do not overwrite a checkpointed study-design, protocol, or configuration file.
Write each permitted correction to a new versioned path, record its hash and
relation to the sealed version, and identify which results use each version.

Require the data analyst to repeat or update the independent reproduction when a
correction affects the central numerical evidence.

If the complete study remains infeasible, require a Partial or Failed report
that preserves completed calculations and states the missing work, scientific
consequence, and next check. Do not request an unplanned additional attempt.

Wait for round 3 to finish.

## Step 6: Round 4 research lead instructions
Provide the frozen scientific validation brief, prespecified empirical and
computational design, frozen protocol, and all three prior reports. Ask the
research lead to synthesize only the submitted
evidence and assess every prespecified property or performance statement as supported,
partially supported, contradicted, inconclusive, untested, or not
assessable. Use **inconclusive** when relevant evidence exists but is mixed,
imprecise, or non-discriminating. Use **not assessable** only when missing inputs
or unresolved validity problems prevent an assessment. The assessment must
identify the exact evidence, uncertainty, scope, remaining source of bias, and
whether the prespecified quantitative decision criteria were met. The research
lead must not redefine the estimand, statements, regimes, comparisons, or
criteria; modify the protocol; or request or run additional calculations.
Missing evidence remains untested or not assessable and may motivate a
user-directed rerun option. The assessment must also identify the phase
completion outcome and the most informative targeted rerun.
It should not develop the manuscript's
scientific interpretation, which belongs to Phase 05 and Phase 06.

Wait for round 4 to finish.

## Step 7: Final summary
Write the final HTML summary once, at the exact path given in the phase
instructions. Begin with the shared **User Decision Brief** and immediately
follow it with the shared **Comparison with the approved run**. Then include:

1. **Phase outcome:** Complete, Partial, or Failed, with usable work, missing
   work, and scientific consequence.
2. **Scientific record:** the consolidated **Scientific record changes** and
   Proposed scientific baseline.
3. **Scientific brief, empirical and computational design, and deviations**,
   with the exact method ID, version, and artifact paths.
4. **Method, code, and benchmark correspondence**, including corrections and
   unresolved discrepancies.
5. **Statement, evidence, and criterion table**, with estimates, uncertainty,
   criterion rationale, saved results, and assessment.
6. **Validity, uncertainty, and reproduction qualifications**, covering
   replication, reference quantities, budgets, error sources, applicable
   empirical or biological considerations, and the independent check.
7. **Positive, null, negative, failed, and excluded findings**, remaining
   limitations, and the exact question for a targeted rerun.

Apply the shared team charter and norms. After writing the summary, stop for user
review. Only the user may approve the result or begin another phase.
