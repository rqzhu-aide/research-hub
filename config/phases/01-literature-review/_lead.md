# Lead Instructions: Literature Review

Coordinate independent searches by the three roles. In the final report, combine
the evidence by its source quality and relevance to the stated contribution.

## Responsibilities
1. Import the accepted scientific record from the selected user-approved
   summary, or initialize a proposed scientific record when none is available.
2. State the research question or estimand, proposed method or mechanism,
   scientific or statistical contribution, and conditions or scope of validity.
3. Formulate specific research questions for each role.
4. Give each role its instructions together with those questions.
5. Compare all reports and identify resolved and unresolved evidence gaps.
6. Attempt exactly the number of rounds selected by the user and retain usable
   work from Complete, Partial, and Failed role reports.
7. Write an evidence-weighted synthesis that states the best-supported
   conclusion, disagreements, uncertainty, and choices available to the user.

## Roles
| Role | Scientific focus | Instructions file |
|------|------|-----------|
| research_lead (you) | scientific importance and positioning | `research_lead.md` |
| theorist | direct theoretical and methodological prior work | `theorist.md` |
| data_scientist | existing implementations and benchmark practice | `data_scientist.md` |

The run task supplies each role's frozen protocol and the user's direction.
Assign the scientific questions for that round. Your `research_lead` report is
one role-specific assessment. Treat it as evidence for the final synthesis, not
as the synthesis itself.

## Step 1: Review the scientific context
Read:

- `setting.md`
- the team norms and the accepted scientific record imported only from a
  current summary approved by the user, when available
- prior `references/literature-review/run/` outputs
- `draft/`, `ideas/`, and `numerical/` when present

Decide whether this is an initial survey or focused literature update. State the
current candidate:

- research question or estimand;
- proposed method, mechanism, or representation;
- scientific or statistical advance over prior work;
- conditions and scope under which the advance is expected to hold.

If any component is unclear, make its clarification part of the search.
If no current summary approved by the user supplies an accepted scientific
record, initialize a proposed scientific record and state that it has no
approved earlier version.

## Step 2: Assign research questions
The instructions for each role must specify:

1. mode: initial survey or focused literature update;
2. the scientific question implied by the supplied user direction;
3. assigned components of the contribution and exact questions;
4. primary-source requirements;
5. the required distinction among direct prior work, theoretical foundations,
   related methods, and existing implementations;
6. a reproducible search log with sources, dates, query families and synonyms,
   citation chaining, software searches, and a stopping rule.
7. a **Scientific record changes** section containing only proposed additions
   or changes to material statements.

Require each role to quote or cite the exact theorem, formula, algorithm, or
repository used to classify a source. Papers with similar keywords alone do not
establish equivalence.

## Step 3: Between rounds
Read all three reports and revise the list of evidence gaps. Do not change the
candidate contribution without evidence. Ask:

- Is the apparent match direct in target, formula, assumptions, and purpose?
- Which theoretical foundations are being mistaken for originality?
- Does a related method support the proposed mechanism without establishing
  the stated advance?
- Does existing software already implement the stated advance?
- What primary source or forward citation could resolve the most consequential
  uncertainty about originality?
- Do the role-specific conclusions conflict, and what targeted search would
  resolve the conflict?

Use later rounds to resolve named gaps. Do not repeat broad searches.
Use the supported content of nonempty Partial and Failed reports, mark
conclusions that depend on missing work as Not assessable, and continue the
configured rounds. A missing or unreadable artifact is a technical run failure,
not a scientific Failed report.

## Step 4: Final synthesis
Write the final HTML summary to the exact path provided for this run.
Do not overwrite an earlier run summary.
Begin with the User Decision Brief and Comparison with the approved run defined
in the team norms.
Immediately afterward, state the phase outcome as Complete, Partial, or Failed.
Complete means the prescribed literature checks were performed, not that the
candidate contribution was supported. For Partial or Failed, state the usable
evidence, missing work, and scientific consequence.
Keep two sections visibly separate:

1. **Role-specific findings**: what each role concluded, including disagreements.
2. **Evidence-weighted synthesis**: the best-supported conclusion, disagreements,
   uncertainty, and choices available to the user.

Include:

1. the current research question or estimand, proposed method or mechanism,
   scientific or statistical contribution, and conditions or scope of validity;
2. an evidence table classifying direct prior work, theoretical foundations,
   related methods, and existing implementations;
3. closest overlapping work and evidence quality;
4. the assessment status of each contribution and originality statement, using the
   shared vocabulary;
5. one consolidated **Scientific record changes** section and the **Proposed
   scientific baseline**, with the source record or explicit initialization
   recorded; the proposed baseline becomes accepted only after user approval;
6. coverage gaps and precise questions for a focused literature update;
7. searched scope, stopping rule, and any "not found within scope" conclusions;
8. explicit options for the user:
   - approve this literature evidence summary as the current evidence base;
   - request revision of named components of the contribution;
   - rerun a focused search;
   - set aside or discontinue the candidate contribution.

Do not select an option for the user. After submitting the summary, stop. The
user alone decides whether to approve it, request changes, rerun the phase, or
start Method Development.

## Requirements
- Follow the shared team norms and use the accepted scientific record for this
  run.
- Require role reports to include only proposed **Scientific record changes**,
  not a reconstructed record. Reconcile those proposed changes in the final
  summary without altering an earlier accepted record.
- Address the user direction already supplied in each run task.
- Calibrate originality to primary-source evidence.
- Treat unresolved overlap as unresolved, not as proof of originality.
- Give each later round a precise question that can be resolved by evidence.
