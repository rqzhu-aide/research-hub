---
sidebar_position: 9
title: "Configuration Reference"
slug: /reference/config
---

# Configuration Reference

Most users only need to choose a workspace and map the four research roles to Hermes profiles. The phase definitions are part of the shipped workflow and should be changed only when you are intentionally designing a different research process.

## Settings most users change

```yaml
hub:
  name: "My Research Hub"
  workspace_dir: "~/research"
  run_timeout_minutes: 240
  allow_unattended_tools: true
```

| Field | Meaning | Shipped value | If omitted |
|---|---|---:|---:|
| `name` | Name shown in the Web UI | `My Research Hub` | Required |
| `workspace_dir` | Location of the project registry and project files | `~/research` | Required |
| `run_timeout_minutes` | Maximum duration of one phase run | `240` | `120` |
| `allow_unattended_tools` | Allows a user-started background run to use its configured tools without further prompts | `true` | `false` |

`allow_unattended_tools: true` does not start work automatically. Every run still requires an explicit user launch.

## Map research roles to Hermes profiles

```yaml
agents:
- id: "research_lead"
  profile: "research_lead"
  name: "Research Lead"
  role: "scientific question, framing, synthesis"

- id: "theorist"
  profile: "theorist"
  name: "Theorist"
  role: "statistical theory, assumptions, proofs"

- id: "data_scientist"
  profile: "data_scientist"
  name: "Data Analyst"
  role: "implementation, numerical studies, data analysis"

- id: "paper_reviewer"
  profile: "paper_reviewer"
  name: "Paper Reviewer"
  role: "context-separated scientific assessment"
```

The fields have different purposes:

- `id` is the stable internal role identifier used by the phase definitions.
- `profile` is the Hermes profile assigned to that role.
- `name` and `role` are user-facing descriptions.

The profile name does not have to match the role identifier. The paper reviewer must use a profile that is not assigned to any author-side role.

Model, provider, tools, profile memory, and general profile skills remain in
Hermes. See [Set Up Hermes Profiles](../profile-setup) for the operational
procedure and [Agent Instructions, Memory, and Skills](../team-resources) for
the boundary between profile state and frozen Research Hub instructions.

## The shipped phases

| Phase | Interaction pattern | Participants | User-selectable plan |
|---|---|---|---|
| Literature Review | Parallel investigation and synthesis | Lead, theorist, data analyst | Round count |
| Method Development | Parallel proposal and synthesis | Lead, theorist, data analyst | Full catalog or one-method focus, plus round count |
| Theoretical Development | Ordered theory, computational audit, and synthesis | Theorist, data analyst, research lead | Current records only, or current records plus archived Phase 3 summaries |
| Implementation & Experiments | Ordered empirical work, theoretical audit, and synthesis | Data analyst, theorist, research lead | Preliminary or comprehensive scope |
| Paper Assembly & Review | Ordered handoffs | Lead and paper reviewer | Assembly or review-revision |

The corresponding phase entries in `config.yaml` define the allowed interaction structure. Free-text instructions can change the scientific focus of a run, but they do not add, skip, reorder, or automatically start phases.

## Phase fields

| Field | Meaning |
|---|---|
| `slug` | Stable phase identifier used in URLs and records |
| `name` | Full user-facing phase name |
| `short_name` | Short label shown in the project tabs |
| `description` | One-sentence purpose shown before launch |
| `pattern` | `parallel`, `debate`, or `sequential` |
| `gated_by` | Recommended upstream context checked before launch |
| `context_from` | Additional available same-branch context included when relevant |
| `folder` | Workspace location for the phase artifacts |
| `members` | Roles that may participate |
| `rounds` | Minimum, default, and maximum depth for parallel or debate work |
| `stages` | Fixed ordered handoffs for a sequential phase |
| `method_binding` | Keeps the run tied to one method branch |
| `run_modes` | Supported plans and the default plan for Phases 4 and 5 |

Do not rename a phase slug in an active project. Slugs are part of run records, paths, manifests, and migration logic.

## Interaction patterns

### Parallel

Participants begin from the same frozen context and develop complementary analyses. Later rounds allow comparison and synthesis.

### Debate

Participants first develop their positions independently. Later rounds directly examine assumptions, derivations, counterexamples, and unresolved disagreements.

### Sequential

Stages run in a fixed order. Each stage receives the preserved output of the preceding stage.

## Run modes

Phase 2 supports two catalog scopes:

- `full_catalog`, which may add, revise, merge, retain, or retire methods;
- `focused_method`, which may revise one selected active method while every
  nonselected catalog entry remains unchanged.

A focused run cannot create, rename, merge, retire, or remove methods. A new
project therefore begins with a full-catalog run.

Phase 3 supports two context policies:

- `current_only`, the default, which uses the current theory manuscript and the
  current same-branch empirical package when available;
- `include_archived_summaries`, which adds archived Phase 3 summaries to those
  current records.

The archived-summary option is disabled until the selected method has Phase 3
history. It adds compact summaries, not every artifact from every older run.

Phase 4 supports two run scopes:

- `preliminary`, for implementation, focused diagnostics, and limited experiments;
- `comprehensive`, for full benchmarking, uncertainty, robustness, and
  sensitivity analysis.

These are alternative scopes. Either can be launched directly after Phase 2 for
a selected active method. Both use the same three-stage sequence: data analyst,
theorist, then research lead.

Phase 5 supports:

- `assembly`, for combining intact, compatible evidence into a coherent manuscript;
- `review_revision`, for context-separated review followed by research-lead revision.

The configured Phase 5 `stages` block describes the base assembly plan. Research
Hub constructs the review-revision stages when that mode is selected. A verified
current `manuscript.md` is sufficient; no separate approval state is required.

## Three kinds of prerequisite

The interface uses three distinct forms of dependency:

1. **Recommended upstream context.** A `gated_by` entry can produce a warning
   when recommended evidence is missing or has changed. The user can proceed through
   an explicit recorded override when that dependency is advisory.
2. **Required method selection.** Phases 3 to 5 must be bound to an active
   Phase 2 method before they can run.
3. **Required complete upstream record for Phase 5.** Phase 5 requires an intact
   completed result from each of Phases 1 through 4. The Phase 3 and Phase 4
   results must both match the selected method's stable ID, version, and
   definition digest.

Phase 4 preliminary and comprehensive have no dependency on one another. A
required method selection, Phase 5 integrity check, or exact method match cannot
be replaced by a prerequisite override.

## Optional phase features

| Feature | Declaration | Effect |
|---|---|---|
| Protocol checkpoint | `protocol_checkpoint: true` | Preserves a protocol artifact before result-stage work |
| Method binding | `method_binding: true` | Freezes method identity and routes output to its branch |
| Run modes | `run_modes:` | Offers explicitly supported run plans in the launch form |

The shipped configuration enables method binding and run modes. Phase 4 also
enables the protocol checkpoint, which seals the analyst's protocol before the
main result work proceeds.

## When validation occurs

When the configuration is loaded, Research Hub checks:

- required role identifiers and safe profile-name syntax;
- presence of the research lead;
- separation of the reviewer profile from author-side profiles;
- safe project-relative output folders;
- valid round bounds and sequential stages;
- an acyclic prerequisite graph;
- supported optional features; and
- required phase playbooks.

The existence and readiness of the mapped Hermes profiles are checked again before a run launches. This separates configuration syntax from runtime availability.
