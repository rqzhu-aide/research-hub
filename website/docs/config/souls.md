---
sidebar_position: 3
title: "Souls: Role Identity"
---

# Souls: Role Identity

Each research role has a **soul** — a durable identity file that defines who they are, how they think, and what their boundaries are.

## Location

```
config/souls/
├── research_lead.md
├── theorist.md
├── data_scientist.md
└── paper_reviewer.md
```

## What a soul contains

A soul defines:

1. **Scientific role** — the member's core identity and focus
2. **Questions to ask** — the diagnostic questions that guide their thinking
3. **Working principles** — how they approach problems
4. **Scope** — what's in and out of their lane
5. **Reporting** — what they're expected to produce

## How souls are used

At launch time, Research Hub:

1. Reads the relevant soul file
2. Computes its SHA-256 hash
3. Embeds the full soul text directly into the sealed lead prompt or member task brief
4. Places the phase-specific playbook **after** the soul

The soul is the **durable** identity — it doesn't change between phases. The playbook is the **phase-specific** instructions. Together they define what a role does in a specific phase.

## Why souls matter

Souls ensure consistency. A theorist in Phase 2 (brainstorming) and a theorist in Phase 3 (proving) are the **same agent** with the same values and reasoning habits — they just have different phase-specific tasks. Without souls, each phase's role instructions would need to redundantly define who the role is.

Souls also make the research process trustworthy. A soul that says "prefer a precise, limited contribution to an ambitious claim with weak support" shapes how the agent reasons about evidence across every phase — not just where that principle happens to be repeated in the playbook.

## Editing souls

Because souls are frozen and hashed at launch time, editing a soul after a run has started does not affect that run. The next run will pick up the new version. This is by design — a run's exact inputs must be reproducible.

If you edit a soul, prior approved runs remain valid (they used the soul version that was current at their launch). Only new runs use the updated soul.
