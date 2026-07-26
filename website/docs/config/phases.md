---
sidebar_position: 2
title: "Phase Configuration"
---

# Phase Configuration

Each phase is defined in `config.yaml` with its pattern, participants, and run parameters.

## Parallel phase

```yaml
- slug: "02-method-development"
  name: "Method Development"
  description: "Brainstorm genuinely new ideas"
  pattern: parallel
  gated_by: ["01-literature-review"]
  folder: "ideas/"
  members: [theorist, research_lead, data_scientist]
  rounds: {min: 2, default: 2, max: 3}
```

| Field | Description |
|-------|-------------|
| `slug` | Unique phase identifier (used in URLs, paths) |
| `pattern` | `parallel`, `debate`, or `sequential` |
| `gated_by` | Recommended approved prerequisites |
| `folder` | Output directory within the project workspace |
| `members` | Participating role IDs |
| `rounds` | User-selectable round count range |

## Debate phase

```yaml
- slug: "03-idea-evaluation"
  name: "Idea Evaluation"
  pattern: debate
  gated_by: ["02-method-development"]
  folder: "evaluations/"
  members: [theorist, research_lead, data_scientist]
  rounds: {min: 2, default: 2, max: 3}
  method_binding: true
  proof_audit:
    plans: [standard, standard_with_audit, audit_only]
    stage:
      role: paper_reviewer
      name: "Audit the final theoretical analysis independently"
```

Debate phases have the same structure as parallel, but Round 2+ is structured as **challenge and revise** rather than cross-pollination.

## Sequential phase

```yaml
- slug: "05-review-revision"
  name: "Review & Revision"
  pattern: sequential
  gated_by: ["04-draft-assembly"]
  folder: "draft/revised/"
  members: [paper_reviewer, research_lead]
  rounds: {min: 2, default: 2, max: 2}
  stages:
  - role: paper_reviewer
    name: "Review"
    description: "Audit the complete draft and produce ranked revision recommendations."
  - role: research_lead
    name: "Revise"
    description: "Address each review point and produce the final manuscript."
```

Sequential phases execute stages **in order**, each owned by one role. For standard sequential phases, `rounds.min`, `rounds.default`, and `rounds.max` must all equal the number of stages.

## Optional feature declarations

| Feature | Declaration | Effect |
|---------|-------------|--------|
| **Theory plans** | `proof_audit:` on Phase 03 | Three user-selectable run plans: standard, standard+audit, audit-only |
| **Protocol checkpoint** | `protocol_checkpoint: true` on sequential | Seals a protocol document before any result-stage work |
| **Method binding** | `method_binding: true` | Freezes an exact method identity per run; routes output to branches |

## Prerequisite graph

- **`gated_by`** defines recommended approved prerequisites. Missing prerequisites trigger a warning requiring explicit override.
- **`context_from`** names additional approved phase summaries that are useful (but not required) when available.
- The current phase's prior approved result is automatically included on reruns for comparison.

## Configuration validation

Before use, configuration is validated for:
- Role and profile identifiers exist
- `research_lead` is present
- `paper_reviewer` uses an independent profile
- Output folders are project-relative and safe
- Round bounds are consistent
- Sequential stage owners are valid
- Prerequisite graph has no cycles
- Optional feature declarations are valid for their phase
- Required playbook files exist
