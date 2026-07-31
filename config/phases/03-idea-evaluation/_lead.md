# Lead Instructions: Theoretical Development

Coordinate a fixed three-stage theoretical development run for the method chosen
by the user. The order is theorist, data analyst, research lead. The theorist
does the primary mathematical work, the analyst audits it and assesses
computability, and the lead reconciles the evidence.

## Step 1: Establish the branch and prior context

Read:

- `setting.md`;
- the published Phase 2 summary and canonical method definition;
- the Phase 1 literature assessment;
- the canonical current Phase 3 and Phase 4 records enumerated in the run
  prompt;
- archived Phase 3 summaries only when the prompt states that the user selected
  `include_archived_summaries`.

Verify the selected stable ID, version, definition path, and
`definition_sha256`. Treat that tuple as the exact mathematical object for the
run. If any field is missing or inconsistent, report a launch-integrity
failure. No team member may choose a replacement method or edit the Phase 2
catalog.

If the supplied current theory was written for an earlier method version, treat
it as historical context rather than current support. Require the specialists
to judge each potentially reusable argument against the frozen definition. A
claim becomes current for the new version only after this run verifies its
assumptions and proof under that definition.

The canonical current records are the shared scientific starting point for this
run. Give them to every role. Archived summaries are optional background, never
the baseline. Preserve source status and distinguish mathematical results,
empirical findings, interpretations, and unresolved disagreements. Never import
an unlisted artifact or material from another method branch.

Treat every supplied knowledge fragment as frozen launch evidence. Specialists
must cite stable statement IDs and report proposed changes in their own stage
reports. They must not edit either a frozen fragment or the prepared run-root
fragment. Only the Stage 3 research lead may write the run-root
`knowledge-fragment.json`.

On a rerun, begin from the prepared current `theory-manuscript.md` rather than
restarting. The new run should correct an error, close a proof gap,
strengthen a bound, relax an assumption, extend the scope, or address a Phase 4
discrepancy. The final manuscript must remain self-contained, and the summary
must state what changed.

## Step 2: Stage 1, theorist

Assign the theorist the selected definition and supplied current context.
Require precise definitions, numbered assumptions, theorem statements, complete
proofs, quantitative bounds when relevant, and explicit scope. Any unproved
result must be labeled as a conjecture with its exact gap.

The theorist's report must be self-contained enough for the analyst to audit. It
must also identify computational claims, numerical assumptions, and empirical
questions arising from the theory.

## Step 3: Stage 2, data analyst

Give the analyst the same frozen context and the completed current theorist
report. Require:

- a quantitative time and memory analysis;
- an end-to-end cost assessment tied to a statistical or numerical precision
  target;
- an implementation and numerical-stability assessment;
- a theorem-by-theorem proof audit with exact citations to assumptions,
  equations, and inference steps;
- reconciliation with any supplied Phase 4 evidence.

The analyst does not merely rate the proofs. Each criticism must state its
scientific consequence and a possible correction or discriminating check.

## Step 4: Stage 3, research lead

Give the lead the supplied context and both current reports. Require the lead to:

- decide which mathematical claims remain supported after the audit;
- narrow or relabel any claim with an unresolved substantive gap;
- position the contribution against named prior work;
- separate deductive conclusions from empirical findings;
- state the implications for a Phase 4 run or rerun;
- preserve every unresolved disagreement in a structured ledger;
- consolidate the supported current results into the complete replacement
  `theory-manuscript.md` at the run output root;
- write the complete current statement set, dependencies, and compact lead
  summary to the prepared run-root `knowledge-fragment.json`.

The lead cannot ask an earlier role to revise within this run. An unresolved
issue becomes a precise target for a user-initiated rerun.

## Step 5: Final synthesis

## Handoff briefs for downstream roles
Before submitting, write one brief per downstream consumer role as
`handoff/{role}.md` in the run output directory (a sibling of your round
reports). These briefs are the primary documents downstream agents read; the
full summary and decision record remain available for depth.

Write briefs for: **data_scientist** (Phase 4: what to validate, assumptions to honor) and **paper_reviewer** (Phase 5: proved claims and limitations).

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

1. **Selected method identity**: stable ID, version, definition path, and
   `definition_sha256`.
2. **Change from prior same-branch work**: what was retained, corrected,
   extended, or contradicted.
3. **Proved results**: theorem statements, assumptions, and proof status.
4. **Conjectures and failed proof steps**.
5. **Computational assessment**: feasibility, time, memory, and stability.
6. **Proof-audit disposition**: each substantive finding and how it affects the
   claims.
7. **Relation to Phase 4 evidence**: agreements, discrepancies, and recommended
   empirical checks.
8. **Contribution and scope**.
9. **Unresolved-issues ledger**: disagreements, consequences, and the smallest
   result that would resolve each one.
10. **Current theory record and knowledge fragment**: the present scientific
    account and its decision-relevant changes.
11. **Status separation**: report method alignment, sibling-basis alignment,
    and the scientific completion outcome as distinct judgments.
12. **Recommendation**.

The recommendation may be:

- **run or rerun Phase 4** for a named empirical question;
- **rerun Phase 3** for a named theorem, assumption, or discrepancy;
- **study another active method** in a separate Phase 3 or Phase 4 launch;
- **rerun Phase 2** only when the canonical method definition or catalog must
  change;
- **defer further work**.

Phase 4 does not require Phase 3 to be completed. Explain how the current theory
would inform Phase 4, but do not present Phase 3 as a launch gate. The user alone
chooses and starts the next run.

## Requirements

- Follow the three stages in the configured order.
- Give each later role every earlier current-stage report.
- Give every role the canonical current records named in the prompt, plus
  archived Phase 3 summaries only when the user selected that launch option.
- Treat the Phase 2 method catalog as read-only.
- Require full proofs for claims labeled proved.
- Require quantitative cost analysis rather than qualitative feasibility
  judgments.
- Preserve negative results and disagreements.
- Do not infer scientific strength from alignment or infer current method
  applicability from a Complete outcome.
- Write only into the current run directory.
- Before submission, ensure `theory-manuscript.md` is a complete, readable
  theory account for the selected method, not a change log or collection of
  references to older runs.
- Before submission, ensure `knowledge-fragment.json` preserves the prepared
  `schema_version`, `kind`, `semantics`, `method`, `generation`, and
  `source_run_id`; sets `coverage` to `complete`; contains every current
  statement and valid dependency; and gives a compact `lead_summary`.
- Ensure the fragment agrees with the report's scientific record changes.
- A Partial scientific outcome may retain unresolved questions, but the
  fragment must remain structurally complete and explicit about support, scope,
  assumptions, and uncertainty.
- A Complete valid submission replaces the branch's current theory package.
  Failed or incomplete work leaves the previous current package unchanged.
