---
sidebar_position: 2
title: "Phase 1: Literature Review"
slug: /workflow/phase-1
---

# Phase 1: Literature Review

Survey relevant prior work, produce structured notes, and identify the gaps your project will address.

## At a glance

| | |
|---|---|
| **Pattern** | Parallel |
| **Participants** | Theorist, Research Lead, Data Analyst |
| **Rounds** | 1–5 (default 2) |
| **Output** | `references/` |
| **Prerequisites** | None |

## How it works

### Round 1: Independent search

Each role searches the literature from their own angle, **without reading each other's work**:

- **Theorist**: finds **theoretical foundations** — the mathematical frameworks the project builds on (e.g., Bakry–Émery theory, hypocoercivity, optimal transport). Identifies which theoretical tools exist and which gaps remain.
- **Research Lead**: finds **direct prior work** — the closest existing contributions that must be differentiated from. Establishes how to position the project's contribution and what makes it novel.
- **Data Analyst**: finds **existing implementations** and **computational approaches**. Identifies benchmarks, standard evaluation targets, and practical algorithms in the area.

### Round 2+: Cross-pollination

Roles read what the others found and fill gaps:
- A paper the theorist found might change how the research lead positions the contribution
- A benchmark the data scientist found might reveal an unexplored regime
- Roles propose additional searches based on cross-role insights

## Per-role responsibilities

### Theorist — theoretical foundations
- Find the **theoretical tools** the project will use (e.g., Γ₂ calculus, Wasserstein gradients, spectral graph theory)
- Identify **prior mathematical frameworks** that are related but distinct from the proposed approach
- Note which assumptions are standard and which would be novel
- Flag theoretical obstacles that the proposed methods will need to overcome

### Research Lead — positioning and closest prior work
- Find the **closest existing contributions** — the papers a reviewer would compare your work to
- Establish the **differentiation**: what does this project do that nothing else does?
- Identify the **research gap** the project fills
- Note how prior work has been positioned and what framing would be most compelling

### Data Analyst — computational landscape
- Find **existing implementations** of related methods (code, packages)
- Identify **standard benchmarks** and evaluation protocols in the area
- Note **computational approaches** that are established vs. novel
- Flag practical challenges (scalability, numerical stability) seen in prior work

## Output: folder structure

After a successful run, the `references/` directory contains:

```
references/
├── literature-review/
│   └── run/
│       └── 01/                         ← run number
│           ├── .directives/
│           │   ├── round-01.md         ← what each role was told to do
│           │   └── round-02.md
│           ├── round-01/
│           │   ├── theorist.md         ← theoretical foundations found
│           │   ├── research_lead.md    ← prior work and positioning
│           │   └── data_scientist.md   ← implementations and benchmarks
│           └── round-02/
│               └── ...                 ← cross-pollination outputs
│
├── papers/                             ← per-reference summary files
│   ├── arxiv-2509.09162.md             ← one file per cited paper
│   ├── arxiv-2603.03268.md
│   └── ...
│
└── literature-summary.md               ← consolidated summary (read this first)
```

### Per-reference files (`references/papers/`)

Each cited paper gets a markdown file with YAML frontmatter:

```yaml
---
arxiv_id: "2509.09162"
title: "Exact title from the citation"
authors: ["Author One", "Author Two"]
year: 2025
relation: "direct prior work"     # or: theoretical foundation / related method / existing implementation
found_in_run: "06"
found_by_role: "research_lead"
also_found_in: ["07"]
---

# arXiv:2509.09162 — Short Title

## One-line summary
What this paper does, in one sentence.

## Relevance to this project
2-4 sentences: why it matters here, how it relates to the candidate contribution.

## Key results / tools
- Specific theorem, algorithm, or data the project references
```

### Consolidated summary (`literature-summary.md`)

A single document with:
- A table of all papers, their relation to the project, and which role found them
- The landscape of prior work (what exists, what's established, what's open)
- The identified gaps the project could fill

**Downstream phases read this summary first** for orientation, then check individual reference files when evaluating specific methods.

## Reruns

Phase 1 can be rerun when:
- You want to search a **broader or different** area
- New papers have appeared since the last run
- A later phase revealed relevant literature the initial run missed

### Rerun protocol

1. **Audit**: read the existing `references/papers/` and `literature-summary.md`. Identify what's already covered and what's missing.
2. **Extend**: search for additional literature. Add new per-reference files. **Do not delete** existing reference files.
3. **Update the summary**: rewrite `literature-summary.md` to incorporate both old and new references. The old summary is preserved in the prior run's output directory.
4. **Never replace**: prior run outputs at `references/literature-review/run/01/` stay sealed. The new run writes to `run/02/`, `run/03/`, etc.

### What changes downstream when you rerun Phase 1

If you approve the rerun, Phases 2–5 are marked **stale** (because their literature context changed). You decide whether to rerun them. When you rerun Phase 2, the agents are told that the existing literature folder and summaries are available for consideration.

## What Phase 1 produces for Phase 2

Phase 2 (Method Development) receives Phase 1's approved summary as a trusted input. The method proposals in Phase 2 are explicitly checked against the literature:
- Don't propose a method that merely redoes classified prior work
- Position new methods relative to what was found in Phase 1
- Use the per-reference files to see exactly which prior papers are relevant
