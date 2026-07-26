---
sidebar_position: 3
title: "Phase 2: Method Development"
---

# Phase 2: Method Development

## Purpose

Brainstorm **genuinely new ideas** — new mechanisms, frameworks, and insights that address the gaps identified in Phase 1. Propose multiple candidate methods, then select one for theoretical development.

## At a glance

| | |
|---|---|
| **Pattern** | Parallel |
| **Participants** | Theorist, Research Lead, Data Scientist |
| **Rounds** | 2–3 (default 2) |
| **Output** | `ideas/methods/` |

## Round structure

### Round 1: Independent brainstorm
Each role proposes multiple ideas from their own angle:
- **Theorist**: new mathematical mechanisms and frameworks (at least 2–3)
- **Research Lead**: new contributions, positioning, scientific value
- **Data Scientist**: computational structures, algorithms, implementation ideas

### Round 2: Cross-pollination
Roles read each other's ideas and:
- Identify whether mechanisms can **combine** (e.g., a theorist's mechanism + a data scientist's computational approach)
- **Refine** ideas based on cross-role insights
- Propose **new ideas** sparked by other perspectives

## Per-role responsibilities

### Theorist
Propose genuinely new **mathematical mechanisms**. For each idea:
1. The core mathematical novelty (new dynamics, geometric perspective, algebraic identity)
2. The target and obstacle — what quantity matters and why existing formulations fail
3. The unique position — what this enables that nothing else can
4. Logical reasoning with minimal notation (full proof not required at this stage)
5. Why it's mathematically interesting

### Research Lead
Propose new **contributions and positioning**:
- What scientific value does each idea offer?
- How does it position against the closest prior work?
- What's the strongest defensible claim?

### Data Scientist
Propose **computational approaches**:
- What algorithms could implement this?
- What's the computational cost?
- What infrastructure is needed?

## Output: the method menu

The lead publishes one markdown file per retained idea to `ideas/methods/`:

```
ideas/methods/
├── _registry.yaml                    ← permanent numbering
├── spectral-graph-coupling.md        ← status: recommended
├── nonreversible-composition.md      ← status: viable
├── multi-scale-rate-transfer.md      ← status: viable
└── cheeger-optimal-dn.md             ← status: retired
```

Each method file contains:
- **Frontmatter**: `stable_id`, `number`, `version`, `label`, `status`
- **Mathematical definition**: the precise formulation with LaTeX
- **Key property**: the invariant measure condition, rate bound conjecture, etc.

The lead selects one method as `recommended` — the proposed primary mechanism for Phase 3.

## Method numbering

Every method gets a **permanent integer number** (see [Method Registry](./../concepts/method-registry.md)). Numbers never get reused — retired or merged methods keep their number. Users refer to methods as "#1 Spectral graph coupling", "#5 Kernel-metric coupling", etc.

## Rerun protocol

When Phase 2 is rerun, the lead must:

1. **Re-evaluate** every existing method against four criteria: novelty, tractability, acceleration potential, differentiation from literature
2. **Retire** methods that score Weak/Insufficient on 2+ dimensions **AND** have no downstream records (never evaluated or implemented in Phase 3/4/5)
3. **Merge** substantially identical methods (same mechanism described differently), keeping the survivor with downstream records
4. **Never reuse** a method number
5. Consider **new methods** based on the updated literature library

## Decision

The user reviews the method menu and the lead's recommendation, then decides which method to evaluate in Phase 3. The user is not bound by the recommendation — they can choose any viable method.
