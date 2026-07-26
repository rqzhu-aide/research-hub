---
sidebar_position: 5
title: "Phase 4: Draft Assembly"
slug: /workflow/phase-4
---

# Phase 4: Draft Assembly

Write the paper. Each role drafts their assigned sections, then the lead synthesizes everything into a formal manuscript with real experiments.

## At a glance

| | |
|---|---|
| **Pattern** | Parallel |
| **Participants** | Theorist, Research Lead, Data Scientist |
| **Rounds** | 2 (fixed) |
| **Output** | `branches/<method>/draft/sections/` |
| **Method-bound** | Yes |
| **Prerequisites** | Phase 3 (Idea Evaluation) |

## How it works

### Round 1: Independent section drafting

Each role writes their assigned sections **independently**:

| Role | Sections |
|------|----------|
| **Research Lead** | Introduction (problem framing, contribution statement), Method section, Discussion |
| **Theorist** | Theory section (main theorem with full proof), derivations, lemmas |
| **Data Scientist** | Implementation description, experiments, numerical results |

### Round 2: Combine and revise

- The lead **synthesizes** all sections into a coherent draft with consistent notation
- Roles revise based on how their sections fit with the others
- The data scientist **runs experiments** and produces real measured data
- The theorist **audits** the experimental results against the proved rate bounds — does reality match theory?

## Per-role responsibilities

### Research Lead
- **Introduction**: frame the problem, state the contribution, position against prior work
- **Method section**: describe the method precisely with its mathematical definition
- **Discussion**: interpret results, state limitations, suggest future work
- **Synthesis**: combine all sections into a formal draft with consistent notation and a coherent narrative

### Theorist
- **Theory section**: state the main theorem with its full proof (carried over from Phase 3)
- **Derivations**: show the key mathematical steps step by step (e.g., Bakry–Émery Γ₂ derivation)
- **Supporting results**: lemmas, propositions, corollaries
- **Audit**: verify that experimental results match the proved bounds. If the measured spectral gap doesn't satisfy the lower bound, investigate why.

### Data Scientist
- **Implementation**: describe the algorithm and its computational cost
- **Experiments**: run diagnostic checks first (known-answer cases, invariants), then the full benchmark
- **Results**: produce tables and figures with **real measured data**
- **Honest reporting**: negative results must be reported with specific numbers, never omitted

## Strict requirements

Phase 4 has hard requirements that, if unmet, cause the run to fail:

- **Working code is mandatory.** A report without actual code files is a failed run.
- **Real diagnostic numbers are mandatory.** A stub JSON with zero values is a failed run.
- **Experiments must be pre-specified** by the lead before results are known (to prevent p-hacking).
- **Negative results must be reported** honestly with specific numbers.
- **The theorist's audit is mandatory.** If they find a discrepancy between code and theory, it must be addressed.

## Output: folder structure

```
branches/
└── spectral-graph-coupling/
        └── draft/
            └── sections/
                └── run/
                    └── 01/
                        ├── .directives/
                        ├── round-01/
                        │   ├── theorist.md         ← theory and proofs section
                        │   ├── data_scientist.md   ← implementation + experiments
                        │   └── research_lead.md    ← intro, method, discussion
                        └── round-02/
                            └── ...                 ← combined + revised + audited
```

The final synthesized draft is referenced in the HTML summary.

## Reruns

### Rerun protocol

1. **Audit**: read every prior section for this method. Identify what's correct, incomplete, wrong, or missing — both in the writing and in the experiments.
2. **Fix**: correct errors, tighten claims, improve clarity in the existing material.
3. **Add**: extend with additional experiments, baselines, or analysis the prior run lacked. Incorporate updated literature if Phase 1 was rerun.
4. **Never replace**: prior run directories stay sealed. The new run writes to a new run number.

### What triggers a Phase 4 rerun?

- The experiments were **incomplete** or the diagnostics failed
- Phase 3 was rerun with **new or sharper** theorems
- The draft needs **additional sections** or comparisons
- A review identified **writing issues** that need a full redraft

## What Phase 4 produces for Phase 5

Phase 4's approved summary tells Phase 5:
- The **complete draft** with all sections
- The **experimental results** (tables, figures, numbers)
- The **theory-experiment agreement** assessment
- Any **known weaknesses** the reviewer should focus on

Phase 5 then independently audits the complete draft.
