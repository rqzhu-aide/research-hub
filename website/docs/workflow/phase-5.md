---
sidebar_position: 6
title: "Phase 5: Paper Assembly & Review"
slug: /workflow/phase-5
---

# Phase 5: Paper Assembly & Review

Transform the separate Phase 1–4 artifacts into a final manuscript through two run modes: **assembly** (combine everything into one paper) then **review and revision** (independent audit + revision).

## At a glance

| | |
|---|---|
| **Pattern** | Sequential |
| **Run modes** | Assembly (default), Review & Revision |
| **Participants** | Research Lead, Paper Reviewer |
| **Output** | `branches/<method>/draft/revised/` |
| **Method-bound** | Yes |
| **Prerequisites** | Phase 4 (Implementation & Experiments) |

## Run modes

Phase 5 has two run modes, selected at launch:

### Assembly — combine everything (default)

The research lead combines the Phase 1–4 artifacts into one coherent manuscript. This is the convergence point — the first time the entire research thread lives as a single document.

The lead assembles five sections from upstream phases:

| Section | Source |
|---------|--------|
| **Introduction** | Written fresh: motivate the problem, state the contribution, position against Phase 1 literature |
| **Method** | Phase 2 method definition (the precise definition of what was proposed) |
| **Theory** | Phase 3 proved theorems with full proofs |
| **Experiments** | Phase 4 implementation, diagnostics, and benchmark results (tables, figures) |
| **Discussion** | Synthesize open questions and connections to broader literature |

**Assembly requirements:**
- **Notation reconciliation**: the same symbols must mean the same thing across method, theory, and experiments
- **Claim consistency**: the intro's claims must match what the theory proves and what the experiments show. If the intro overclaims, narrow it
- **Honest reporting**: do not soften the theorist's proofs or the analyst's negative results
- **Unified bibliography**: merge all section references into one

- **1 round** — research lead assembles the manuscript
- Uses the `stat-paper-writing` skill

### Review & Revision — audit then revise (gated)

The paper reviewer audits the assembled manuscript, then the research lead revises it. Requires a prior approved **assembly** run for the same method branch — the assembled manuscript is the input to the review.

Can be run **iteratively** on the same assembly — multiple review passes without re-assembling.

**Stage 1 — Review (Paper Reviewer):**
The reviewer reads the assembled manuscript independently and audits it across four dimensions:

| Dimension | What's checked |
|-----------|---------------|
| **Soundness** | Are the theorems correct? Are the proofs complete? Do the experiments actually support the claims? Are there hidden assumptions? |
| **Clarity** | Is the writing clear? Is the notation consistent? Can a reader follow the argument from start to finish? |
| **Significance** | Does the contribution matter to the field? Is it substantial enough to publish? |
| **Originality** | How does it compare to existing work? Is the differentiation clearly stated and accurate? |

The reviewer produces **ranked revision recommendations** — a prioritized list from critical errors that must be fixed, to polish items.

**Stage 2 — Revise (Research Lead):**
The lead addresses each review point:
- **Fix** errors identified by the reviewer
- **Strengthen** weak claims with additional evidence or tighter arguments
- **Defer** (with reasoning) points that don't need immediate attention
- **Push back** (with reasoning) on recommendations the lead disagrees with
- Produce the **final manuscript** with a mandatory **revision log**

- **2 rounds** — review then revise
- Reviewer uses the `stat-paper-reviewer` skill; lead uses `stat-paper-writing` during revision

## Gate: review-revision requires assembly

The **review & revision** mode requires a prior approved **assembly** run for the same method branch. The assembled manuscript is the input to the review — you can't review a paper that hasn't been assembled yet.

If you try to launch review-revision without a prior approved assembly, the UI will block it with an explanation.

## Why independence matters

The paper reviewer **must use a separate Hermes profile** from the theorist, data analyst, and research lead. Research Hub validates this at startup.

This independence is essential:
- The reviewer **hasn't seen** the draft being written — they approach it fresh
- The reviewer's judgment isn't influenced by the authoring process
- The review is closer to what a real peer reviewer would provide

## Output: folder structure

```
branches/
└── <method-stable-id>/
    └── draft/
        └── revised/
            └── run/
                └── 01/
                    ├── .directives/
                    ├── round-01/                      ← Assembly mode
                    │   └── research_lead.md           ← assembled manuscript
                    └── (review-revision mode writes to a separate run)
                        ├── round-01/
                        │   └── paper_reviewer.md      ← structured review
                        └── round-02/
                            └── research_lead.md       ← revised manuscript + revision log
```

## Readiness assessment

After each run, the lead presents a readiness assessment with a clear recommendation:

| Recommendation | Meaning |
|----------------|---------|
| **Approve** | The manuscript is ready for submission |
| **Revise further** | Run another review-revision cycle with specific focus areas |
| **Return to Phase N** | The theory, experiments, or literature needs more work |
| **Dead end** | The method cannot be supported; select a different one |

**You make the final call** based on this assessment.

## Reruns

### Assembly rerun

The prior assembly is **comparison evidence**. Improve on it — incorporate new Phase 3/4 results, fix notation inconsistencies, deepen thin sections.

### Review-revision rerun

The prior review and revision are comparison evidence. Conduct an independent re-review and produce a fresh revision that addresses any remaining weaknesses.

Prior run directories always stay sealed — nothing is ever overwritten.

## What the project produces

After Phase 5 review-revision is approved, you have:
- A **final manuscript** ready for submission
- A complete **revision log** documenting every change
- The full **provenance chain**: from literature review through method development, theorem proving, experimentation, assembly, and review
