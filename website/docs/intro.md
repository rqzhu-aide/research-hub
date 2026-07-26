---
sidebar_position: 1
title: "Introduction to Research Hub"
slug: /intro
---

# Introduction to Research Hub

Research Hub is a local Web UI for running **structured, multi-agent research workflows** with Hermes. It coordinates project files, phase playbooks, run history, and user review — turning the research process into a reproducible, auditable pipeline.

## The central rule

**Nothing advances automatically.** The user explicitly starts every phase run, reviews its evidence, and decides whether to approve it, request a revision, rerun it, or leave it unapproved. Any phase can be rerun when the user wants a different question, scope, or approach.

## The research pipeline

Research Hub organizes research into five sequential phases:

| Phase | Purpose |
|-------|---------|
| **1. Literature Review** | Survey relevant work, produce structured notes, identify gaps |
| **2. Method Development** | Brainstorm genuinely new ideas — mechanisms, frameworks, insights |
| **3. Idea Evaluation** | Prove theorems, establish rate bounds, assess computational feasibility |
| **4. Draft Assembly** | Write the paper — intro, theory, experiments, discussion |
| **5. Review & Revision** | Independent audit and final revision into a polished manuscript |

Each phase builds on the approved results of prior phases.

## The research team

Four specialized roles collaborate across phases:

| Role | Focus |
|------|-------|
| **Research Lead** | Domain expertise, framing, writing, coordination |
| **Theorist** | Methods, mathematics, rigor |
| **Data Scientist** | Computational approaches, algorithms, implementation |
| **Paper Reviewer** | Independent audit, quality control |

Each role is backed by a separate Hermes profile with its own durable identity (a "soul").

## What makes Research Hub different

1. **Sealed manifests.** Every run's exact inputs — playbooks, souls, prior summaries — are frozen and SHA-256 hashed. Runs are fully reproducible and tamper-evident.

2. **User-in-control workflow.** Agents produce evidence; the user makes every decision. Agents cannot approve their own results.

3. **Iterative refinement.** Reruns audit and extend prior work rather than replacing it. Method histories accumulate across runs with permanent numbering.

4. **Method branching.** When a method is selected for evaluation, its Phase 3/4/5 outputs are isolated in per-method branch directories, keeping each method's artifacts clean.

## Next steps

- [Installation](./install) — get Research Hub running
- [Quickstart](./quickstart) — your first research project
- [Research Workflow](./workflow/overview) — understand the 5-phase pipeline
