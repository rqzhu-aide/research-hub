# Phase: Paper Assembly & Review

## Goal
Transform the separate Phase 1–4 artifacts into a final manuscript through two
run modes: **assembly** (combine everything into one paper) then **review and
revision** (independent audit + revision into the final manuscript).

## Two run modes

This phase has two run modes, selected at launch:

### Assembly mode
The research lead combines the Phase 1–4 artifacts into one coherent manuscript.
This is the convergence point — the first time the entire research thread lives
as a single document.

### Review-revision mode (gated by an approved assembly run)
The paper reviewer audits the assembled manuscript, then the research lead
revises it. Can be run iteratively on the same assembly — multiple review
passes without re-assembling.

## What the lead assembles (assembly mode)

The lead combines material from ALL upstream phases:

- **Introduction** (written fresh): motivate the problem, state the contribution,
  position against prior work.
- **Method** (from Phase 2): the precise method definition — what was proposed.
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

**Stage 1 — Review (paper_reviewer):** read the assembled manuscript
independently. Produce a structured review using the `stat-paper-reviewer` skill:
soundness, clarity, significance, originality, ranked weaknesses (fatal/major/
minor), specific revision recommendations, missing references, scores, overall
assessment.

**Stage 2 — Revise (research_lead):** address every review point. Use the
`stat-paper-writing` skill during revision. Fix, defer (with reasoning), or
push back (with reasoning). Produce the final revised manuscript plus a
mandatory revision log.

## Skill requirement
- **Paper reviewer** uses the `stat-paper-reviewer` skill.
- **Research lead** uses the `stat-paper-writing` skill when assembling and
  revising.

## Prior information
Requires a current Phase 04 summary approved by the user (experiment results).
Phases 01–03 are also provided.

**Review-revision mode** additionally requires a prior approved Phase 05
assembly run for the same method branch — the assembled manuscript is the
input to the review.

**On rerun:**

- **Assembly rerun:** the prior assembly is comparison evidence. Improve on it
  — incorporate new Phase 3/4 results, fix notation inconsistencies, deepen
  thin sections.
- **Review-revision rerun:** the prior review and revision are comparison
  evidence. Conduct an independent re-review and produce a fresh revision that
  addresses any remaining weaknesses.

## Files and outputs
Write all outputs under `branches/<stable_id>/draft/revised/run/NN/`:

- Assembly mode: `round-01/research_lead.md` — assembled manuscript
- Review-revision mode:
  - `round-01/paper_reviewer.md` — structured review
  - `round-02/research_lead.md` — revised manuscript + revision log
- Write the HTML summary to the exact path provided for this run.

**This phase continues a method branch.** The exact method identity (stable ID +
version) is frozen into this run. Read the branch's Phase 01–04 outputs and
assemble/review the paper for that specific method. Different methods accumulate
in separate branch folders.

## Files in this folder
- `_lead.md`: instructions for the research lead.
- `paper_reviewer.md`: instructions for the paper reviewer.

## What the user decides
The user starts every run. After each run, the lead presents a **readiness
assessment** with a clear recommendation:

- **approve** — the manuscript is ready for submission
- **revise further** — run another review-revision cycle
- **return to Phase N** — the theory, experiments, or literature needs more work
- **dead end** — the method cannot be supported; select a different one

The final manuscript from review-revision mode is the deliverable — it can be
packaged and sent as a complete paper.
