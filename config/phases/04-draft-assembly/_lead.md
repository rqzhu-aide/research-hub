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
- the canonical current Phase 3 record and cumulative Phase 4 package enumerated
  in the run prompt.

Verify the selected stable ID, version, definition path, and
`definition_sha256`. Treat that tuple as the exact calculation used by the run.
If any field is missing or inconsistent, report a launch-integrity failure. No
role may choose another method or edit the Phase 2 catalog.

After a method-version change, treat prior code and scientific outputs as
historical. Raw source data and generic infrastructure may be proposed for
reuse only with an explicit mathematical-independence argument. The team may
decide that little or extensive recomputation is needed, but any revalidated or
replacement result must be a new artifact with a new evidence ID.

Phase 3 is optional context. A Phase 4 run may begin directly from the Phase 2
definition. When same-branch Phase 3 results exist, use their assumptions,
theorems, bounds, and open questions. When they do not exist, do not infer a
missing guarantee.

Give every role the canonical current same-branch context named in the prompt.
For Phase 4, use the current `empirical-synthesis.md`, `evidence-index.json`,
and `knowledge-fragment.json`, including the indexed artifact paths, evidence
dispositions, current statements, and evidence links. Do not import an unlisted
artifact or material from another branch.

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

Assign the analyst the selected definition and current cumulative context. The
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
- provide exact code, data, figure, table, and command paths;
- report every proposed evidence-index addition and status change while
  preserving all earlier evidence IDs and immutable artifact fields, assigning
  an `evidence_type`, and applying the exact-method rule;
- propose current empirical statements and evidence links for the knowledge
  fragment, including any carried statement that needs revision after a method
  change;
- leave `empirical-synthesis.md`, `evidence-index.json`, and
  `knowledge-fragment.json` unchanged at the run root.

## Step 4: Stage 2, theorist

Give the theorist the same current context and the completed current analyst
report and artifacts. Require an audit of:

- correspondence between the Phase 2 definition and the implementation;
- protocol integrity and the distinction between confirmatory and exploratory
  results;
- assumptions, approximations, discretization, and numerical behavior;
- correspondence between the data and any available same-branch Phase 3 result;
- plausible explanations for every important discrepancy;
- the proposed evidence-index dispositions and their scientific justification;
- the analyst's proposed empirical statements, dependencies, and evidence
  links, including the continued validity of carried statements.

If Phase 3 has not run, the theorist may state exact consequences of the Phase 2
definition and formulate conjectures, but may not invent a proved guarantee.
The theorist reports recommended package changes but does not edit the three
run-root package files.

## Step 5: Stage 3, research lead

Give the lead the current package and both current reports. Require the lead to:

- classify each central empirical claim using its estimate, uncertainty, design,
  and audit status;
- retain null results, failures, and protocol deviations;
- distinguish empirical findings from mathematical conclusions;
- state how the results inform a Phase 3 run or rerun;
- preserve unresolved disagreements in a structured ledger;
- act as the sole finalizer of `empirical-synthesis.md`,
  `evidence-index.json`, and `knowledge-fragment.json` at the run root;
- finalize `evidence-index.json` without dropping or mutating an earlier
  artifact identity;
- rewrite `empirical-synthesis.md` as the compact complete current empirical
  account, including outdated and unresolved evidence;
- update the evidence index's synthesis SHA-256 and byte size after the final
  synthesis write;
- rewrite `knowledge-fragment.json` as the full current statement set and
  exact evidence links, with `coverage` set to `complete` for a Complete or
  Partial scientific outcome.

The lead cannot ask an earlier role to revise within this run. A required fix or
additional experiment becomes a precise target for a user-initiated rerun.

## Step 6: Final synthesis

## Handoff briefs for downstream roles
Before submitting, write one brief per downstream consumer role as
`handoff/{role}.md` in the run output directory (a sibling of your round
reports). These briefs are the primary documents downstream agents read; the
full summary and decision record remain available for depth.

Write briefs for: **paper_reviewer** (Phase 5: evidence status and what the data showed) and **research_lead** (Phase 5: outdated or unresolved evidence).

Each brief is at most ~200 lines and contains exactly three parts:
1. **What you must know** — the findings and current records this role relies on.
2. **What you must verify or honor** — assumptions, limitations, and unresolved
   items this role must respect or check.
3. **What changed** — versus the previous current record (state "initial run"
   when there is none).

Write for the reader's task, not from your own workflow: a downstream role
should be able to start from your brief without reading the raw reports.
Research Hub seals these files at finalization; missing briefs are recorded
as a warning, and downstream runs then fall back to digests and raw reports.

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
11. **Current empirical record** and scientific record changes.
12. **Status separation**: exact-method applicability, research attention from
    outdated or unresolved evidence, and scientific completion outcome.
13. **Recommendation**.

The recommendation may be:

- **rerun Phase 4** with a named preliminary or comprehensive objective;
- **run or rerun Phase 3** for a named theorem, assumption, or discrepancy;
- **study another active method** in a separate Phase 3 or Phase 4 launch;
- **rerun Phase 2** only when the canonical definition or catalog must change;
- **proceed to Phase 5** only when both Phase 3 and Phase 4 have completed for
  the same exact `stable_id`, `version`, and `definition_sha256`;
- **defer further work**.

The user alone chooses and starts the next run.

## Requirements

- Follow the three stages in the configured order.
- Complete the protocol checkpoint before the main result-producing work.
- Give each later role every earlier current-stage report.
- Give every role the canonical current Phase 3 record and all three files in
  the cumulative Phase 4 package named in the prompt.
- Treat the Phase 2 catalog as read-only.
- Apply the completion standard for the selected empirical scope.
- Require runnable code and recorded measurements.
- Quantify uncertainty when the design supports it.
- Preserve negative results, deviations, failures, and disagreements.
- Before submission, verify that `evidence-index.json` retains every prior entry,
  gives each new artifact a unique ID and exact digest, and marks every obsolete
  exact-method entry `outdated`. Code and scientific outputs cannot be declared
  method-independent. Raw data or generic infrastructure may be declared
  reusable only with a precise independence reason.
- Preserve the prepared top-level method identity, generation, and source run
  ID in both JSON files. Set `synthesis.path` to `empirical-synthesis.md` and
  update its digest and byte size to match the final file.
- Ensure `empirical-synthesis.md` states the current method's performance and
  limitations without requiring a reader to reconstruct them from old runs.
- Verify that `knowledge-fragment.json` has `coverage: complete`, contains the
  full current statement set, and binds every evidence ID exactly once with the
  same status as `evidence-index.json`.
- Reassess carried statements after a method change and keep `lead_summary`
  compact, decision-relevant, and explicit about unresolved questions.
- Do not infer scientific strength from alignment or infer current method
  applicability from a Complete outcome.
- A valid Complete or Partial package becomes current. Failed or invalid work
  leaves the previous package unchanged.
