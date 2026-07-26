---
sidebar_position: 6
title: "Phase 5: Review & Revision"
slug: /workflow/phase-5
---

# Phase 5: Review & Revision

Independent audit of the complete draft by the paper reviewer, followed by final revision by the research lead.

## At a glance

| | |
|---|---|
| **Pattern** | Sequential (2 fixed stages) |
| **Participants** | Paper Reviewer → Research Lead |
| **Stages** | 2 (fixed) |
| **Output** | `draft/revised/` |
| **Prerequisites** | Phase 4 (Draft Assembly) |

## How it works

Unlike parallel and debate phases, Phase 5 runs in **strict sequence** — each stage completes before the next begins.

### Stage 1: Review (Paper Reviewer)

The paper reviewer — an **independent agent** with a separate Hermes profile — audits the complete draft across four dimensions:

| Dimension | What's checked |
|-----------|---------------|
| **Soundness** | Are the theorems correct? Are the proofs complete? Do the experiments actually support the claims? Are there hidden assumptions? |
| **Clarity** | Is the writing clear? Is the notation consistent? Can a reader follow the argument from start to finish? |
| **Significance** | Does the contribution matter to the field? Is it substantial enough to publish? |
| **Originality** | How does it compare to existing work? Is the differentiation clearly stated and accurate? |

The reviewer produces **ranked revision recommendations** — a prioritized list from critical errors that must be fixed, to polish items. Each recommendation includes specific page/section references.

### Stage 2: Revise (Research Lead)

The research lead addresses each review point:
- Fixes errors identified by the reviewer
- Strengthens weak claims with additional evidence or tighter arguments
- Improves clarity and consistency
- Produces the **final manuscript** with a **revision log** documenting what was changed and why

## Why independence matters

The paper reviewer **must use a separate Hermes profile** from the theorist, data scientist, and research lead. Research Hub validates this at startup.

This independence is essential:
- The reviewer **hasn't seen** the draft being written — they approach it fresh
- The reviewer's judgment isn't influenced by the authoring process
- The review is closer to what a real peer reviewer would provide

The reviewer uses the `stat-paper-reviewer` skill for consistent review standards.

## Per-role responsibilities

### Paper Reviewer (Stage 1 only)
- Read the **complete draft** as submitted in Phase 4
- Audit across the four dimensions above
- Produce **ranked, actionable** recommendations with specific references
- Do **not** revise the draft — that's the lead's job
- Do **not** decide whether to proceed — that's your decision

### Research Lead (Stage 2 only)
- Read the reviewer's recommendations
- Address **every point** — fix, strengthen, or explain why it doesn't apply
- Produce the **final manuscript**
- Write a **revision log** mapping each recommendation to the change made

## Output: folder structure

```
draft/
└── revised/
    └── run/
        └── 01/
            ├── .directives/
            ├── stage-01/                    ← Paper Reviewer's review
            │   └── paper_reviewer.md        ← ranked revision recommendations
            └── stage-02/                    ← Research Lead's revision
                ├── manuscript-final.md      ← the polished manuscript
                └── revision-log.md          ← what was changed and why
```

## Readiness assessment

The reviewer and lead jointly assess readiness. The recommendation is one of:

| Recommendation | Meaning |
|----------------|---------|
| **Proceed** | The manuscript is ready (may have minor polish items) |
| **Improve experiments** | Specific experiments or proofs need more work → rerun Phase 4 |
| **Return to Phase N** | A deeper gap exists (e.g., the theory is incomplete) → rerun Phase 3 |
| **Dead end** | The method doesn't work as claimed → return to Phase 2 |

**You make the final call** based on this assessment.

## Reruns

Phase 5 can be rerun if:
- The revision didn't adequately address the review points
- Phase 4 was rerun with a substantially different draft
- You want a fresh independent review of a revised manuscript

The rerun follows the same sequential structure: review first, then revise. Prior reviews and revisions stay sealed in their run directories.

## What the project produces

After Phase 5 is approved, you have:
- A **final manuscript** ready for submission
- A complete **revision log** for your records
- The full **provenance chain**: from literature review through method development, theorem proving, experimentation, drafting, and review
