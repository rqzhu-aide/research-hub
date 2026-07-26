---
sidebar_position: 5
title: "Phase 4: Implementation & Experiments"
slug: /workflow/phase-4
---

# Phase 4: Implementation & Experiments

Implement the selected method in code, run pre-specified experiments with diagnostics, and validate theoretical predictions against measured results.

## At a glance

| | |
|---|---|
| **Pattern** | Parallel |
| **Participants** | Research Lead, Theorist, Data Analyst |
| **Run modes** | Preliminary (default), Comprehensive |
| **Rounds** | 1–2 (mode-dependent) |
| **Output** | `branches/<method>/draft/sections/` |
| **Method-bound** | Yes |
| **Prerequisites** | Phase 3 (Theoretical Development) |

## Run modes

Phase 4 has two run modes, selected at launch:

### Preliminary — implement & test

The first implementation pass. The data analyst writes the code and runs diagnostic checks (known-answer cases, invariants, sanity tests). The theorist audits whether the diagnostics make sense. The goal is a **working, validated implementation** — not yet a full benchmark suite.

- **1 round** — implement, test, validate
- The lead specifies the experiments **before** results are known (pre-registration)
- Diagnostic failures must be reported honestly — no hiding broken code

### Comprehensive — benchmark (gated)

The full experimental suite. Requires a prior approved **preliminary** run for the same method branch. The data analyst runs the full benchmark with real parameter sweeps, comparison baselines, and scaling tests. The theorist audits whether measured results match the proved rate bounds.

- **2 rounds** — implement/extend + cross-audit
- Real measured data in tables and figures — no stubs, no zeros
- The theorist's audit is mandatory: do the experiments confirm the theory?

## How it works

### Round 1: Independent work

Each role works independently:

| Role | Responsibility |
|------|---------------|
| **Data Analyst** | Implement the algorithm, write diagnostic tests, run initial/comprehensive experiments |
| **Theorist** | Prepare the theoretical predictions (rate bounds, convergence guarantees) for the auditor to check against |
| **Research Lead** | Pre-specify the experiment plan, frame the implementation description, interpret results |

### Round 2 (comprehensive only): Cross-audit

- The **theorist audits** experimental results against proved bounds — does reality match theory?
- The **data analyst** runs the full benchmark and produces final tables/figures
- The **lead** synthesizes the implementation description and interprets the results

## Per-role responsibilities

### Research Lead
- **Pre-specify experiments**: define what will be tested *before* results are known (prevents p-hacking)
- **Implementation description**: describe the algorithm and its computational cost
- **Synthesis**: combine code, results, and theory-experiment agreement into a coherent package
- **Interpretation**: what do the numbers mean? Do they support the paper's claims?

### Data Analyst
- **Implementation**: write working, tested code for the method
- **Diagnostics**: run known-answer cases, invariant checks, convergence tests first
- **Experiments**: run the pre-specified experiment plan with real parameters
- **Results**: produce tables and figures with **real measured data**
- **Honest reporting**: negative results must be reported with specific numbers, never omitted

### Theorist
- **Predictions**: state what the proved bounds predict for the experimental setup
- **Audit**: verify that experimental results match the proved bounds. If the measured spectral gap doesn't satisfy the lower bound, investigate why
- **Discrepancy report**: if code and theory disagree, flag it explicitly

## Strict requirements

Phase 4 has hard requirements that, if unmet, cause the run to fail:

- **Working code is mandatory.** A report without actual code files is a failed run.
- **Real diagnostic numbers are mandatory.** A stub JSON with zero values is a failed run.
- **Experiments must be pre-specified** by the lead before results are known.
- **Negative results must be reported** honestly with specific numbers.
- **The theorist's audit is mandatory.** If they find a discrepancy between code and theory, it must be addressed.

## Gate: comprehensive requires preliminary

The **comprehensive** mode requires a prior approved **preliminary** run for the same method branch. This prevents running expensive benchmarks before the basic implementation is validated.

If you try to launch comprehensive without a prior approved preliminary run, the UI will block it with an explanation.

## Output: folder structure

```
branches/
└── <method-stable-id>/
    └── draft/
        └── sections/
            └── run/
                └── 01/
                    ├── .directives/
                    ├── round-01/
                    │   ├── data_scientist.md    ← implementation + diagnostics
                    │   ├── theorist.md           ← predictions for audit
                    │   └── research_lead.md      ← experiment plan + interpretation
                    └── round-02/                 ← comprehensive: full benchmark + audit
                        └── ...
```

## Reruns

### Rerun protocol

1. **Audit**: read every prior output for this method. Identify what's correct, incomplete, wrong, or missing — both in the code and in the experiments.
2. **Fix**: correct errors, tighten claims, improve the implementation.
3. **Add**: extend with additional experiments, baselines, or analysis the prior run lacked. Incorporate updated theory if Phase 3 was rerun.
4. **Never replace**: prior run directories stay sealed. The new run writes to a new run number.

### What triggers a Phase 4 rerun?

- The experiments were **incomplete** or the diagnostics failed
- Phase 3 was rerun with **new or sharper** theorems
- The implementation needs **additional baselines** or comparisons
- A review identified **issues** that need re-implementation

## What Phase 4 produces for Phase 5

Phase 4's approved summary tells Phase 5:
- The **working implementation** and code
- The **experimental results** (tables, figures, numbers)
- The **theory-experiment agreement** assessment
- Any **known weaknesses** to address during paper assembly

Phase 5 then assembles the paper from these results.
