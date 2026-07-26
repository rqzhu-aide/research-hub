---
sidebar_position: 5
title: "Phase 4: Draft Assembly"
---

# Phase 4: Draft Assembly

## Purpose

Write the actual paper. Each role drafts their assigned sections, then the lead synthesizes everything into a formal manuscript.

## At a glance

| | |
|---|---|
| **Pattern** | Parallel |
| **Participants** | Theorist, Research Lead, Data Scientist |
| **Rounds** | 2 (fixed) |
| **Output** | `branches/<method>/draft/sections/` |
| **Method-bound** | Yes |

## Round structure

### Round 1: Independent section drafting
Each role writes their assigned sections independently:
- **Research Lead**: introduction (beyond-covariance framing), method section, discussion
- **Theorist**: theory and proofs sections (the main result, derivations, lemmas)
- **Data Scientist**: implementation description, experiments, numerical results

### Round 2: Combine and revise
- The lead **synthesizes** all sections into a coherent draft
- Roles revise based on how their sections fit with the others
- The data scientist runs **experiments** and produces real numbers
- The theorist **audits** the results against the proved rate bounds from Phase 3

## Per-role responsibilities

### Research Lead
- **Introduction**: frame the problem, state the contribution, position against prior work
- **Method section**: describe the method precisely
- **Discussion**: interpret results, state limitations, suggest future work
- **Synthesis**: combine all sections into a formal draft with consistent notation and narrative

### Theorist
- **Theory section**: state the main theorem with full proof
- **Derivations**: show the key mathematical steps (e.g., Bakry–Émery Γ₂ derivation)
- **Lemmas and propositions**: supporting results
- **Audit**: verify that experimental results match the proved bounds

### Data Scientist
- **Implementation**: describe the algorithm and its computational cost
- **Experiments**: run diagnostics (sanity checks) and benchmarks
- **Results**: produce tables and figures with real measured data
- **Honest reporting**: negative results must be reported with specific numbers

## Requirements

- The data scientist **must produce working code**. A report without actual code files is a failed run.
- The data scientist **must produce diagnostic results with real numbers**. A stub JSON with zero values is a failed run.
- Experiments **must be pre-specified** by the lead before the results are known.
- Negative results **must be reported honestly** with specific numbers.
- The theorist's **audit is mandatory**. If they find a discrepancy between code and theory, it must be addressed.

## Output

```
branches/<method>/draft/sections/run/01/
├── round-01/
│   ├── theorist.md          ← theory and proofs section
│   ├── data_scientist.md    ← implementation and experiments
│   └── research_lead.md     ← intro, method, discussion
└── round-02/
    └── ...                  ← combined and revised
```

## Rerun protocol

When Phase 4 is rerun, the lead treats it as an **audit and refinement** of the existing draft:

1. **Audit** every prior section for correctness, completeness, and accuracy
2. **Fix** errors and fill gaps in the existing material
3. **Add** new experiments, baselines, or analysis the prior run lacked
4. **Never replace** prior run files

The final summary references both prior and new material, noting what changed.
