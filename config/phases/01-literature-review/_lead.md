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
- `references/papers/` — the per-reference summary files (one `.md` per cited
  paper, built by prior runs). These are the project's structured reference
  library. Read them to understand what has already been found and classified.
- `references/literature-summary.md` — the consolidated literature summary
  (updated each run). Read it first for orientation.
- `ideas/` and `branches/` when present

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
8. **Reference library maintenance.** Each role must write a per-reference
   summary file for every new paper it classifies, and update existing files
   when it re-confirms or extends a prior finding. Details in the
   **Reference library** section below.

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

## Reference library

The project maintains a structured reference library at `references/papers/`,
with one `.md` file per cited paper, and a consolidated summary at
`references/literature-summary.md`. This library persists across runs and is
read by downstream phases (especially Phase 02 Method Development).

### Per-reference files (`references/papers/{source}-{id}.md`)
Every role that classifies a new paper writes a file using this format:

```markdown
---
arxiv_id: "2509.09162"          # or github_repo, pmlr_vol, etc.
title: "Full paper title"
authors: ["Author1", "Author2"]
year: 2025
venue: "arXiv preprint"          # or conference/journal name
relation: "direct prior work"    # direct prior work | theoretical foundation | related method | existing implementation
found_in_run: "06"               # this run number
found_by_role: "research_lead"   # this role
also_found_in: []                # later runs that re-confirm (append only)
---

# arXiv:2509.09162 — Short Title

## One-line summary
One sentence.

## Relevance to this project
2-4 sentences.

## Key results / tools
- Specific theorems, algorithms, or data.

## Classification
- **Relation**: direct prior work
- **Overlap**: precise overlap
- **Difference**: what our method does differently
```

Rules:
- Filename: `{source}-{id}.md` with dots → hyphens (e.g. `arxiv-2509.09162.md`).
- If a file already exists from a prior run, **do not overwrite it** — append
  this run's number to `also_found_in` and amend the notes if you have new
  information. The `found_in_run` and `found_by_role` fields are immutable.
- Only create files for papers you have actually read and classified — not
  every search hit.

### Consolidated summary (`references/literature-summary.md`)
The lead updates this file in Step 4. It is a 3–5 page synthesis of the entire
reference library, organized by relation type, with one-line entries linking to
the per-reference files. It is **cumulative** — a rerun adds to it, it does not
replace it.

## Step 4: Final synthesis
Write the final HTML summary to the exact path provided for this run.
Do not overwrite an earlier run summary.

**Also update `references/literature-summary.md`** — the consolidated reference
library summary. This is a required deliverable alongside the HTML summary. The
file is cumulative: read the existing version (if any), integrate new references
from this run, and rewrite it to reflect the complete current library. Organize
by relation type (direct prior work, theoretical foundations, related methods,
existing implementations), with one-line entries linking to the per-reference
files in `references/papers/`. Target 3–5 pages. Include a "Key findings"
section summarizing the latest run's conclusions and a "Coverage gaps" section
for what remains unexplored.

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
8. **Readiness assessment and recommendation.** Evaluate explicitly:

   a. **Is the literature sufficient to proceed to Phase 02?** Can the team
      brainstorm new methods with the current evidence base? If yes, recommend
      proceeding and state what aspects of the literature are most relevant.

   b. **Does the literature need improvement before Phase 02?** If there are
      coverage gaps, missing recent work, or unclear theoretical foundations,
      recommend rerunning this phase with a specific focus (e.g., "survey
      non-reversible MCMC methods," "update with 2024-2026 papers"). State
      exactly what is missing.

   c. **Is the research direction viable?** If the literature reveals that the
      proposed approach is already solved, or that the problem is fundamentally
      harder than expected, state this honestly with specific evidence.

   State the recommendation clearly as one of: **proceed**, **improve
   literature**, or **reconsider direction**. Justify with specific evidence
   from the survey.

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
