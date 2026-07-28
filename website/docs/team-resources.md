---
title: "Agent Instructions, Memory, and Skills"
slug: /team-resources
---

# Agent Instructions, Memory, and Skills

Research Hub does more than assign a task to a role. For each run, it combines
the role's standing scientific responsibilities, the protocol for the selected
phase, the user's direction, the relevant project evidence, and any applicable
Hermes skill.

These resources have different scopes. Some belong to the role, some belong to
the Hermes profile, and some are created specifically for one phase run.

## The five resource layers

| Layer | Scope | What it contributes | Preserved by Research Hub? |
|---|---|---|---|
| Hermes profile | One configured agent profile | Model, provider, tools, profile `SOUL.md`, persistent memory, and installed skills | Profile identity and applicable skill state are recorded; profile memory and profile `SOUL.md` are managed by Hermes |
| Team guidance | All scientific roles | Team charter and norms for evidence, uncertainty, disagreement, and reproducibility | Yes, copied and hashed for the run |
| Standing role instructions, called the role soul | One scientific role | Stable responsibilities and characteristic questions for the lead, theorist, analyst, or reviewer | Yes, copied, embedded in the task brief, and hashed |
| Phase playbook | One role in one phase | The scientific objective, role-specific work, handoff order, reporting requirements, and limits for that phase | Yes, copied and hashed |
| Run and stage brief | One authorized run or stage | User instructions, selected method, frozen evidence, earlier reports, exact output location, and completion contract | Yes, generated and sealed for that run |

The effective behavior of a team member changes by phase mainly because the
phase playbook, evidence, and stage brief change. The standing role soul remains
the same across phases unless a maintainer edits it.

## What varies by phase today

| Phase | Main role-specific preparation |
|---|---|
| Phase 1: Literature Review | Literature search, comparison, foundations, implementation availability, and synthesis instructions |
| Phase 2: Method Development | Independent method proposals, mathematical definitions, novelty checks, comparison, and catalog synthesis |
| Phase 3: Theoretical Development | Theorist-led derivation and proof work, analyst audit, then lead synthesis |
| Phase 4: Implementation and Experiments | Analyst-led protocol, implementation, and experiments, theorist audit, then lead synthesis |
| Phase 5: Paper Assembly and Review | Manuscript assembly or reviewer-led assessment and research-lead revision |

Phase 3 and Phase 4 also receive available prior results, role reports,
discussion, and supporting artifacts from both phases when they belong to the
same method branch. Later stages in the current run receive the reports already
produced by earlier stages.

## Standing role instructions and phase playbooks

Research Hub's own standing role instructions are in:

```text
config/souls/
```

Phase-specific instructions are in:

```text
config/phases/<phase>/
```

Each phase directory contains:

| File | Purpose |
|---|---|
| `_phase.md` | Scientific purpose and shared protocol for the phase |
| `_lead.md` | Orchestration and synthesis responsibilities for the research lead |
| `<role>.md` | Work and reporting requirements for a participating role |

At launch, Research Hub copies the applicable files into the run's protected
context and records their hashes. Editing the source files later does not change
the instructions already frozen for that run.

## Hermes profile memory

Each Hermes profile can retain its own persistent memory across sessions.
Research Hub displays the profile's `memories/MEMORY.md` on the **Agent
profiles** page when that file is available.

Profile memory is not phase-specific. The same mapped profile can carry memory
from one phase to another. It is also not copied into Research Hub's frozen run
context. Hermes owns and updates this state.

For that reason:

- use separate profiles for roles that require memory separation;
- always use a separate profile for the Paper Reviewer;
- record project-specific facts, assumptions, evidence, and decisions in the
  project brief or research artifacts rather than relying on profile memory;
- inspect profile memory when unexplained prior assumptions appear in an
  agent's work.

See [Set Up Hermes Profiles](./profile-setup) for profile creation, mapping, and
memory separation.

## Skills in the current release

Research Hub bundles pinned copies of two recommended Hermes skills:

| Role | Recommended skill |
|---|---|
| Research Lead, Theorist, Data Analyst | `stat-paper-writing` |
| Paper Reviewer | `stat-paper-reviewer` |

Installation is an explicit user action on the **Agent profiles** page.
Research Hub reports whether the bundled copy is missing, current, or different
from the installed copy. Replacing a different copy requires confirmation and
preserves the prior files as a backup.

Installing a skill and activating it for a run are different actions. The
current launch policy explicitly preloads:

- `stat-paper-writing` for author-side Phase 5 work;
- `stat-paper-reviewer` when the Paper Reviewer participates.

The bundled writing skill is not currently preloaded automatically in Phases 1
through 4. Other skills installed in a profile remain under Hermes control;
Research Hub does not currently select, version, or verify them by phase.

The exact applicable bundled-skill state is recorded when a run is prepared and
rechecked before Hermes starts. If that installed copy changes between
preparation and dispatch, Research Hub stops rather than silently using a
different skill.

## Library-specific reference and tool packs

Research Hub does not yet have a managed collection of phase-specific library
packs. This is an important extension point.

Examples include:

- a Phase 3 theorist pack for [Lean mathlib](https://mathlib.org/), theorem
  search, formalization conventions, and proof checking;
- a Phase 4 analyst pack for
  [OptimizationProblems.jl](https://jso.dev/OptimizationProblems.jl/stable/),
  benchmark selection, problem classifications, and evaluation conventions;
- packs for numerical optimization, probabilistic programming, biological
  databases, single-cell analysis, causal inference, or reproducible computing.

A reference pack gives the agent reliable guidance about a library. It does not
install the corresponding software. For example, a mathlib pack does not by
itself install Lean, and an OptimizationProblems.jl pack does not install Julia
or the package.

A future managed pack should record:

- the roles and phases for which it is relevant;
- the source and version of the reference material;
- the required runtime, packages, and environment checks;
- verified examples and known limitations;
- whether it should be loaded automatically or only when requested;
- a content digest so the exact revision can be recorded with a run.

Project-specific results should remain in project artifacts. General library
guidance belongs in a reusable pack. This separation avoids turning persistent
profile memory into an unreviewed mixture of software notes and scientific
claims.

## Safe customization

Most users should customize:

- profile models, providers, tools, and memory through Hermes;
- role-to-profile mappings and recommended skills through **Agent profiles**;
- project questions and run-specific direction through the Research Hub Web UI.

Maintainers can also revise the team guidance, role souls, and phase playbooks.
Make those changes only when no run is active, keep them under version control,
and test them with a disposable project. Research Hub's frozen records preserve
the prior instructions for runs that were already prepared.

For the exact configuration fields, see
[Configuration Reference](./reference/config). For the provenance boundary
between frozen Research Hub inputs and live Hermes profile state, see
[Architecture and Integrity](./reference/architecture).
