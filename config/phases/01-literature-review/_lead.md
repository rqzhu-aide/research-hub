# Lead Instructions: Literature Review

Coordinate independent searches by the three roles. In the final report, combine
the evidence by its source quality and relevance to the stated contribution.

## Responsibilities
1. Read the canonical current literature record, or initialize the literature
   record when no current record is available.
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
- the team norms and the canonical current literature record, when available
- `references/papers/`, the per-reference summary files (one `.md` per cited
  paper, built by prior runs). These are the project's structured reference
  library. Read them to understand what has already been found and classified.
- `references/literature-summary.md`, the consolidated literature summary
  (updated each run). Read it first for orientation.
- `ideas/` and `branches/` when present

Decide whether this is an initial survey or focused literature update. State the
current candidate:

- research question or estimand;
- proposed method, mechanism, or representation;
- scientific or statistical advance over prior work;
- conditions and scope under which the advance is expected to hold.

If any component is unclear, make its clarification part of the search.
If no current literature record exists, initialize it and state that this is
the first generation.

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
8. **Reference candidates.** Each role must include a complete candidate card
   for every new source it classifies. A source already represented by canonical
   identity or filename is not a delta candidate. The lead reconciles the new
   candidates and writes the run-local delta.
   Details are in the **Reference library** section below.

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

The canonical library lives at `references/papers/`, with one `.md` file per
cited source, plus `references/reference-index.json` and
`references/literature-summary.md`. It persists across runs and is read by
downstream phases. During this run, write only to the prepared
`reference-delta/` folder. Research Hub applies the delta to the canonical
library after validation.

### Delta cards (`reference-delta/papers/{source}-{id}.md`)
After comparing all role reports, the lead writes each reconciled new card using
this format:

```markdown
---
arxiv_id: "2509.09162"          # or doi, pmid, pmcid, github_repo, etc.
title: "Full paper title"
authors: ["Author1", "Author2"]
year: 2025
venue: "arXiv preprint"          # or conference/journal name
relation: "direct prior work"    # direct prior work | theoretical foundation | related method | existing implementation
found_in_run: "06"               # this run number
found_by_role: "research_lead"   # this role
---

# arXiv:2509.09162: Short Title

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
- Filename: a stable `{source}-{id}.md` name using letters, digits, dots,
  underscores, or hyphens, for example `arxiv-2509.09162.md`.
- If the canonical filename or identity already exists, do not write a delta
  card. Mention the source as already represented when it matters to the
  synthesis.
- Never create a second card for the same DOI, arXiv ID, PMID, PMCID, repository,
  or package under another filename.
- Only create files for sources actually read and classified, not
  every search hit.

### Consolidated summary (`reference-delta/literature-summary.md`)
The prepared file begins from the current synthesis. The lead rewrites it as a
compact complete view of the cumulative library after adding this run's new
unique sources. It is not a chronological transcript.

## Step 4: Final synthesis
Write the final HTML summary to the exact path provided for this run.
Do not overwrite an earlier run summary.

**Also update `reference-delta/literature-summary.md`.** This is a required
deliverable alongside the HTML summary. Integrate new evidence with the prepared
current synthesis and rewrite it to reflect the complete current library.
Organize by relation type, with one-line entries linking to the canonical paths
in `references/papers/`. Keep the synthesis compact. Include a "Key findings"
section for the current evidence and a "Coverage gaps" section for what remains
unexplored. Do not edit `_baseline.json`.

Begin with the User Decision Brief and comparison with the current record defined
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
5. one consolidated **Scientific record changes** section and the updated
   current literature synthesis, with initialization recorded when applicable;
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
user alone decides whether to rerun this phase, start Method Development, or
defer further work.

## Handoff briefs for downstream roles
Before submitting, write one brief per downstream consumer role as
`handoff/{role}.md` in the run output directory (a sibling of your round
reports). These briefs are the primary documents downstream agents read; the
full summary and decision record remain available for depth.

Write briefs for: **research_lead** (Phase 2 method scoping) and **paper_reviewer** (Phase 5 citations).

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

## Requirements
- Follow the shared team norms and use the current scientific record for this
  run.
- Require role reports to include only proposed **Scientific record changes**,
  not a reconstructed record. Reconcile those changes in the final summary and
  staged literature synthesis.
- Address the user direction already supplied in each run task.
- Calibrate originality to primary-source evidence.
- Treat unresolved overlap as unresolved, not as proof of originality.
- Give each later round a precise question that can be resolved by evidence.
