---
sidebar_position: 3
title: "Phase 2: Method Development"
slug: /workflow/phase-2
---

# Phase 2: Method Development

Brainstorm **genuinely new ideas** — new mechanisms, frameworks, and insights that address the gaps identified in Phase 1. Propose multiple candidate methods, then select one for theoretical development.

## At a glance

| | |
|---|---|
| **Pattern** | Parallel |
| **Participants** | Theorist, Research Lead, Data Scientist |
| **Rounds** | 2–3 (default 2) |
| **Output** | `ideas/methods/` |
| **Prerequisites** | Phase 1 (Literature Review) |

## How it works

### Round 1: Independent brainstorm

Each role proposes multiple ideas from their own angle, **without reading each other's work**:

- **Theorist**: new **mathematical mechanisms** — new dynamics, geometric perspectives, algebraic identities, theoretical frameworks from other fields. At least 2–3 ideas.
- **Research Lead**: new **contributions and positioning** — what scientific value does each idea offer? How does it position against the closest prior work?
- **Data Scientist**: **computational structures** — algorithms that could implement the mechanisms, their cost, and infrastructure needs.

### Round 2: Cross-pollination

Roles read each other's ideas and:
- Identify whether mechanisms can **combine** (e.g., a theorist's mechanism + a data scientist's computational approach → a new composed method)
- **Refine** ideas based on cross-role insights
- Propose **new ideas** sparked by other perspectives
- Identify mathematical issues (e.g., "this parametrization produces zero drift")

## Per-role responsibilities

### Theorist
For each idea, state:
1. The **core mathematical novelty** (new dynamical structure, geometric insight, algebraic identity)
2. The **target and obstacle** — what quantity matters and why existing formulations fail
3. The **unique position** — what this enables that nothing else can
4. **Logical reasoning** with minimal notation (full proof not required at this stage — the idea needs to be sound, not rigorous)
5. **Why it's mathematically interesting**

### Research Lead
- What **scientific value** does each idea offer?
- How does it **position** against the closest prior work?
- What's the **strongest defensible claim** if the method works?

### Data Scientist
- What **algorithms** could implement this?
- What's the **computational cost**?
- What **infrastructure** is needed?

## Output: the method menu

The lead publishes one markdown file per retained idea to `ideas/methods/`:

```
ideas/
├── methods/
│   ├── _registry.yaml                    ← permanent numbering (see below)
│   ├── spectral-graph-coupling.md        ← status: recommended
│   ├── nonreversible-composition.md      ← status: viable
│   ├── multi-scale-rate-transfer.md      ← status: viable
│   ├── kernel-metric-coupling.md         ← status: viable
│   └── cheeger-optimal-dn.md             ← status: retired
│
└── run/
    └── 01/                               ← run outputs (round files)
        ├── .directives/
        ├── round-01/
        │   ├── theorist.md
        │   ├── research_lead.md
        │   └── data_scientist.md
        └── round-02/
            └── ...
```

### Method file format

Each method file contains rigorous mathematical definitions:

```markdown
---
stable_id: spectral-graph-coupling
number: 1
version: v1
label: Spectral graph coupling
status: recommended
---

# Spectral graph coupling

## Mathematical definition

$$D_N(X) = L_G \otimes K$$

where $L_G$ is the graph Laplacian of a sparse expander graph (degree
$d = O(\log N)$) and $K \in \mathbb{S}_{++}^d$ is a constant
positive-definite preconditioner.

**Key property**: The Fiedler eigenvalue $\sigma_2(L_G)$ acts as a
multiplicative accelerator. Conjectured rate bound:
$\lambda \geq \rho \cdot \sigma_2(L_G) \cdot \lambda_{\min}(K)$
under strong log-concavity $-\nabla^2 \log p \succeq \rho I_d$.
```

The lead selects exactly one method as `status: recommended` — the proposed primary mechanism for Phase 3.

## Method numbering

Every method gets a **permanent integer number** that survives retirement and merge. This gives each method a stable, human-friendly handle.

### The registry file

`ideas/methods/_registry.yaml` is the single source of truth:

```yaml
next_number: 8
entries:
  - number: 1
    stable_id: spectral-graph-coupling
    label: Spectral graph coupling
    status: recommended
    added_in_run: f14ad9b2-...
  - number: 4
    stable_id: cheeger-optimal-dn
    label: Cheeger-optimal D_N
    status: retired
    added_in_run: f14ad9b2-...
    retired_in_run: 9bc360f2-...
```

### Rules

- **Numbers never get reused.** A retired or merged method keeps its number. `next_number` only increases. Gaps are never filled.
- **Every method file has a `number:` field** in frontmatter matching the registry.
- **Users refer to methods by number**: "#1 Spectral graph coupling", "#5 Kernel-metric coupling". The number is the method's identity for the life of the project — names can drift, status can change, but "#4" always means the same method.

This is the "jersey number" principle: once assigned, the number is permanent.

## Reruns

Phase 2 is the most complex phase to rerun. The rerun protocol includes four operations:

### 1. Re-evaluate existing methods

Every existing method is re-assessed against four criteria:
1. **Novelty** — is it genuinely new?
2. **Tractability** — can it be proved with current tools?
3. **Acceleration potential** — does it actually offer improvement?
4. **Differentiation** — is it fundamentally different from prior work?

### 2. Retire weak methods

A method is **retired** (`status: retired`) if **both** conditions hold:
- Scores **Weak or Insufficient** on 2+ of the four criteria
- Has **no downstream records** — never evaluated in Phase 3, never drafted in Phase 4

A method that has already been evaluated or implemented downstream is **never retired** — it's part of the project's history.

When retiring: set `status: retired` in the method file, add a `## Retirement reason` section explaining which criteria failed, and update the registry with `retired_in_run`.

### 3. Merge duplicate methods

If two methods are **substantially identical** (same core mechanism, same math, same unique position — just worded differently), merge them:

1. **Survivor**: prefer the method with downstream records. If neither has any, prefer the more complete definition. If tied, alphabetical `stable_id`.
2. **Merge files**: copy unique content from the absorbed file into the survivor. Add a `## Merged from` section.
3. **Downstream records stay sealed**: if the absorbed method was run in Phase 3/4/5, those artifacts stay in place. Note the provenance in the survivor's `## Merged from` section.
4. **Retire the absorbed file**: `status: retired` with reason `merged into <survivor_stable_id>`.

A merge is for **the same mechanism described differently** — not for methods that are merely related or composable.

### 4. Add new methods

The lead can also propose **new methods** based on the updated literature library. New methods get the next available number from the registry.

### What stays sealed

Prior run outputs (`ideas/run/01/`, `ideas/run/02/`) are never modified. The new run writes to `ideas/run/03/`, etc. Method files in `ideas/methods/` are updated in place (status changes, new versions) but never deleted.

## What Phase 2 produces for Phase 3

The approved summary tells Phase 3:
- The **selected method** (the `recommended` one) and its mathematical definition
- The full **method menu** (all active methods with their status)
- Any **mathematical issues** found during brainstorming (e.g., "gradient-orthogonal A_N produces zero drift")

Phase 3 takes the selected method and develops its theory rigorously. The user chooses which method to evaluate — they're not bound by the recommendation.
