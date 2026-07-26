---
sidebar_position: 4
title: "Phase 3: Theoretical Development"
slug: /workflow/phase-3
---

# Phase 3: Theoretical Development

Take the selected method from Phase 2 and **develop its theory rigorously**: prove theorems, establish rate bounds, assess computational feasibility, and position the contribution.

## At a glance

| | |
|---|---|
| **Pattern** | Debate |
| **Participants** | Theorist, Research Lead, Data Analyst |
| **Rounds** | 2–3 (default 2) |
| **Output** | `branches/<method>/evaluations/` |
| **Method-bound** | Yes — output routes to the selected method's branch |
| **Prerequisites** | Phase 2 (Method Development) |

## How it works

### Round 1: Independent development

Each role works independently on their aspect, **without reading each other's work**:

- **Theorist**: derives and proves the main theorems. Produces **actual theorems with full proofs** — not just sketches. Establishes rate bounds (e.g., spectral gap lower bounds via Bakry–Émery Γ₂ calculus). Identifies every assumption, hidden or explicit.
- **Data Analyst**: assesses **computational feasibility** — can this be implemented? At what cost? Evaluates numerical stability. Proposes concrete experiment designs that would validate or challenge the theory.
- **Research Lead**: identifies the **contribution structure** — what was proved, what it means, how it positions. Structures the paper's narrative.

### Round 2+: Debate

Roles read each other's Round 1 work and **challenge** it:

- Does the theorist's proof actually hold? Where are the gaps?
- Is the data scientist's cost assessment realistic?
- Does the research lead's positioning accurately reflect what was proved?

Roles **concede** when persuaded (with reasoning) or **hold** their position (with reasoning). The goal is convergence toward a defensible set of claims. This debate structure is what makes Phase 3 different from Phase 2's cross-pollination — here, claims are directly challenged, not just built upon.

## Per-role responsibilities

### Theorist
- **Derive and prove** the main results for the selected method
- Produce **actual theorems with full proofs** (Bakry–Émery Γ₂ derivation, spectral gap bounds, stationarity verification)
- State all **assumptions** explicitly — which are standard, which are novel
- Flag where the proof is **incomplete** or relies on conjecture
- In debate rounds: defend proofs against critique, or concede gaps honestly

### Data Analyst
- Assess **computational cost**: per-step complexity, memory, scalability
- Evaluate **numerical stability**: will the method blow up? Under what conditions?
- Identify the **key algorithmic challenges** (e.g., divergence correction, sparsity management)
- Propose **experiment designs**: what targets, what baselines, what would confirm or refute the theory

### Research Lead
- Identify the **contribution structure**: what are the headline results?
- **Position** against existing work from Phase 1 — how does this advance the field?
- Structure the **paper's narrative**: what should the paper emphasize?
- Assess **strength of evidence**: is this ready for a paper, or are there critical gaps?

## Output: method-bound branches

Phase 3 is **method-bound**: its output routes to a per-method branch directory. This isolates each method's evaluation history.

```
branches/
└── spectral-graph-coupling/              ← the selected method
    └── evaluations/
        └── run/
            ├── 01/                        ← Run 1
            │   ├── .directives/
            │   │   ├── round-01.md
            │   │   └── round-02.md
            │   ├── round-01/
            │   │   ├── theorist.md        ← theorems with full proofs
            │   │   ├── data_scientist.md  ← cost analysis + experiment design
            │   │   └── research_lead.md   ← contribution structure + positioning
            │   └── round-02/
            │       └── ...                ← debate: challenges, concessions, convergence
            ├── 02/                        ← Run 2 (if rerun)
            │   └── ...
            └── 04/                        ← Run 4 (audit/fix/extend of prior runs)
                └── ...
```

### Why method branches?

Without branching, all methods' Phase 3 outputs would pile into the same `evaluations/run/` directory. Branches solve this:

- Each method gets its own clean run history (`run/01/`, `run/02/`, ...)
- A future Phase 4 run for method X reads only from method X's branch
- Multiple methods can be evaluated in parallel without collision

The method identity is **sealed** in the run manifest at launch — it cannot change mid-run:

```json
"method_selection": {
  "stable_id": "spectral-graph-coupling",
  "version": "v1",
  "source": "approved_phase_02_selection"
}
```

## Reruns

### Rerun protocol

1. **Audit**: read every prior round output for this method. For each existing theorem, proof, or assessment, identify what's correct, incomplete, wrong, or missing. Write the audit findings.
2. **Fix**: correct errors, fill proof gaps, tighten claims. Build on prior work.
3. **Add new material**: extend with sharper bounds, additional theorems, or deeper analysis. Incorporate the updated literature library if Phase 1 was also rerun.
4. **Never replace**: prior run directories (`run/01/`, `run/02/`) stay sealed. The new run writes to `run/03/` or `run/04/`. The summary references both old and new material.

### What triggers a Phase 3 rerun?

- You want to prove a **sharper or different** bound
- Phase 2 was rerun and produced an **enriched method** definition
- Phase 1 was rerun with **new literature** that changes the positioning
- The initial proofs had **gaps** identified during review

## What Phase 3 produces for Phase 4

Phase 3's approved summary tells Phase 4:
- What was **proved** (theorem statements and conditions)
- The **rate bounds** and their derivation
- The **computational assessment** (feasibility, cost, stability)
- The **paper's narrative structure** (what to emphasize)
- Any **open problems** the draft should acknowledge

Phase 4 then writes the paper based on this evidence.
