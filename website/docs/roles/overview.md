---
sidebar_position: 1
title: "Research Roles Overview"
---

# Research Roles Overview

Research Hub uses four specialized roles, each backed by a separate Hermes profile with a durable identity.

## The four roles

| Role | Focus | Participates in |
|------|-------|-----------------|
| **Research Lead** | Domain expertise, framing, writing, coordination | Phases 1–5 |
| **Theorist** | Methods, mathematics, rigor | Phases 1–4 |
| **Data Scientist** | Computational approaches, algorithms, implementation | Phases 1–4 |
| **Paper Reviewer** | Independent audit, quality control | Phase 5 only |

## How roles interact

Roles work **in parallel within rounds** and **cross-pollinate across rounds**:

- **Round 1**: each role works independently — no cross-reading
- **Round 2+**: roles read each other's prior outputs, critique, refine, and propose new ideas sparked by other perspectives

In **debate phases** (Phase 3), cross-round interaction is structured as challenge-and-revise: roles explicitly critique each other's claims, concede when persuaded, or hold with reasoning.

The **Research Lead** has a special role: in addition to their domain contribution, they **coordinate** the phase — reading all prior context, dispatching round tasks, and synthesizing the final summary.

## Souls: durable identity

Each role has a **soul** — a personality file at `config/souls/<role>.md` that defines:

- **Scientific role**: the member's core identity
- **Questions to ask**: diagnostic questions that guide their thinking
- **Working principles**: how they approach problems
- **Scope**: what's in and out of their lane

The soul is **durable** — it doesn't change between phases. The phase-specific playbook adds task instructions on top of the soul. Together they define what a role does in a specific phase.

At launch time, the soul is frozen, hashed, and embedded directly into the sealed prompt. This ensures every run uses the exact same role identity.

## Independence requirement

The **Paper Reviewer** must use an independent Hermes profile, separate from the three authoring roles. Research Hub validates this at startup. This ensures the Phase 5 review is genuinely independent — the reviewer has not been influenced by authoring the draft.

## Per-role pages

- [Research Lead](./research-lead) — coordination, framing, writing
- [Theorist](./theorist) — mathematics, proofs, rigor
- [Data Scientist](./data-scientist) — computation, experiments, implementation
- [Paper Reviewer](./paper-reviewer) — independent audit
