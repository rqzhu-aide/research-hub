---
sidebar_position: 2
title: "Creating a Project"
slug: /project-setup
---

# Creating a Project

A Research Hub project is a focused research effort with a clear goal, a research brief, and a five-phase pipeline. This page covers how to set up a project that produces good results.

## Step 1: Create the project

1. Open [http://127.0.0.1:5055](http://127.0.0.1:5055)
2. Click **New Project**
3. Enter a **project name** (this becomes the folder slug — keep it short and descriptive)
4. Write the **research brief** (see below)

The project appears as a new tab with five phase sub-tabs.

## Step 2: Write the research brief

The research brief (`setting.md`) is the single most important input. Every agent in every phase reads it. A vague brief produces vague research; a sharp brief produces sharp research.

### What a good brief contains

```markdown
# <Project Title>

## Research Goal

State the central question in one or two sentences. Be specific about what
you want to discover or prove, not just the general area.

> Can we construct finite-dimensional particle systems whose update rule
> entangles particles in a way that produces faster mixing than independent
> Langevin chains, while maintaining Π_N = p^⊗N as the exact stationary
> distribution for finite N?

## Background / What we already know

Summarize the starting point. What mathematical foundation are you building
on? What's the key equation or condition? What prior results are established?

## Scope and directions

List the directions you want explored. This guides Phase 2 (Method
Development) but doesn't constrain it — agents can propose directions you
didn't list.

- Direction A (e.g., graph-structured interactions)
- Direction B (e.g., non-reversible entanglement)
- Direction C (e.g., multi-scale coupling)

## Restrictions (optional but recommended)

State any constraints:
- "Focus on the finite-N regime, not mean-field limits"
- "Prioritize provable rate bounds over empirical heuristics"
- "The method must preserve the exact invariant measure, not approximate it"
- "Avoid approaches that require N → ∞ for the guarantee to hold"
```

### What makes a good research goal

| ✅ Good goal | ❌ Vague goal |
|-------------|-------------|
| "Can graph-structured interaction accelerate Langevin sampling with a provable rate bound?" | "Improve Langevin sampling" |
| "Does the Bakry–Émery Γ₂ calculus yield a tighter spectral gap for non-reversible ALDI?" | "Study non-reversible MCMC" |
| "Can memory-augmented interaction achieve entanglement beyond covariance preconditioning?" | "Explore new MCMC methods" |

A good goal is:
- **Specific** — names the mechanism, the quantity, and the comparison
- **Open-ended enough for creativity** — doesn't prescribe the answer
- **Constrained enough to be tractable** — has a clear success criterion

### Restrictions shape the research

Restrictions are how you steer the research without micromanaging it. Common restriction types:

- **Theoretical**: "Must preserve the exact invariant measure", "Prioritize provable bounds over empirical gains"
- **Computational**: "Must be implementable in O(N log N) per step", "Must work on GPU"
- **Scope**: "Finite-N only, not mean-field", "Focus on log-concave targets first"
- **Differentiation**: "Must be fundamentally different from ALDI and covariance preconditioning"

Without restrictions, agents may propose methods that are technically novel but not aligned with your actual research constraints. With too many restrictions, they can't be creative. The sweet spot is 2–4 clear constraints.

## Step 3: Understand the folder structure

When you create a project, Research Hub sets up:

```
<project-slug>/
├── setting.md                 ← your research brief (editable)
├── phase-summaries/           ← HTML decision briefs from each run
│   ├── 01-literature-review/
│   ├── 02-method-development/
│   ├── 03-idea-evaluation/
│   ├── 04-draft-assembly/
│   └── 05-review-revision/
├── references/                ← Phase 1 output (literature)
│   ├── literature-review/run/
│   ├── papers/                ← per-reference summary files
│   └── literature-summary.md  ← consolidated summary
├── ideas/                     ← Phase 2 output (methods)
│   ├── methods/               ← one file per proposed method
│   │   ├── _registry.yaml     ← permanent numbering registry
│   │   └── <method-slug>.md
│   └── run/
├── branches/<method-slug>/    ← Phase 3/4 output (per-method)
│   ├── evaluations/run/       ← Phase 3: theorems and proofs
│   └── draft/sections/run/    ← Phase 4: paper draft sections
└── draft/revised/             ← Phase 5 output (final manuscript)
```

### Editing the brief

You can edit `setting.md` at any time. The edit takes effect on the **next run** — runs that are already in flight read from the frozen copy made at launch. This is by design: a run's exact inputs must be reproducible.

### What agents can and cannot touch

- **Agents write to**: `references/`, `ideas/`, `branches/`, `draft/`, and the run's output directories
- **Agents do not touch**: the control directory (`.research-hub-control/`), run manifests, decision records
- **You control**: `setting.md` (the brief), `config.yaml`, and all approval decisions

## Step 4: Start the first phase

Once your brief is written, open **Phase 1: Literature Review** and [start a run](./workflow/pipeline). The pipeline will guide you through each phase sequentially — you decide when to proceed.

---

## Tips for a successful project

1. **Write a sharp brief.** This is the highest-leverage thing you can do. Spend 30 minutes on the goal and restrictions; it saves hours of misdirected research.

2. **Let Phase 1 (Literature) run first.** Even if you know the literature, the structured notes and reference library become context for every later phase. Approve Phase 1 before starting Phase 2.

3. **Use the "direction" field on each run.** When starting a phase, you can add free-text direction (e.g., "focus on graph-based methods", "compare against the ALDI baseline specifically"). This steers the agents without changing the brief.

4. **Review critically.** Read the HTML summary at each `awaiting_review`. The summary states conclusions, evidence, and risks. Don't rubber-stamp — if the evidence is weak, request a revision or rerun.

5. **Rerun when you have new context.** If Phase 1 finds new literature, or you realize the brief needs refinement, rerun. The rerun protocol audits and extends prior work — nothing is lost.

---

## Next steps

- [Pipeline Overview](./workflow/pipeline) — how the five phases connect
- [Phase 1: Literature Review](./workflow/phase-1) — start here
