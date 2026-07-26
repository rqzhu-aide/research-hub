---
sidebar_position: 5
title: "Paper Reviewer"
---

# Paper Reviewer

## Scientific focus

**Independent audit and quality control.** The Paper Reviewer is the project's internal reviewer — an independent agent who audits the complete draft for soundness, clarity, significance, and originality.

## When the reviewer participates

The Paper Reviewer participates **only in Phase 5 (Review & Revision)**. They do not contribute to Phases 1–4. This separation ensures the review is genuinely independent.

## Responsibilities

### Phase 5, Stage 1: Review
The Paper Reviewer audits the complete draft across four dimensions:

- **Soundness**: Are the theorems correct? Are the proofs complete? Do the experiments actually support the claims? Are there hidden assumptions?
- **Clarity**: Is the writing clear? Is the notation consistent? Can a reader follow the argument from start to finish?
- **Significance**: Does the contribution matter to the field? Is it substantial enough to publish?
- **Originality**: How does it compare to existing work? Is the differentiation from prior work clearly stated and accurate?

The reviewer produces **ranked revision recommendations** — a prioritized list from critical errors that must be fixed to polish items.

## Independence requirement

The Paper Reviewer **must use a separate Hermes profile** from the Research Lead, Theorist, and Data Scientist. Research Hub validates this at startup and refuses to run if the reviewer profile overlaps with an authoring role.

This independence is essential:
- The reviewer hasn't "seen" the draft being written
- The reviewer's judgment isn't influenced by the authoring process
- The review is closer to what a real peer reviewer would provide

## The stat-paper-reviewer skill

The Paper Reviewer uses the `stat-paper-reviewer` skill, which provides:
- Consistent review standards across projects
- A structured review framework
- An optional OpenAlex search helper for checking related work

## What the reviewer does NOT do

- The reviewer does **not** revise the draft — that's the Research Lead's job in Stage 2
- The reviewer does **not** decide whether to proceed — that's the user's decision
- The reviewer does **not** participate in earlier phases — they see only the final draft

The reviewer's output is **recommendations**. The Research Lead addresses them; the user decides if the result is good enough.
