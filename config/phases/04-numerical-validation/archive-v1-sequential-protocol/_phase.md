# Phase: Numerical Validation

## Goal
Assess the empirical behavior of the proposed method. Implement the selected
method version exactly, compare it with appropriately specified benchmarks and,
when available, analytically known values or independently computed reference
estimates. Determine which prespecified statistical properties or performance
statements the numerical results support, narrow, contradict, or leave
inconclusive.

This phase assesses correspondence between the method specification and its
implementation and the validity of the numerical study. It does not choose the
paper's final interpretation. Phase 05 interprets the numerical results and their
qualifications if the user decides to run it.

## Prior information
This phase normally uses the exact stable method ID and version recorded in the
approved Phase 02 **Method selection for downstream study**. Do not infer that
selection from a recommendation, ranking, or method table. The web UI indicates
when the selection or specification is missing or has been replaced by a later
approved version, but the user may choose to continue. In that case, the lead
must identify the exact method ID and version used, state that it is a
run-specific choice rather than the recorded Phase 02 selection when applicable,
and state which estimands, assumptions, or statistical properties cannot be
assessed.

Phase 03 provides useful context but is not required. When the user supplies a
Phase 03 theoretical analysis, study both the regime covered by the results and
scientifically relevant boundary or weakened-assumption regimes. Do not describe
an empirical pattern as a theorem.

For a rerun, use a trusted current approved Phase 04 result as the accepted
scientific record. Treat a stale Phase 04 result only as comparison evidence.

## Study structure
**Sequential.** Keep the four rounds in this exact order:

1. Round 1 contains two ordered data-analyst tasks. The protocol-only task uses
   the frozen scientific validation brief to prespecify and freeze the empirical
   and computational design and executable protocol in an isolated write
   workspace, writes the checkpoint request and protocol-stage report, and stops.
   Research Hub seals both records after the task has ended and dispatches the
   result task only after verification. The result task implements the method and
   runs the initial validation in a separate write workspace.
2. Theorist audits whether the code represents the specified method and whether
   the frozen empirical and computational design and protocol assess each
   prespecified statement in round 2.
3. Data analyst corrects or justifies each identified problem and runs the final
   numerical study in round 3.
4. Research lead synthesizes the submitted empirical evidence for each
   prespecified statement in round 4 without redefining the study or running
   additional analyses.

Each round uses the submitted report from the preceding round. Begin a round only
after that report records a **Complete**, **Partial**, or **Failed** outcome. A
Partial or Failed round does not authorize an unplanned rerun. Pass its usable
evidence and unresolved problems to the next role so the sequence can reach a
scientifically informative conclusion. Do not skip, combine, reorder, or
parallelize these rounds.

## Responsibility for the scientific brief and study design
The coordinating lead freezes a scientific validation brief before round 1. The
brief fixes the exact method ID and version, estimand, scientific statements and
scope, comparison questions, and substantive decision needs. The lead does not
choose the data-generating process or empirical sample, study regimes, benchmark
implementation, metric, quantitative criterion, sampling or replication plan,
uncertainty procedure, independent check, or computational details.

In the round 1 protocol-only task, the data analyst is responsible for
prespecifying and freezing the empirical and computational design and its
executable protocol. The
task may write only in the run-scoped protocol directory. Its only unlisted
files are the checkpoint JSON and protocol-stage report. The task then stops.
The design fixes the
population or data-generating process, units,
regimes, comparisons, metrics and quantitative criteria, sample size and
replication, uncertainty analysis, independent checks, and validity conditions.
The protocol fixes code and software versions, data generation or extraction,
preprocessing, splits, seeds, numerical budgets, stopping and convergence rules,
failure handling, and artifact paths. Each choice must answer the fixed
scientific brief and have a statistical or scientific rationale. If no valid
design can answer the estimand, statement, comparison question, or substantive
decision need, record that limitation rather than changing the brief.

Immediately after its scientific completion outcome, the protocol-stage report
must include a **Protocol checkpoint** section. It identifies every study-design,
protocol, and configuration file by exact path and SHA-256 hash. The data
analyst then stops. After the task has ended, Research
Hub verifies that the isolated workspace contains no unlisted file, seals the
checkpoint JSON, protocol-stage report, and every listed file hash, and prevents
dispatch of the result task until this verification succeeds. Every later task
has a separate write-limited round directory and cannot modify the protocol
directory. This establishes a file-level prespecification boundary; it does not
establish that the chosen design is scientifically adequate. The result task
cites the sealed checkpoint in the round 1 result report. That report, the
protocol-stage report, checkpoint JSON, and listed files are available to rounds
2 through 4. Checkpointed files are immutable. A later
protocol correction must use a new, versioned path and preserve the checkpointed
version for comparison.

The theorist audits correspondence among the frozen scientific validation brief,
prespecified empirical and computational design, frozen protocol, mathematical
method, code, and evidence. The theorist does not revise the brief or design,
modify the implementation, or run a replacement study. The research lead
synthesizes the evidence already submitted in rounds 1
through 3. The research lead does not redefine a statement or criterion, modify
the protocol, or request or run additional calculations. Missing evidence must
remain untested or not assessable and may be presented as a user-directed rerun
option.

## Prespecified empirical and computational design
Use the following terms consistently:

- **Estimand or target parameter:** the population or scientific quantity the
  study seeks to estimate.
- **Oracle procedure:** an idealized procedure that uses information unavailable
  to the feasible method.
- **True parameter value:** a value known from the simulation design or an
  analytic calculation.
- **Independent reference estimate:** a separately computed approximation to the
  estimand, reported with its numerical uncertainty and never described as truth.

For empirical or biological data, a true value or sufficiently accurate
independent reference estimate may not exist. State this explicitly and define
the observable outcome, calibration condition, or comparison used for
assessment.

