---
sidebar_position: 2
title: "Phase 1: Literature Review"
---

# Phase 1: Literature Review

## Purpose

Survey relevant prior work, produce structured notes, and identify gaps that the research project will address.

## At a glance

| | |
|---|---|
| **Pattern** | Parallel |
| **Participants** | Theorist, Research Lead, Data Scientist |
| **Rounds** | 1–5 (default 2) |
| **Output** | `references/` |

## Round structure

### Round 1: Independent search
Each role searches for literature from their own perspective:
- **Theorist**: theoretical foundations, prior mathematical frameworks
- **Research Lead**: direct prior work, the closest related contributions, how to position the project
- **Data Scientist**: existing implementations, computational approaches, benchmarks

### Round 2+: Cross-pollination
Roles read what the others found, identify gaps, and fill in missing areas. A paper found by the theorist might inspire the research lead to reconsider positioning; a benchmark found by the data scientist might reveal an unexplored regime.

## Per-role responsibilities

### Theorist
- Find the **theoretical foundations** the project builds on (e.g., Bakry–Émery theory, hypocoercivity, optimal transport)
- Identify prior **mathematical frameworks** that are related but distinct
- Note which theoretical tools are available and which gaps remain

### Research Lead
- Find **direct prior work** — the closest existing contributions that must be differentiated from
- Establish how to **position** the project's contribution
- Identify what makes this project novel relative to the literature

### Data Scientist
- Find **existing implementations** of related methods
- Identify **computational approaches** and algorithms in the area
- Note **benchmarks** and standard evaluation targets

## Output structure

The phase produces:

```
references/
├── literature-review/
│   └── run/           ← per-round role outputs
├── papers/            ← per-reference summary files
│   ├── arxiv-2509.09162.md
│   ├── arxiv-2603.03268.md
│   └── ...
└── literature-summary.md   ← consolidated summary
```

### Per-reference files (`references/papers/`)

Each cited paper gets a markdown file with YAML frontmatter:

```yaml
---
arxiv_id: "2509.09162"
title: "Exact title from the paper citation"
authors: ["Author list"]
year: 2025
relation: "direct prior work"   # or theoretical foundation / related method / existing implementation
found_in_run: "06"
found_by_role: "research_lead"
also_found_in: ["07"]
---
```

The body contains a one-line summary, relevance to the project, key results/tools, and classification.

### Consolidated summary (`literature-summary.md`)

A single document consolidating all references into:
- A table of all papers with their relation to the project
- The landscape of prior work
- The identified gaps

## Downstream use

Phase 2 (Method Development) reads the literature summary first for orientation, then checks individual reference files when considering whether a proposed method merely redoes classified prior work.

When the literature review is rerun, the summary is updated. Phase 2 reruns are told that the existing literature folder and summaries are available.
