# Phase: Paper Assembly & Review

## Goal
Assemble the research paper from the Phase 3 theoretical results and Phase 4
experimental results, then have it reviewed by an independent paper reviewer.
The research lead assembles the manuscript. The paper reviewer audits it.

## Role division

| Role | Primary responsibility | Audit responsibility |
|------|----------------------|---------------------|
| **Research Lead** | **Assemble** the paper: intro, method, theory (from Phase 3), experiments (from Phase 4), discussion | Respond to reviewer comments and revise |
| **Paper Reviewer** | **Review** the assembled paper independently | Identify weaknesses, gaps, missing elements |

This is a **sequential** two-stage process: assemble first, then review and revise.

## Study structure
**Sequential, 2 stages:**

1. **Assemble** (research_lead): combine the Phase 3 proofs, Phase 4 experiments,
   and Phase 1 literature context into a coherent manuscript. Reconcile notation,
   framing, and claims across all sections.
2. **Review** (paper_reviewer): read the assembled paper independently. Produce a
   structured review: soundness, clarity, significance, originality, missing
   elements, specific revision recommendations ranked by priority.
3. **Revise** (research_lead): address each review point. State what was changed,
   what was not changed (and why), and what remains open.

## What the lead assembles

The lead combines:

- **Introduction** (written fresh): motivate the problem, state the contribution,
  position against prior work.
- **Method** (from Phase 2 definition + Phase 3 development): precise definition
  of the method, its interaction structure, and its mechanism.
- **Theory** (from Phase 3): the proved theorems with full proofs. Use the
  theorist's actual output, not a re-derivation.
- **Experiments** (from Phase 4): the data analyst's measured results with
  tables and figures. Use the analyst's actual output.
- **Discussion**: what the results mean, limitations, open questions from Phase 3
  and Phase 4, connections to broader literature.

### Assembly requirements

- **Notation reconciliation**: ensure the same symbols mean the same thing in
  the method, theory, and experiments sections.
- **Claim consistency**: the intro's claims must match what the theory proves
  and what the experiments show. If the intro overclaims, narrow it.
- **Honest reporting**: do not soften the theorist's proofs or the analyst's
  negative results. Include limitations and counterexamples.
- **References**: assemble from all sections into one bibliography.

## Skill requirement
- **Paper reviewer** uses the `stat-paper-reviewer` skill.
- **Research lead** uses the `stat-paper-writing` skill when assembling and revising.

## Prior information
Requires a current Phase 04 summary approved by the user (experiment results).
Phases 01–03 are also provided.

**On rerun:** the prior Phase 05 run is provided as **comparison evidence** —
"here is the assembled manuscript, the review, and the revision history." The
new run must **improve on it**, not merely repeat it:

- **Address remaining review points**: if the prior review identified weaknesses
  that were not fully addressed, address them in the new revision.
- **Deepen sections**: if the prior manuscript was thin in some areas (e.g.,
  related work, discussion), expand them using the Phase 1–04 context.
- **Fix issues**: if the prior assembly had notation inconsistencies or framing
  mismatches, correct them.
- **Respond to new evidence**: if Phase 3 or 4 was rerun and produced new
  results, incorporate them into the manuscript.

The prior manuscript and review are starting material, not a constraint. The
new run should read them carefully and build on them.

## Files and outputs
Write all outputs under `branches/<stable_id>/draft/revised/run/NN/`:

- `round-01/research_lead.md`: assembled manuscript
- `round-02/paper_reviewer.md`: structured review
- `round-03/research_lead.md`: revised manuscript + revision log
- Write the HTML summary to the exact path provided for this run.

**This phase continues a method branch.** The exact method identity (stable ID +
version) is frozen into this run. Read the branch's Phase 03 theory and Phase 04
experiments under `branches/<stable_id>/` and assemble the paper for that specific
method. Different methods accumulate in separate branch folders.

## Files in this folder
- `_lead.md`: instructions for the research lead.
- `paper_reviewer.md`: instructions for the paper reviewer.

## What the user decides
The user starts every run. After the revised manuscript is produced, the lead
presents a **readiness assessment** with a clear recommendation:

- **approve** — the manuscript is ready for submission
- **revise further** — specific weaknesses need another revision cycle
- **return to Phase N** — the theory, experiments, or literature needs more work
- **dead end** — the method cannot be supported; select a different one

The final manuscript is the deliverable — it can be packaged and sent as a
complete paper.
