---
sidebar_position: 8
title: "Files and Research Records"
slug: /reference/files-and-records
---

# Files and Research Records

You can use Research Hub without managing its internal files directly. This page explains where your research materials live and which records should not be edited.

## The four kinds of project material

| Material | What it contains | Should you edit it? |
|---|---|---|
| Research brief | Your question, background, scope, and decision criteria | Yes, between runs |
| Research artifacts | Literature notes, method definitions, proofs, code, results, and manuscript drafts | Inspect freely; edit only when you intentionally take over from the agents |
| Phase summaries | The evidence summary associated with each completed run | No |
| Control records | Frozen inputs, prompts, manifests, hashes, run state, and logs | No |

The project workspace contains the research materials you read and use. A separate control directory contains the records Research Hub uses to preserve provenance and verify integrity.

## Main workspace locations

| Location | Purpose |
|---|---|
| `setting.md` | The research brief read by every phase |
| `references/` | Phase 1 literature records and synthesis |
| `ideas/` | Phase 2 candidate methods and method registry |
| `branches/<method>/evaluations/` | Phase 3 theory and feasibility work for one method |
| `branches/<method>/draft/sections/` | Phase 4 implementation and experimental evidence |
| `branches/<method>/draft/revised/` | Phase 5 manuscripts, reviews, and revision records |
| `phase-summaries/` | Human-readable summaries from individual runs |

Phases 3 to 5 use a separate branch directory for each method. Phase 3 and
Phase 4 are sibling workflows within that directory, so either can run first and
each can use available prior results and discussion from both phases on the same
branch. Phase 5 uses it only after Phases 1 through 4 have intact completed
results. The Phase 3 and Phase 4 results must both match the selected method's
stable ID, version, and definition digest. This layout prevents results for
different methods from being mixed.

## Immutable history and current synthesis

Research Hub preserves each reserved run as a separate history entry. Successfully prepared runs retain frozen prompts, manifests, and logs; submitted summaries are retained when produced.

Some current synthesis files, such as the consolidated literature summary or an active method definition, can be updated when you rerun a phase. The earlier run records remain available, so you can distinguish the current synthesis from the evidence that produced it.

## The control directory

The control directory contains:

- the run state for each project;
- frozen copies of all inputs used at launch, including selected same-branch
  summaries, role reports, supporting evidence, and Phase 4 protocol records;
- the exact prompt supplied to the lead agent;
- a sealed manifest describing the run;
- hashes used to detect later changes; and
- execution logs.

Do not edit, rename, or delete these files manually. Doing so can invalidate a run or prevent Research Hub from verifying its history.

## Back up a project

Make backups only when no run is active, and preferably after stopping the Web
UI. The safest approach is to back up the entire configured `workspace_dir`.
That preserves `hub.db`, the project folders under `projects/`, and the matching
control records under `projects/.research-hub-control/`.

If you copy one project separately, preserve its project folder and the control
folder with the same name together. A project folder alone is not a complete run history.

For the implementation details, see [Architecture and Integrity](./architecture).
