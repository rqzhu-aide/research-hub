---
sidebar_position: 4
title: "Phase 3: Idea Evaluation"
---

# Phase 3: Idea Evaluation

## Purpose

Take the selected method and **develop its theoretical results rigorously**: prove theorems, establish rate bounds, assess computational feasibility, and position the contribution.

## At a glance

| | |
|---|---|
| **Pattern** | Debate |
| **Participants** | Theorist, Research Lead, Data Scientist |
| **Rounds** | 2–3 (default 2) |
| **Output** | `branches/<method>/evaluations/` |
| **Method-bound** | Yes — output routes to the selected method's branch |

## Round structure

### Round 1: Independent development
Each role works independently on their aspect:
- **Theorist**: derive and prove the main theorems
- **Data Scientist**: assess computational cost, implementation feasibility, numerical stability
- **Research Lead**: identify the contribution structure, position against literature, structure the paper's narrative

### Round 2+: Debate
Roles read each other's Round 1 work and **challenge** it:
- Does the theorist's proof actually hold? Where are the gaps?
- Is the data scientist's cost assessment realistic?
- Does the research lead's positioning accurately reflect what was proved?

Roles **concede** when persuaded (with reasoning) or **hold** their position (with reasoning). The goal is convergence toward a defensible set of claims.

## Per-role responsibilities

### Theorist
- **Derive and prove** the main results for the selected method
- Produce **actual theorems with full proofs** — not just sketches
- Establish **rate bounds** (e.g., spectral gap lower bounds via Bakry–Émery Γ₂ calculus)
- Identify what assumptions each result depends on
- Flag where the proof is incomplete or relies on conjecture

### Data Scientist
- Assess **computational feasibility**: can this be implemented? At what cost?
- Evaluate **numerical stability**: will the method blow up in practice?
- Estimate **implementation complexity** and identify the key algorithmic challenges
- Propose concrete **experiment designs** that would validate or challenge the theory

### Research Lead
- Identify the **contribution structure**: what was proved, what it means, how it positions
- Position against **existing work** from Phase 1
- Structure the **paper's narrative** — what should the paper emphasize?
- Assess the **strength of evidence**: is this ready for a paper?

## Output

Method-bound runs write to `branches/<stable_id>/evaluations/run/NN/`:

```
branches/spectral-graph-coupling/evaluations/run/
├── 01/
│   ├── .directives/
│   ├── round-01/
│   │   ├── theorist.md
│   │   ├── data_scientist.md
│   │   └── research_lead.md
│   └── round-02/
│       └── ...
└── 04/
    └── ...
```

Each round file contains the role's detailed work: full proofs, cost analyses, positioning arguments.

## Rerun protocol

When Phase 3 is rerun, the lead treats it as an **audit and refinement** of prior runs:

1. **Audit** every prior round output for correctness, completeness, and accuracy
2. **Fix** errors and fill proof gaps in the existing material
3. **Add** new theorems, sharper bounds, or deeper analysis
4. **Never replace** prior run files — write into the new run directory

The final summary references both prior and new material, noting what changed.

## What this phase produces for Phase 4

Phase 3's approved summary tells Phase 4:
- What was proved (the theorem statements and their conditions)
- The rate bounds and their derivation
- The computational assessment
- The paper's narrative structure

Phase 4 then writes the paper based on this evidence.
