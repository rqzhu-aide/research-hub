# Phase: Paper Assembly & Review

## Goal
Transform the separate Phase 1 through Phase 4 artifacts into a final
manuscript through two
run modes: **assembly** (combine everything into one paper) then **review and
revision** (independent audit + revision into the final manuscript).

## Two run modes

This phase has two run modes, selected at launch:

### Assembly mode
The research lead combines the Phase 1 through Phase 4 artifacts into one
coherent manuscript.
This is the convergence point. It is the first time the entire research thread
appears in a single document.

### Review-revision mode (gated by an approved assembly run)
The paper reviewer audits the assembled manuscript, then the research lead
revises it. This mode can be run iteratively on the same assembly, allowing
multiple review passes without reassembling the paper.

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

**Stage 1: Review (paper_reviewer):** read the assembled manuscript
independently. Produce a structured review using the `stat-paper-reviewer` skill:
soundness, clarity, significance, originality, ranked weaknesses (fatal/major/
minor), specific revision recommendations, missing references, scores, overall
assessment.

**Stage 2: Revise (research_lead):** address every review point. Use the
`stat-paper-writing` skill during revision. Fix, defer (with reasoning), or
push back (with reasoning). Produce the final revised manuscript plus a
mandatory revision log.

## Skill requirement
- **Paper reviewer** uses the `stat-paper-reviewer` skill.
- **Research lead** uses the `stat-paper-writing` skill when assembling and
  revising.

## Prior information

Assembly mode requires intact, completed results from Phases 1 through 4. The
run must receive the completed Phase 1 literature result; the completed Phase 2
method-development result and its published canonical definition; the completed
Phase 3 theoretical result; and the completed Phase 4 empirical result.
Each result must be present, readable, and pass its integrity check.

The Phase 3 and Phase 4 results must match the same stable ID, version, and
definition digest selected for the Phase 5 run. Neither sibling result
substitutes for the other, and results from different method branches or
versions must not be combined.

**Review-revision mode** additionally requires a prior approved Phase 5
assembly run for the same method identity. That assembled manuscript is the
object reviewed and revised.

**On rerun:**

- **Assembly rerun:** use the prior assembly as comparison evidence. Incorporate
  updated same-branch Phase 3 or Phase 4 results, correct notation
  inconsistencies, and strengthen incomplete sections.
- **Review-revision rerun:** use the prior review and revision as comparison
  evidence. Conduct an independent re-review and produce a fresh revision that
  addresses remaining weaknesses.

## Files and outputs
Write all outputs under `branches/<stable_id>/draft/revised/run/NN/`:

- Assembly mode: the assembled manuscript at `round-01/research_lead.md`
- Review-revision mode:
  - the structured review at `round-01/paper_reviewer.md`
  - the revised manuscript and revision log at `round-02/research_lead.md`
- Write the HTML summary to the exact path provided for this run.

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

- **approve**: the manuscript is ready for submission
- **revise further**: run another review-revision cycle
- **return to Phase N**: the theory, experiments, or literature needs more work
- **dead end**: the method cannot be supported; select a different one

The final manuscript from review-revision mode is the deliverable. It can be
packaged and sent as a complete paper.
