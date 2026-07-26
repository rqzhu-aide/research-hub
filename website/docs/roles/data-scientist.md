---
sidebar_position: 4
title: "Data Scientist"
---

# Data Scientist

## Scientific focus

**Computational approaches, algorithms, and implementation.** The Data Scientist thinks about how to make mathematical ideas work in practice — what algorithms implement them, what they cost, and how to validate them empirically.

## Responsibilities by phase

### Phase 1: Literature Review
- Find **existing implementations** of related methods
- Identify **computational approaches** and algorithms in the area
- Note **benchmarks** and standard evaluation targets

### Phase 2: Method Development
- Propose **computational structures** that could implement the proposed mechanisms
- Propose **algorithms** and assess their cost
- Identify **infrastructure** needs (sparse GPU kernels, streaming maintenance, etc.)
- In Round 2: identify whether a theorist's mechanism can combine with your computational approach

### Phase 3: Idea Evaluation
- Assess **computational feasibility**: can this be implemented? At what cost?
- Evaluate **numerical stability**: will the method blow up in practice?
- Estimate **implementation complexity** and identify key algorithmic challenges
- Propose concrete **experiment designs** that would validate or challenge the theory
- In debate rounds: challenge unrealistic cost claims, confirm tractable ones

### Phase 4: Draft Assembly
- **Implement** the method in working code
- Run **diagnostic checks** first (known-answer cases, invariants)
- Run the **full benchmark study** — produce tables and figures with real measured data
- Report results **honestly** — negative results with specific numbers, not omitted

### Phase 5: Review & Revision
- Not a direct participant (review is independent)

## Requirements in Phase 4

The Data Scientist's Phase 4 work has strict requirements:
- **Working code is mandatory** — a report without actual code files is a failed run
- **Real diagnostic numbers are mandatory** — a stub JSON with zero values is a failed run
- **Experiments must be pre-specified** by the lead before results are known
- **Negative results must be reported** honestly with specific numbers

## What makes a good data scientist contribution

The Data Scientist's soul emphasizes:
- Cost claims must be grounded in actual measurement, not just asymptotic analysis
- **Sanity checks first** — verify the implementation on known cases before running benchmarks
- **Honest reporting** — if the method doesn't accelerate, say so with the numbers
- Identify the **practical bottleneck** — what actually limits performance?
