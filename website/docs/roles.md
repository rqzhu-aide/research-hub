---
sidebar_position: 7
title: "Roles & Team"
slug: /roles
---

# Roles & Team

Research Hub uses **four specialized roles**, each backed by a separate Hermes profile with a durable identity (a "soul"). Roles collaborate in structured rounds within each phase.

## The four roles

| Role | Focus | Participates in | Skill |
|------|-------|-----------------|-------|
| **Research Lead** | Domain expertise, framing, writing, coordination | Phases 1–5 | `stat-paper-writing` |
| **Theorist** | Methods, mathematics, rigor | Phases 1–4 | `stat-paper-writing` |
| **Data Scientist** | Computational approaches, algorithms, implementation | Phases 1–4 | `stat-paper-writing` |
| **Paper Reviewer** | Independent audit, quality control | Phase 5 only | `stat-paper-reviewer` |

## Responsibilities by phase

| | Phase 1 | Phase 2 | Phase 3 | Phase 4 | Phase 5 |
|---|---|---|---|---|---|
|| **Research Lead** | Position contribution, find closest prior work | Propose new contributions; coordinate method menu; select recommended method | Identify contribution structure, position against literature, structure paper narrative | Implement code, run experiments, synthesize results | Address review points, produce final manuscript |
|| **Theorist** | Find theoretical foundations, prior math frameworks | Propose new mathematical mechanisms (2–3+ ideas) | Derive and prove theorems, establish rate bounds, full proofs | Validate experiments against theoretical bounds; audit numerical results | — |
|| **Data Scientist** | Find existing implementations, benchmarks | Propose computational structures, algorithms, infrastructure | Assess computational feasibility, numerical stability, experiment design | Implement code, run experiments, produce real data | — |
| **Paper Reviewer** | — | — | — | — | Audit draft for soundness, clarity, significance, originality |

## How roles interact

### Within a round
In Round 1 of any phase, roles work **independently** — no cross-reading. Each produces their own output without seeing the others'.

### Across rounds
In Round 2+, roles read each other's prior-round outputs:
- **Parallel phases** (1, 2, 4): cross-pollination — roles refine ideas based on what others found
- **Debate phases** (3): challenge and revise — roles directly critique each other's claims, concede or hold with reasoning
- **Sequential phases** (5): stages run one at a time; the reviewer's output becomes the lead's input

### The lead as coordinator
The Research Lead has a dual role:
1. **Domain contributor** — writes sections, positions the contribution, structures the narrative
2. **Phase coordinator** — reads all prior context, dispatches round tasks to other roles, synthesizes the HTML summary

The summary is written for **your decision** — it states conclusions, evidence, risks, and a recommendation. The lead does not make the final decision; you do.

## Souls: durable identity

Each role has a **soul** — a personality file at `config/souls/<role>.md` that defines:

- **Scientific role**: the member's core identity and focus
- **Questions to ask**: diagnostic questions that guide their thinking
- **Working principles**: how they approach problems
- **Scope**: what's in and out of their lane

The soul is **durable** — it doesn't change between phases. The phase-specific playbook adds task instructions on top of the soul.

At launch time, the soul is frozen, hashed, and embedded directly into the sealed prompt. This ensures every run uses the exact same role identity and is fully reproducible.

### Editing souls

Because souls are frozen at launch, editing a soul after a run starts doesn't affect that run. The next run picks up the new version. Prior approved runs remain valid (they used the soul version current at their launch).

## Independence requirement

The **Paper Reviewer** must use an independent Hermes profile, separate from the three authoring roles. Research Hub validates this at startup and refuses to run if they overlap.

This ensures the Phase 5 review is genuinely independent — the reviewer hasn't been influenced by authoring the draft, and their judgment is closer to what a real peer reviewer would provide.

## Recommended skills

| Role | Skill | Purpose |
|------|-------|---------|
| Research Lead, Theorist, Data Scientist | `stat-paper-writing` | Paper writing conventions, proof formatting, experiment standards |
| Paper Reviewer | `stat-paper-reviewer` | Structured review framework, consistency across projects |

Skills are **recommendations, not prerequisites**. A phase runs even if a skill is absent. The web UI's **Profiles** page shows skill status and lets you install them.

The reviewer bundle also includes an optional OpenAlex search helper for checking related work during review.
