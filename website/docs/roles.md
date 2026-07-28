---
sidebar_position: 7
title: "Roles and Team"
slug: /roles
---

# Roles and Team

Research Hub assigns four scientific perspectives to separate Hermes profiles.

## The four roles

| Role | Primary scientific responsibility | Participates in |
|---|---|---|
| **Research Lead** | Defines the scientific argument, evaluates importance and positioning, integrates evidence, and states what can be concluded | Phases 1 to 5 |
| **Theorist** | Examines definitions, assumptions, identifiability, mathematical structure, guarantees, counterexamples, and proofs | Phases 1 to 4 |
| **Data Analyst** | Examines study design, algorithms, implementation, numerical stability, diagnostics, uncertainty, and reproducibility | Phases 1 to 4 |
| **Paper Reviewer** | Reads the assembled work critically, tests claims against evidence, and identifies revisions needed before submission | Phase 5 review and revision |

## Research Lead

The research lead keeps the work centered on a coherent scientific question. The lead:

- connects the proposed contribution to the literature;
- distinguishes central claims from supporting results;
- integrates theoretical and empirical evidence;
- identifies limitations and unresolved questions;
- prepares the phase summary used for your decision.

The lead may recommend a direction, but does not make the user's decision or start the next phase.

## Theorist

The theorist determines what follows from the stated assumptions. Depending on the project, this includes:

- defining mathematical objects and claims precisely;
- checking identifiability and regularity conditions;
- deriving guarantees, rates, or counterexamples;
- writing and checking proofs;
- distinguishing a theorem from a conjecture or heuristic;
- checking whether an implementation represents the proposed method.

The theorist should narrow a claim when the available assumptions do not support it.

## Data Analyst

The data analyst determines whether the computational and empirical evidence is credible. This includes:

- translating the method into an implementable algorithm;
- specifying simulation or empirical study designs;
- selecting appropriate baselines and evaluation measures;
- checking data leakage, numerical stability, and failure cases;
- reporting uncertainty, sensitivity analyses, and diagnostics;
- preserving code, settings, seeds, and outputs needed for reproducibility.

The data analyst also checks whether theoretical assumptions correspond to the implemented procedure and observed data.

## Paper Reviewer

The paper reviewer evaluates the assembled manuscript as a critical scientific reader. The review addresses:

- whether claims are supported by proofs, analyses, and experiments;
- whether comparisons are fair and relevant;
- whether assumptions and limitations are stated;
- whether the contribution is original and scientifically important;
- whether the manuscript is clear enough for expert assessment and reproduction.

The reviewer ranks weaknesses and recommends specific corrections. In a Review & Revision run, the research lead then records how each point was addressed, deferred, or disputed.

## How the roles work together

Phases 1 and 2 use rounds that first preserve distinct perspectives and then allow comparison and criticism.

Phase 3 and Phase 4 use ordered, cumulative discussion:

- **Phase 3:** Theorist, then Data Analyst, then Research Lead. The theorist performs the main mathematical work. The analyst reads and stress-tests it. The lead reads both reports and prepares the summary.
- **Phase 4:** Data Analyst, then Theorist, then Research Lead. The analyst performs the main implementation and empirical work. The theorist reads and audits it. The lead reads both reports and prepares the summary.

For both sibling phases, every role receives the frozen method and available prior results and discussion from Phase 3 and Phase 4 on the same method branch. Each later stage also receives the reports already produced in the current run. The lead records unresolved disagreements so a later rerun can return to them explicitly.

Phase 5 depends on the selected run mode. Assembly uses the Research Lead only.
Review & Revision uses the Paper Reviewer and then the Research Lead. A Review
target uses the Paper Reviewer only. Further review is appropriate when
important concerns remain. The current release has a legacy gate on Review &
Revision, described in [Known Limitations](./known-limitations).

## Standing role guidance

Each Research Hub role has standing guidance that defines its scientific
responsibilities and characteristic questions. Each phase adds instructions
specific to the task at hand.

Changes to Research Hub guidance apply to future runs. A prepared run retains
the exact Research Hub guidance recorded at launch. Hermes profile `SOUL.md`
and memory remain external profile state and are not frozen by Research Hub.
See [Files and Records](./reference/files-and-records) for provenance details.

The effective instruction package also includes Hermes profile state,
team guidance, a phase playbook, a run-specific brief, and applicable skills.
See [Agent Instructions, Memory, and Skills](./team-resources).

## Reviewer separation and its limits

The paper reviewer must use a Hermes profile that is not assigned to any authoring role. It does not share the research lead's, theorist's, or data analyst's conversational memory. The review stage receives the manuscript and the project evidence needed to check its claims.

This is a context-separated internal AI review. It is not independent human peer review, and it does not replace review by domain experts, statisticians, collaborators, ethics committees, or a journal.

## Recommended skills

| Role | Recommended skill | Contribution |
|---|---|---|
| Research Lead, Theorist, Data Analyst | `stat-paper-writing` | Statistical writing, mathematical exposition, empirical reporting, and claim control |
| Paper Reviewer | `stat-paper-reviewer` | Structured assessment of soundness, clarity, significance, and originality |

The skills are optional. Installation and replacement are explicit user
actions. Phase-specific activation follows the launch policy described in
[Agent Instructions, Memory, and Skills](./team-resources).

## Your role

Before each run, you choose its scope and settings. Afterward, you judge whether:

- the evidence supports the stated conclusion;
- important uncertainty and limitations are visible;
- a focused rerun can correct the current result;
- a fresh run is needed with different direction or inputs;
- the project should proceed, return to an earlier phase, or stop.

No team member makes these decisions on your behalf.
