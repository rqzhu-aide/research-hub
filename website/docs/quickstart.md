---
sidebar_position: 3
title: "Quickstart"
slug: /quickstart
---

# Quickstart

This guide walks through your first research project from setup to a completed phase.

## Step 1: Create a project

1. Open [http://127.0.0.1:5055](http://127.0.0.1:5055)
2. Click **New Project**
3. Give it a name and write a focused **research brief** (`setting.md`). The brief should state:
   - The research question in one sentence
   - Why it matters
   - What gap in existing work it addresses

## Step 2: Open a phase

Each project shows five phase tabs. Open **Phase 1: Literature Review**. The phase page shows:
- **Purpose** — what this phase does
- **Prerequisites** — what approved results are recommended
- **Participants** — which roles will work
- **Round plan** — the structure of rounds

## Step 3: Configure and start the run

1. Choose the **round count** (e.g., 2 rounds)
2. Add optional **direction** for the agents (e.g., "focus on graph-based sampling methods")
3. Review the prerequisite status. If something is missing, acknowledge the warning and override if you want to proceed
4. Click **Start**

## Step 4: Monitor the run

The run progresses through these states:

```text
starting → running → submitting → awaiting_review
                                      │
                                      ├── approve → trusted result
                                      ├── request revision → rerun later
                                      └── rerun → replace with new run
```

While running, you can:
- Watch round-by-round progress
- Read the live log
- Cancel the run if needed

## Step 5: Review the result

When the run reaches **awaiting_review**:
1. Read the **HTML summary** — it states the conclusions, evidence, risks, and recommendation
2. The summary is written for *you* to make a decision, not as the final artifact

You have three choices:
- **Approve** — the result becomes trusted context for downstream phases
- **Request revision** — leave a note; rerun later with the feedback
- **Rerun** — start a new run (prior result is preserved)

## Step 6: Proceed to the next phase

Once Phase 1 is approved, open Phase 2. Its prerequisite (Phase 1) is now satisfied. Repeat the cycle.

:::note
- Only **one run** can be active per project at a time
- Separate projects run independently
- Completing a phase never auto-starts the next one — you decide
:::

## Key concepts to remember

- **Agents produce evidence; you make decisions.** Agents cannot approve their own work.
- **Prior runs are sealed history.** Reruns audit and extend, never replace.
- **Approved results are trusted context.** Downstream phases build on approved summaries.
- **Everything is hash-verified.** You can always verify what a run consumed.
