---
sidebar_position: 6
title: "Phase 5: Review & Revision"
---

# Phase 5: Review & Revision

## Purpose

Independent audit of the complete draft, followed by revision into a polished final manuscript.

## At a glance

| | |
|---|---|
| **Pattern** | Sequential (2 fixed stages) |
| **Participants** | Paper Reviewer → Research Lead |
| **Stages** | 2 (fixed) |
| **Output** | `draft/revised/` |

## Stage structure

### Stage 1: Review (Paper Reviewer)
The paper reviewer — an **independent** agent separate from the authoring roles — audits the complete draft:

- **Soundness**: are the theorems correct? Are the proofs complete? Do the experiments support the claims?
- **Clarity**: is the writing clear? Is the notation consistent? Can a reader follow the argument?
- **Significance**: does the contribution matter? Is it novel enough?
- **Originality**: how does it compare to existing work? Is the differentiation clear?

The reviewer produces **ranked revision recommendations** — a prioritized list of what to fix, from critical errors to polish.

### Stage 2: Revise (Research Lead)
The research lead addresses each review point:
- Fixes errors identified by the reviewer
- Strengthens weak claims
- Improves clarity
- Produces the **final manuscript** with a **revision log** documenting what was changed and why

## Why independence matters

The paper reviewer **must use a separate Hermes profile** from the theorist, data scientist, and research lead. Research Hub validates this at startup. This ensures the review is genuinely independent — the reviewer hasn't been "poisoned" by authoring the draft.

The reviewer uses the `stat-paper-reviewer` skill for consistent review standards.

## Output

```
draft/revised/
├── manuscript-final.md       ← the polished manuscript
├── revision-log.md           ← what was changed and why
└── review-recommendations.md ← the reviewer's ranked recommendations
```

## Readiness assessment

The reviewer and lead jointly assess readiness:
- **Proceed**: the manuscript is ready (may have minor polish items)
- **Improve**: specific experiments or proofs need more work — recommend rerunning Phase 4
- **Return to Phase N**: a deeper gap exists (e.g., the theory is incomplete) — recommend rerunning Phase 3
- **Dead end**: the method doesn't work as claimed — recommend returning to Phase 2

The user makes the final call based on this assessment.
