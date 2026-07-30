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
| Research artifacts | Literature notes, method definitions, proofs, code, results, and manuscript drafts | Inspect freely. Copy a file elsewhere before manual editing; changing a current project record can invalidate its recorded identity. |
| Phase summaries | The evidence summary associated with each completed run | No |
| Control records | Frozen inputs, prompts, manifests, hashes, run state, and logs | No |

The project workspace contains the research materials you read and use. A separate control directory contains the records Research Hub uses to preserve provenance and verify integrity.

## Main workspace locations

| Location | Purpose |
|---|---|
| `setting.md` | The research brief read by every phase |
| `references/papers/`, `references/reference-index.json`, `references/literature-summary.md` | Current cumulative Phase 1 library, index, and synthesis |
| `ideas/methods/*.md`, `ideas/methods/_registry.yaml` | Current Phase 2 method definitions, permanent identities, and system-managed per-method provenance |
| `branches/<method>/evaluations/current/` | Current Phase 3 `theory-manuscript.md` and record |
| `branches/<method>/draft/sections/current/` | Current Phase 4 `empirical-synthesis.md` and `evidence-index.json` |
| `branches/<method>/draft/current/` | Current Phase 5 `manuscript.md` and record |
| `phase-summaries/` | Human-readable summaries from individual runs |

Phases 3 to 5 use a separate branch directory for each method. Phase 3 and
Phase 4 are sibling workflows, so either can run first. Each run records which
decision-relevant conclusions and evidence from the sibling phase were available
at launch. Phase 5 runs only after Phases 1 through 4 have usable current results
and the selected method's Phase 2 literature basis is current. The Phase 3 and
Phase 4 records must also be exactly aligned.

## Phase-specific current records

Each phase has a storage rule suited to its scientific output:

1. **Phase 1 is cumulative.** A run produces `reference-delta/papers/` and a
   complete `reference-delta/literature-summary.md` in its run folder. After
   validation, only new unique paper cards are added to the canonical library,
   the index is regenerated, and the current synthesis is replaced. The
   reference collection and literature synthesis have separate identities
   because either can change the basis of a manuscript.
2. **Phase 2 maintains one catalog with per-method provenance.** A full-catalog
   run may change the complete catalog and reviews every entry against the exact
   Phase 1 basis fixed at launch. A focused run may change and review only its
   selected active method. Validated output replaces the current published
   catalog atomically. For each method covered by a valid Complete or Partial
   run, Research Hub records the definition source, the latest review source,
   the method identity, the review outcome and scope, and the exact Phase 1
   reference collection and literature synthesis reviewed. A no-change review
   advances the review source and literature basis without changing the
   definition source. Nonselected methods in a focused run retain their earlier
   provenance. Each method file has one authoritative
   `## Mathematical definition` section. Research Hub computes
   `definition_sha256` from that section. A calculation-defining change requires
   a new method version; a status, literature, explanation, or formatting edit
   outside that section does not. Retaining a version requires leaving the
   authoritative section exactly unchanged.
3. **Phase 3 is a replacement workflow.** A valid Complete run publishes one
   self-contained current `theory-manuscript.md`. The next run uses that current
   manuscript by default. Archived Phase 3 summaries are included only when you
   select that context option. The manuscript is bound to the exact
   `stable_id`, version, and definition digest. Theory for an earlier version is
   historical until a rerun verifies its arguments under the new definition.
4. **Phase 4 is cumulative.** Code and results remain in their immutable run
   locations. The current `evidence-index.json` keeps every evidence identity and
   marks each entry as current, outdated, superseded, withdrawn, or unresolved.
   The current `empirical-synthesis.md` states what the method presently supports.
   A calculation-defining version change makes earlier code and scientific
   outputs outdated. Raw source data and generic infrastructure remain reusable
   only when their mathematical independence is recorded explicitly. A later
   recomputation or revalidation appends a new current evidence ID and leaves
   the old entry non-current for provenance.
5. **Phase 5 maintains one current manuscript.** A valid Assembly or Review &
   Revision run replaces the branch's current `manuscript.md`. Earlier run
   records remain available for provenance, but are not working drafts. Its
   record identifies both the Phase 1 reference collection and literature
   synthesis used to produce the manuscript. A new Phase 5 run also requires the
   selected method's Phase 2 literature basis to match the current Phase 1
   record.

Do not directly edit a current artifact in place. Copy it elsewhere if you want
to make an independent version, or use a rerun to update the recorded result.

Do not edit `ideas/methods/_registry.yaml` manually. Research Hub writes its
per-method provenance from the sealed Phase 2 run after validating the staged
catalog. The research lead maintains only the scientific and historical fields
described in the Phase 2 instructions.

## Read status fields separately

The branch view presents related but distinct information:

- **Method and basis alignment** states whether a record refers to the exact
  current method and recorded sibling input.
- **Research attention** identifies outdated or unresolved Phase 4 evidence.
- **Scientific outcome** reports whether the authorized run was Complete,
  Partial, or Failed.

These fields answer different questions. Current alignment does not establish
that a theorem or empirical claim is strong. A Complete run can contain
negative findings or evidence that still requires attention. A Partial run can
contain valid current results.

## Sealed run records

Research Hub preserves every reserved run as a separate provenance entry.
Successfully prepared runs retain their frozen inputs, prompts, manifests, logs,
stage reports, and submitted summaries. These records explain how a current
scientific record was produced; they are not all loaded into every later run.

## What grows over time

Storage grows because Research Hub preserves provenance as well as current
scientific records:

- Phase 1 adds unique source cards to the cumulative literature library.
- Phase 4 preserves run-local code, data, results, and evidence records.
- Every run preserves its frozen inputs, prompt, reports, summary, and log.
- Phase 2, Phase 3, and Phase 5 replace their current working records, but their
  earlier sealed run records remain.

Research Hub does not currently provide supported automatic pruning. Monitor
available disk space, especially for Phase 4 projects. Back up the complete
project and control directory before storage maintenance, and do not delete
individual control files or run files manually.

## The control directory

The control directory contains:

- the run state for each project;
- frozen copies or hashes of the exact current records used at launch, plus any
  archived summaries explicitly selected for Phase 3;
- the rebuildable branch alignment graph derived from current records;
- current-run role reports, supporting evidence, and Phase 4 protocol records;
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