Across the frozen scientific validation brief, empirical and computational
design, and executable protocol, record the following before the main results
are generated:
- the exact estimand or target parameter;
- the mathematical method, algorithmic variant, code implementation, and code
  version being tested;
- the table linking each prespecified property or performance statement to the
  evidence needed to assess it;
- fixed or random design, conditioning set, data-generating processes, datasets,
  splits, and quantities resampled at each replication level;
- the observational and experimental units and, when relevant, biological,
  technical, and simulation replicates; the replication unit used to compute any
  independent reference estimate; and the sources of randomness averaged over;
- the reference quantity for each design or configuration, when available: the
  true parameter value in simulation or an independent high-accuracy reference
  estimate with its construction and numerical uncertainty;
- justification for reusing a reference quantity across configurations, or a
  statement that no defensible reference quantity is available;
- benchmark specification, including the primary definition, the official
  implementation or another documented reference implementation and its version,
  formula and tuning mapping, deviations, and an independent spot check;
- benchmark methods and equal-information, tuning, stopping, and computational
  resource conditions;
- independent simulation replications, the random seed for each, algorithm
  budgets, stopping criteria, and treatment of failed or nonconvergent runs;
- quantitative decision criteria for each principal comparison: the
  scientifically meaningful effect size or equivalence margin when applicable,
  the required interval precision, the maximum acceptable Monte Carlo standard
  error, the settings over which robustness is required, and the numerical
  convergence threshold; for each criterion give its numerical value and scale,
  scientific or decision basis, source or derivation, and how crossing it changes
  the statement assessment; state why a criterion is not applicable when it is
  omitted. Tie Monte Carlo tolerance to the resolution needed for the substantive
  conclusion and convergence tolerance to stability of the reported estimand,
  not to an unexplained default;
- required invariants, calculations with known true parameter values or
  independent high-accuracy reference estimates, and
  saved result locations.

The experimental unit determines the number of independent replications.
Technical replicates do not increase the number of independent biological or
experimental units. Uncertainty estimates and degrees of freedom must respect
nesting, clustering, repeated measures, and other dependence in the design.

For a study using empirical or biological data, also prespecify:

- the target population and the sampled population;
- sampling, inclusion, exclusion, and selection mechanisms;
- measurement or assay validity, measurement error, detection limits, and
  quality-control rules;
- potential confounding and the design or adjustment used to address it when a
  causal or comparative interpretation is intended;
- missing-data patterns, assumptions, and handling;
- batch, laboratory, center, site, operator, and temporal effects when relevant;
- the family of comparisons and multiplicity control when multiple findings
  contribute to a conclusion;
- the population, setting, or measurement system to which the result may be
  transported, and the assumptions required for that transport.

For a pure simulation study, state that these empirical and biological
considerations do not apply and why. Do not use a simulation study to establish
the validity of a biological measurement or a population-level interpretation
that the design does not represent.

Prespecify a reproduction record for the smallest set of results supporting the
central conclusion. Name the primary artifact, reproducing calculation or code
path, owner and round, shared components and independence boundary, uncertainty,
quantitative agreement rule, and fallback. Work by the same data analyst using a
separate code path is an independent implementation check, not replication by a
different analyst. If the planned check is infeasible, state why and use
the strongest check that does not share the suspected failure path.

After examining the results, do not change the frozen scientific validation
brief or prespecified empirical and computational design within the run. Record
every protocol correction or data-dependent exploratory proposal, why it was
needed, and which results it affects. A corrected brief or study design belongs
in a user-directed rerun.

## Folder
All reports land in `numerical/run/NN/`:
- `protocol/protocol-stage.md`: prespecified empirical and computational design,
  executable protocol, and checkpoint declaration, completed before result
  generation
- `protocol/protocol-checkpoint.json`: the sealed checkpoint and exact hashes of its
  listed design, protocol, and configuration files
- `round-01/data_scientist.md`: implementation and initial validation results
  generated after the checkpoint is verified
- `round-02/theorist.md`: mathematical and computational correspondence audit
- `round-03/data_scientist.md`: corrected implementation and final validation
- `round-04/research_lead.md`: statement-level empirical assessment
- the final HTML summary at the exact path given in the phase instructions


Code, scripts, configurations, logs, tables, figures, and saved numerical results
from each task go under that task's assigned `round-NN/` directory. Reports must
cite their exact paths.

## Expected scientific output
By the end of this phase, the project should have five linked records:

1. the frozen scientific validation brief, prespecified empirical and
   computational design, and executable protocol, with every protocol deviation
   tied to runnable code and a fixed method ID and version;
2. method, code, invariant, and consequential benchmark correspondence;
3. one statement-level table linking each criterion and its rationale to the
   estimate, uncertainty, setting, assessment, and saved result;
4. validity, replication, reference-quantity, computational-budget,
   reproduction, and error-source qualifications, including the conditional
   empirical and biological considerations above;
5. positive, null, negative, failed, and excluded results, remaining limitations,
   and the exact question a targeted rerun would address.

## Completion outcomes
Apply the shared completion outcomes to this phase. Mark the phase **Complete**
only when the prespecified study and the checks needed for its principal
conclusions are complete. Mark it **Partial** when all selected rounds returned
nonempty reports but a named comparison, validity check, or reproduction remains
scientifically incomplete. Mark it **Failed** when the completed reports support
no reliable numerical conclusion. A missing report or unfinished task is a
technical run failure, not a scientific completion outcome. A Partial or Failed
phase still requires a final summary that preserves usable results, identifies
missing work and its scientific consequence, and presents options to the user.

Apply the shared team charter and norms. The user decides when to begin each
Phase 04 study and whether to use, revise, or rerun its results. Completion does
not approve the evidence or begin Phase 05.
