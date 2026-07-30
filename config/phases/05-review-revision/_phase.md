# Phase: Paper Assembly & Review

## Goal
Transform the separate Phase 1 through Phase 4 artifacts into a final
manuscript through two user-selected run modes: **assembly** updates the paper
from the current upstream records; **review and revision** independently audits
and revises the current paper.

## Two run modes

This phase has two run modes, selected at launch:

### Assembly mode
The research lead combines the Phase 1 through Phase 4 artifacts into one
coherent manuscript. On a rerun, the prepared current manuscript is the starting
draft and must be updated for the exact current upstream basis.

### Review-revision mode
This mode requires a verified current manuscript for the branch. The paper
reviewer audits an immutable snapshot of that manuscript, then the research lead
revises the current draft. The user may launch another review-revision run at
any time after the revised draft becomes current.

## What the lead assembles (assembly mode)

The lead combines material from ALL upstream phases:

- **Introduction** (written fresh): motivate the problem, state the contribution,
  position against prior work.
- **Method** (from Phase 2): the precise canonical definition of the proposed
  method.
- **Theory** (from Phase 3): the proved theorems with full proofs. Use the
  theorist's actual output, not a re-derivation.
- **Experiments** (from Phase 4): the data analyst's implementation, diagnostics,
  and benchmark results with tables and figures. Use the analyst's actual output.
- **Discussion**: what the results mean, limitations, open questions from Phases 3
  and 4, connections to broader literature.

### Assembly requirements

- **Notation reconciliation**: ensure the same symbols mean the same thing in
  the method, theory, and experiments sections.
- **Claim consistency**: the intro's claims must match what the theory proves
  and what the experiments show. If the intro overclaims, narrow it.
- **Honest reporting**: do not soften the theorist's proofs or the analyst's
  negative results. Include limitations and counterexamples.
- **References**: assemble from all sections into one bibliography.

## What the reviewer + reviser do (review-revision mode)

**Stage 1: Review (paper_reviewer):** read the frozen current manuscript
independently. Produce a structured review using the `stat-paper-reviewer` skill:
soundness, clarity, significance, originality, ranked weaknesses (fatal/major/
minor), specific revision recommendations, missing references, scores, overall
assessment.

**Stage 2: Revise (research_lead):** address every review point. Use the
`stat-paper-writing` skill during revision. Fix, defer (with reasoning), or
push back (with reasoning). Produce the complete revised `manuscript.md`, a
mandatory revision log, and an exact review-to-revision diff.

## Skill requirement
- **Paper reviewer** uses the `stat-paper-reviewer` skill.
- **Research lead** uses the `stat-paper-writing` skill when assembling and
  revising.

## Prior information

Phase 5 requires the canonical current records from Phases 1 through 4. The run
must receive the current Phase 1 literature record, current Phase 2 catalog and
selected definition, current Phase 3 theory package, and current Phase 4
empirical package. Each record must be present, readable, and pass its integrity
check.

The Phase 3 and Phase 4 results must match the same stable ID, version, and
definition digest selected for the Phase 5 run. Neither sibling result
substitutes for the other, and results from different method branches or
versions must not be combined.

**Review-revision mode** additionally requires a verified current Phase 5
`manuscript.md` for the same branch. No separate confirmation gate is required.

**On rerun:**

- **Assembly rerun:** update the prepared current manuscript for any changed
  Phase 1 through Phase 4 records, notation inconsistencies, or incomplete
  sections.
- **Review-revision rerun:** independently review the prepared current manuscript
  and revise it in response to the new review.

## Files and outputs
Write all outputs under `branches/<stable_id>/draft/revised/run/NN/`:

- Both modes must leave the complete paper at the exact run-root path
  `manuscript.md`.
- Assembly mode records the lead's stage report at
  `round-01/research_lead.md`.
- Review-revision mode:
  - the structured review at `round-01/paper_reviewer.md`
  - the revision response and log at `round-02/research_lead.md`
  - the exact unified diff at `manuscript-post-review.diff`
- Write the HTML summary to the exact path provided for this run.

Research Hub prepares `manuscript.md` from the verified current branch draft,
or from a template on the first assembly run. A valid Complete run atomically
replaces `branches/<stable_id>/draft/current/manuscript.md`. An incomplete or
invalid run leaves the previous current manuscript unchanged. Run-local reviews,
diffs, and summaries remain as records, but there is only one current paper.

**This phase continues one method branch.** The stable ID, version, canonical
definition, and definition digest are frozen into the run. Use only the supplied
Phase 3 theory and Phase 4 empirical results that match that identity. If either
result is missing or refers to another version or branch, stop and report the
mismatch rather than assembling incompatible evidence.

## Files in this folder
- `_lead.md`: instructions for the research lead.
- `paper_reviewer.md`: instructions for the paper reviewer.

## What the user decides
The user starts every run. After each run, the lead presents a **readiness
assessment** with a clear recommendation:

- **ready for submission**: the current manuscript supports submission
- **revise further**: run another review-revision cycle
- **return to Phase N**: the theory, experiments, or literature needs more work
- **dead end**: the method cannot be supported; select a different one

The user decides whether and when to run or rerun any phase, review the current
paper again, prepare it for submission, or defer further work.
