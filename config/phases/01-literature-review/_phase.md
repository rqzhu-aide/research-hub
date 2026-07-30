# Phase: Literature Review

## Goal
Assemble the evidence needed to evaluate the project's candidate contribution.
Distinguish four kinds of precedent:

1. **Direct prior work**: the same target, construction, formula, or scientific conclusion.
2. **Theoretical foundations**: established results that the project would use.
3. **Related methods**: related mathematical or computational ideas used for
   a different purpose or target.
4. **Existing implementations**: code, packages, benchmarks, or analysis
   procedures that already implement part or all of the idea.

State the candidate contribution in terms of the research question or estimand,
the proposed method or mechanism, the scientific or statistical advance, and
the conditions under which that advance is expected to hold. Record evidence
and uncertainty as changes to the current scientific record rather
than treating originality as a binary judgment.

## When this phase may be run
The user may run or rerun this phase at any time. No earlier phase is required.

**On rerun:** begin from the current reference library and synthesis. Search only
for new unique sources that are not already represented. Do not regenerate,
replace, or delete existing source cards. Do not repeat a search merely to
reproduce evidence already represented in the current library. A focused rescan
and an initial survey use the same role
instructions; they differ only in the lead's scientific questions.

## Study structure
All three roles search independently from their scientific perspective. The
research lead then writes an evidence-weighted synthesis that states the
best-supported conclusion, disagreements, uncertainty, and choices available to
the user.

## Files and outputs
Write role reports and the run summary under the exact run output root, normally
`references/literature-review/run/NN/`:

- `round-01/<role>.md`, `round-02/<role>.md`, ...: per-round outputs
- Write the HTML summary to the exact path provided for this run and do not
  overwrite earlier summaries.

Research Hub prepares a run-local reference delta at `reference-delta/` inside
the run root. The research lead must leave these exact deliverables there:

- `reference-delta/papers/`: one complete card for each new unique source;
- `reference-delta/literature-summary.md`: the complete current synthesis after
  incorporating this run.

Size budget: the staged synthesis must not exceed 5 MiB and each card must not
exceed 1 MiB — a staged file over budget fails sealing after the run. Keep the
synthesis evidence-weighted prose, not a dump of full paper text; quote
sparingly and cite cards instead.

Do not edit `reference-delta/_baseline.json`. Do not write directly to the live
`references/papers/`, `references/reference-index.json`, or
`references/literature-summary.md` paths during a run. Research Hub validates
and promotes a valid delta atomically. Existing reference cards are never
deleted by a Phase 1 run.

Each role report begins with Complete, Partial, or Failed as defined in the team
norms. Nonempty Partial and Failed reports preserve usable evidence and do not
prevent the lead from completing the configured run.

## Evidence standard
- Prefer primary papers, official documentation, and original repositories.
- State whether a source is direct prior work, a theoretical foundation, a
  related method, or an existing implementation. Similar vocabulary alone is
  not evidence of equivalence.
- Inspect the actual estimand, assumptions, formula, and computation before
  making an originality judgment.
- Preserve a compact search log: sources searched, dates, query families and
  synonyms, backward and forward citation paths, software searches, and the
  stopping rule.
- Use scientific relevance and evidence saturation, not a target source count.
  Stop when additional targeted searches do not change the closest-work set,
  contribution boundary, important assumptions, or material uncertainty.
- Phrase negative conclusions as "not found within the searched scope," then
  state that scope. Absence from a search is not proof of absence.
- State unresolved overlap with prior work and missing evidence explicitly.
- Follow the shared team norms. Use the canonical current literature summary and
  reference cards when available. If none is available, initialize the record
  and say so explicitly. Role reports include a
  **Scientific record changes** section. The final summary provides one
  consolidated **Scientific record changes** section and a compact current
  literature synthesis.

## User decisions
The user starts each run from the web UI and selects the number of rounds.
Completing a run reports the evidence but does not establish originality or the
contribution and does not start another phase. After a valid run, the current
reference record contains the cumulative library and new synthesis. The user may
rerun the phase with a narrower search, start another phase, or defer further
work at any time. The final summary begins with the User Decision Brief and a
comparison with the current literature record defined in the team norms.

## Files in this folder
- `_lead.md`: instructions for the research lead. Read this file first if you are
  the lead.
- `research_lead.md`, `theorist.md`, `data_scientist.md`: role-specific
  instructions.

## Search scope
An initial survey and a focused literature update use the same role instructions
and output structure. They differ only in the scientific questions assigned by
the lead. No separate set of instructions is needed for a more focused search.
