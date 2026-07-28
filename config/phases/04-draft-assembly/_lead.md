# Lead Instructions: Implementation and Experiments

Coordinate a fixed three-stage empirical run for the method chosen by the user.
The order is data analyst, theorist, research lead. The analyst does the primary
implementation and experimental work, the theorist audits it, and the lead
reconciles the evidence.

## Step 1: Establish the branch, scope, and prior context

Read:

- `setting.md`;
- the published Phase 2 summary and canonical method definition;
- the Phase 1 literature assessment, including relevant baselines;
- every frozen prior same-branch Phase 3 and Phase 4 summary and discussion
  report enumerated in the run prompt.

Verify the selected stable ID, version, definition path, and SHA-256 digest. If
they are missing or inconsistent, report a launch-integrity failure. No role may
choose another method or edit the Phase 2 catalog.

Phase 3 is optional context. A Phase 4 run may begin directly from the Phase 2
definition. When same-branch Phase 3 results exist, use their assumptions,
theorems, bounds, and open questions. When they do not exist, do not infer a
missing guarantee.

Give every role the complete frozen same-branch context named in the prompt,
including prior summaries and role reports from both sibling phases. Do not
import an unlisted artifact or material from another branch. Prior files are
sealed and the current run writes only to its new run directory.

## Step 2: Interpret the selected run mode

The run mode changes empirical scope only:

- **Preliminary**: a runnable implementation, protocol, focused diagnostics, and
  a small study that establishes basic numerical credibility.
- **Comprehensive**: a full prespecified evaluation with strong baselines,
  multiple settings, sensitivity analysis, uncertainty, tables, figures, and
  complete reproducibility information.

Both modes use the same role order. Either may be launched directly after Phase
2. A comprehensive run does not require a preliminary run. If prior same-branch
code exists, require the analyst to audit and reuse the supported parts when
appropriate.

## Step 3: Stage 1, data analyst

Assign the analyst the selected definition and all frozen prior context. The
analyst must first record a study protocol with hypotheses, outcomes, baselines,
settings, sample sizes, replications, uncertainty measures, stopping rules, and
success or failure criteria. Complete the protocol checkpoint before the analyst
executes the main result-producing work.

Then require the analyst to:

- implement or verify the selected method in runnable code;
- run appropriate known-answer, invariant, data-integrity, numerical, and
  reproducibility diagnostics;
- complete the selected preliminary or comprehensive scope;
- record actual measurements, uncertainty, failures, and negative results;
- identify all protocol deviations and exploratory analyses;
- provide exact code, data, figure, table, and command paths.

## Step 4: Stage 2, theorist

Give the theorist the same frozen context and the completed current analyst
report and artifacts. Require an audit of:

- correspondence between the Phase 2 definition and the implementation;
- protocol integrity and the distinction between confirmatory and exploratory
  results;
- assumptions, approximations, discretization, and numerical behavior;
- correspondence between the data and any available same-branch Phase 3 result;
- plausible explanations for every important discrepancy.

If Phase 3 has not run, the theorist may state exact consequences of the Phase 2
definition and formulate conjectures, but may not invent a proved guarantee.

## Step 5: Stage 3, research lead

Give the lead all prior context and both current reports. Require the lead to:

- classify each central empirical claim using its estimate, uncertainty, design,
  and audit status;
- retain null results, failures, and protocol deviations;
- distinguish empirical findings from mathematical conclusions;
- state how the results inform a Phase 3 run or rerun;
- preserve unresolved disagreements in a structured ledger.

The lead cannot ask an earlier role to revise within this run. A required fix or
additional experiment becomes a precise target for a user-initiated rerun.

## Step 6: Final synthesis

Write the HTML summary to the exact path provided. Begin with the User Decision
Brief required by the team norms. Include:

1. **Selected method identity and run scope**.
2. **Change from prior same-branch work**.
3. **Prespecified protocol and deviations**.
4. **Implementation and diagnostic status**.
5. **Empirical findings** with uncertainty and baseline comparisons.
6. **Negative and inconclusive results**.
7. **Theorist-audit disposition**.
8. **Relation to same-branch Phase 3 theory**, or the precise theoretical
   questions raised when no such result exists.
9. **Reproducibility record**.
10. **Unresolved-issues ledger**.
11. **Proposed scientific baseline** and scientific record changes.
12. **Recommendation**.

The recommendation may be:

- **rerun Phase 4** with a named preliminary or comprehensive objective;
- **run or rerun Phase 3** for a named theorem, assumption, or discrepancy;
- **study another active method** in a separate Phase 3 or Phase 4 launch;
- **rerun Phase 2** only when the canonical definition or catalog must change;
- **proceed to Phase 5** only when both Phase 3 and Phase 4 have completed for
  the exact same method identity;
- **defer further work**.

The user alone chooses and starts the next run.

## Requirements

- Follow the three stages in the configured order.
- Complete the protocol checkpoint before the main result-producing work.
- Give each later role every earlier current-stage report.
- Give every role all frozen prior same-branch Phase 3 and Phase 4 context named
  in the prompt.
- Treat the Phase 2 catalog as read-only.
- Apply the completion standard for the selected empirical scope.
- Require runnable code and recorded measurements.
- Quantify uncertainty when the design supports it.
- Preserve negative results, deviations, failures, and disagreements.
