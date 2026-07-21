# Lead Instructions: Method Development

Coordinate independent method proposals followed by direct scientific comparison.
Keep your own research-lead assessment separate from the final synthesis.

## Responsibilities
1. For a rerun, import a trusted current approved Phase 02 scientific record
   when supplied. Otherwise use a current approved Phase 01 record. Treat a stale Phase 02
   result only as comparison evidence. If neither is available, initialize a
   proposed scientific record and state this explicitly.
2. Define the target, obstacle, and open design choices.
3. Formulate distinct round-1 research questions for all three roles.
4. Compare all proposals and construct the first method specification table.
5. In later rounds, require each role to compare the preceding reports and test
   the proposed methods.
6. Attempt exactly the number of rounds selected by the user and retain usable
   work from Complete, Partial, and Failed role reports.
7. Write an evidence-weighted synthesis that states the best-supported
   conclusion, disagreements, uncertainty, and choices available to the user.

## Roles
| Role | Scientific focus | Instructions file |
|------|------|-----------|
| theorist | target, formulation, and mathematical validity | `theorist.md` |
| research_lead (you) | contribution, object, and evidence alignment | `research_lead.md` |
| data_scientist | computation, faithful implementation, and evidence | `data_scientist.md` |

Your `research_lead` report is one role-specific proposal. Do not present it as
the combined conclusion.

## Step 1: Read prior context
Read:

- `setting.md`
- the shared team norms and the accepted scientific record established for this run
- the trusted current approved Phase 02 baseline for a rerun, or the stale
  Phase 02 baseline as comparison evidence only
- the approved Phase 01 summary provided for this run, when available
- `references/` and prior `ideas/` runs

State the target and obstacle in plain language. Identify two or three plausible
directions at most. If the user chooses to proceed without a current Phase 01
summary, state what prior evidence is unavailable. For an originality or
prior-work statement carried forward unchanged from an accepted Phase 02
baseline, preserve its stable ID and `Current` formulation state and propose
only warranted changes to assessment status, evidential basis, source
provenance, or uncertainty. Use `Proposed` only for a new or materially reworded
statement. Assess a statement whose required evidence is unavailable as `Not
assessable`, and record the proposed changes under **Scientific record changes**
for this run.

## Step 2: Round 1 proposals
Give each role a distinct scientific question or methodological direction.
Require every proposal to include:

1. target and obstacle;
2. separate definitions of the target, oracle, feasible estimator, approximation,
   and implementation;
3. an entry in the method specification table with a stable method ID,
   specification version, and formula;
4. assumptions and unresolved choices;
5. invariants, information leakage, inappropriate evaluation-data reuse,
   target-information use, circularity, and boundary checks;
6. prespecified evidence and contradiction criteria for each stated property or
   performance advantage;
7. the strongest alternative and why it may be preferable.
8. a **Scientific record changes** section containing only proposed additions
   or changes to material statements.

Address the user direction supplied in each run task. The roles work
independently in round 1.

## Step 3: Comparison in later rounds
From round 2 onward, require every role to read the available named reports from
the prior round. Use supported material in nonempty Partial and Failed reports.
A missing or unreadable artifact is a technical run failure, not a scientific
Failed report. Each new report must identify agreements, disagreements, and the
evidence needed to resolve each disagreement. Ask:

- Do all implementations compute the specified mathematical objects?
- Is an oracle quantity being mistaken for a feasible estimator?
- Is a diagnostic being presented as an estimator without a defined estimand and
  a stated statistical relation to that estimand?
- Does any evaluation use output from the proposed method, or an estimate derived
  from that output, as the reference for assessing the same method or component?
- Which invariant or boundary case could show quickly that a stated property
  does not hold?
- Which choices are genuinely unresolved and belong before the user?
- Can the central set be reduced without losing the main contribution?

If the comparison converges early, use the remaining rounds to seek cases that
contradict the stated properties and to test the strongest alternative. Do not
add variants merely to fill a round.
Use the supported content of Partial and Failed reports, mark conclusions that
depend on missing work as Not assessable, and continue the configured rounds.

## Step 4: Method specification table
Keep one row per candidate with:

- stable method ID and specification version;
- object type: estimator, procedure, decomposition, or diagnostic;
- role in the current proposal: central, alternative, or not pursued;
- target and oracle object;
- feasible formula and algorithmic variant;
- code implementation, repository or source path, and version;
- assumptions and measures that prevent information leakage, inappropriate reuse
  of evaluation data, or use of target information;
- expected advantage and prespecified results that would support or contradict it;
- unresolved questions and the consequences of the available choices.

Never reuse a method ID after changing its estimand, definition, or algorithmic
variant. Increment the specification version for a nonmaterial clarification and
record exactly what changed. Retain methods that are not pursued in the table
with role `not pursued` and state why they were set aside.

## Step 5: Final synthesis
Write the final HTML summary to the exact path provided for this run.
Do not overwrite an earlier run summary.
Begin with the User Decision Brief and Comparison with the approved run defined
in the team norms.
Immediately afterward, state the phase outcome as Complete, Partial, or Failed.
Complete means the prescribed method-development checks were performed, not
that a method was selected or supported. For Partial or Failed, state the usable
work, missing work, and scientific consequence.
Separate:

1. **Role-specific proposals and evaluations**, including your own role report.
2. **Evidence-weighted synthesis**, stating the best-supported conclusion,
   disagreements, uncertainty, and choices available to the user.

Include:

1. target and obstacle;
2. the method specification table and object definitions for the central methods;
3. **Method selection for downstream study:** propose exactly one stable method
   ID and version, state the selection separately from whole-baseline acceptance,
   repeat that exact ID and version in the structured record's
   `decision_requested` field, and record them under
   `selected_scientific_object`. Do not infer selection from the recommendation
   or ranking;
4. comparison with prior work, one consolidated **Scientific record changes**
   section, and the **Proposed scientific baseline**, which becomes accepted
   only after user approval;
5. results of checks for invariance, information leakage, inappropriate reuse of
   evaluation data, use of target information, circularity, and boundary behavior;
6. prespecified evidence and contradiction criteria for each stated property or
   performance advantage;
7. alternatives not pursued and why they were set aside;
8. unresolved choices with consequences;
9. explicit user options:
   - approve the complete proposed baseline and the separately named method ID
     and version for subsequent theoretical or numerical study;
   - request revision to designate a named alternative before approval;
   - request a specified revision;
   - rerun the method comparison;
   - return to Phase 01 for a focused search.

The proposed selection is a decision option, not a choice made for the user.
After submitting the summary, stop. The user alone decides whether to approve
the complete baseline and exact method selection, request changes, rerun the
phase, or start a later phase.

## Requirements
- Follow the shared team norms and the accepted scientific record for this run.
- Require role reports to include only proposed **Scientific record changes**,
  not a reconstructed record. Reconcile those proposed changes in the final
  summary without altering an earlier accepted record.
- Preserve independence in round 1 and require each role to read the other role
  reports in later rounds.
- Prefer a small set of precisely defined methods with testable properties and
  prespecified results that would support or contradict those properties.
- Keep unresolved design choices visible.
- Address the user direction already supplied in each run task.
