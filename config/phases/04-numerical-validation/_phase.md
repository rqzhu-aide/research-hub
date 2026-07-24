# Phase: Draft Assembly

## Goal
Produce a formal draft of the research paper for the selected method. Three
members work **in parallel**, each writing their section independently. The
research lead then combines the three sections into one coherent manuscript.

**One method per run.** If the user specifies which idea to pursue, the team
works on that one. If the user does not specify, the **research lead decides**
which idea from the Phase 3 rankings to pursue, and states the choice and
reasoning clearly.

## Parallel structure
All three members work independently in round 1:

| Member | Deliverable |
|--------|-------------|
| **Research Lead** | Introduction + method section draft |
| **Theorist** | All theory-related results, detailed proofs |
| **Data Analyst** | Implement the method, run simulations + real data analysis, produce an empirical report with tables and figures |

In round 2, the lead reads all three sections, reconciles notation and framing,
and combines them into a single formal draft.

## Relevant protocol elements (carried from the prior design)
The data analyst's empirical work retains these scientific-integrity practices:
- **Pre-specify** what experiments will test before running them (what metrics,
  what comparisons, what would support or contradict the method's claims).
- **Diagnostic checks first**: simple invariants, known-answer cases, and
  sanity checks before the main benchmark study.
- **Quantify numerical uncertainty**: report MCSE, confidence intervals, or
  bootstrap estimates for every empirical claim.
- **Computational reproducibility**: record seeds, software versions, hardware,
  and the exact commands needed to reproduce each result.

The heavy sealed-protocol-checkpoint machinery (hash-locked study designs,
cross-stage audits, protocol-only first rounds) has been **archived** — it
belonged to the old sequential structure and is not needed for parallel
drafting.

## Prior information
Requires a current Phase 03 summary approved by the user (contains the idea
rankings). If the user specifies an idea in the run-start form, the team works
on that idea. If not, the lead selects one from the Phase 3 rankings and states
the choice. The lead must identify the idea by its Phase 2 method ID and the
Phase 3 evaluation outcome.

## Files and outputs
Write all outputs under `numerical/run/NN/`:

- `round-01/research_lead.md`: introduction + method section
- `round-01/theorist.md`: theory section with proofs
- `round-01/data_scientist.md`: empirical report with tables, figures, and data
- `round-02/research_lead.md`: combined formal draft
- Write the HTML summary to the exact path provided for this run.

Each role report begins with Complete, Partial, or Failed as defined in the team
norms.

## Files in this folder
- `_lead.md`: instructions for the research lead.
- `research_lead.md`: intro + method section instructions.
- `theorist.md`: theory section instructions.
- `data_scientist.md`: implementation + empirical report instructions.
- `archive-v1-sequential-protocol/`: the prior sequential-protocol design,
  archived for reference. Not used by the current phase.

## What the user decides
The user starts every run and may specify which idea to pursue. After the
combined draft is produced, the user decides whether to approve it, request
revision, or rerun with a different idea.
