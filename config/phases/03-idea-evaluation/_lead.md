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
- every frozen prior same-branch Phase 3 and Phase 4 summary and discussion
  report enumerated in the run prompt.

Verify the selected stable ID, version, definition path, and SHA-256 digest. If
they are missing or inconsistent, report a launch-integrity failure. No team
member may choose a replacement method or edit the Phase 2 catalog.

The supplied prior context is the shared discussion history for this run. Give
it to every role. Preserve its source status and distinguish mathematical
results, empirical findings, interpretations, and unresolved disagreements.
Never import an unlisted artifact or material from another method branch.

On a rerun, begin from supported earlier results rather than restarting. Earlier
files are sealed. The new run should correct an error, close a proof gap,
strengthen a bound, relax an assumption, extend the scope, or address a Phase 4
discrepancy. The final summary must state what changed.

## Step 2: Stage 1, theorist

Assign the theorist the selected definition and all frozen same-branch context.
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

Give the lead all prior context and both current reports. Require the lead to:

- decide which mathematical claims remain supported after the audit;
- narrow or relabel any claim with an unresolved substantive gap;
- position the contribution against named prior work;
- separate deductive conclusions from empirical findings;
- state the implications for a Phase 4 run or rerun;
- preserve every unresolved disagreement in a structured ledger.

The lead cannot ask an earlier role to revise within this run. An unresolved
issue becomes a precise target for a user-initiated rerun.

## Step 5: Final synthesis

Write the HTML summary to the exact path provided. Begin with the User Decision
Brief required by the team norms. Include:

1. **Selected method identity**: stable ID, version, definition path, and digest.
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
10. **Proposed scientific baseline** and scientific record changes.
11. **Recommendation**.

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
- Give every role all frozen prior same-branch Phase 3 and Phase 4 context named
  in the prompt.
- Treat the Phase 2 method catalog as read-only.
- Require full proofs for claims labeled proved.
- Require quantitative cost analysis rather than qualitative feasibility
  judgments.
- Preserve negative results and disagreements.
- Write only into the current run directory.
