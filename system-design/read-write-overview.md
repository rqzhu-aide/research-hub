# Read/Write Rules — Overview

Cross-cutting conventions shared by all phase read/write files. The canonical folder layout is [file-system.md](./file-system.md).

## Output Types (Layer Mapping)

| Output Type | Layer | Typical Size | Behavior |
|-------------|-------|-------------|----------|
| **Full** | Layer 1 | Any | Raw output, code, data, PDFs. Organized in subfolders as needed. |
| **Summary** | Layer 2 | 2–16 KB | Structured `.md` with key mathematical/innovative details. Loaded when user clicks "view details" or by other roles in later phases. |
| **Highlight** | Layer 3 | 200–400 words | Abstract-length `.md`. Displayed in web UI; also used as per-reference tracing cards. |

## Cross-Phase Read Dependencies

```
references/ ─────────────────────────────────────────────┐
    │                                                     │
    ▼                                                     │
Phase-1 ────► Phase-2 ────► <method>/proofs/ ─────────┐  │
                          │                            │  │
                          │   ┌────────────────────────┘  │
                          │   │                           │
                          │   ▼                           │
                          ├──► <method>/numerical/ ───┐   │
                          │                            │   │
                          │   ┌────────────────────────┘   │
                          │   │                            │
                          │   ▼                            ▼
                          └──► <method>/draft/ ◄───────────┘
```

### Gating

- **Phase-1** must complete at least one run before **Phase-2** can start
- **Phase-2** must complete at least one run before **Phases 3 or 4** can start
- **Phase-3** and **Phase-4** run independently — either can run first
- **Phase-5** is gated: cannot run until both Phase 3 and Phase 4 have completed at least one run each

### Cross-phase reads

- **references/** is read by every phase and every role — it's the universal knowledge base
- **Phase-1** role-facing summaries feed into **Phase-2** (theorist reads theorist-focus, etc.) and **Phases 3–5**
- **Phase-2** creates `<stable_id>.md` which is required reading for Phases 3, 4, 5
- **Phases 3 and 4** each receive the other's Layer 3 highlight for brief awareness, and know the Layer 2 file locations for deep auditing when needed. Layer 2 files must be technically self-contained and precise — another role's agent should understand the work without reading Layer 1.

### Phase 3–4 cross-review and lead synthesis

Each Phase 3 or 4 run includes cross-review and lead synthesis as part of the run:

**Phase 3:** theorist writes proof → data_scientist reviews (`proofs/review.md`) → research_lead synthesizes (`proofs/lead-highlight.md`)

**Phase 4:** data_scientist writes implementation → theorist reviews (`numerical/review.md`) → research_lead synthesizes (`numerical/lead-highlight.md`)

The `lead-highlight.md` in each folder is the user-facing Layer 3 summary displayed in the web UI.

### Phase 5 workflow

**Run 1 — Initial Draft:** research_lead loads paper writing skill → scaffolds paper from Layer 2 summaries → writes complete draft from Layer 1 material

**Run N — Revision:** theorist audits paper vs. proofs (`draft/theorist-audit.md`) → data_scientist audits paper vs. implementation (`draft/analyst-audit.md`) → paper_reviewer loads reviewer skills and independently reviews paper only (`draft/reviewer-report.md`) → research_lead loads paper writing skill and revises paper from all audits

## Update Semantics

| File type | Update strategy | Examples |
|-----------|----------------|----------|
| **Live status** (Layer 2 status files) | Overwrite in place each run | `literature-summary.md`, `proof_status.md`, `numerical_status.md`, `draft_status.md` |
| **Live highlight** (Layer 3) | Overwrite in place each run | `proofs/highlight.md`, `numerical/highlight.md`, `draft/highlight.md`, `Phase-1/highlight.md`, `Phase-2/highlight.md` |
| **Run reports** | Append-only — new file per run | `run-001/lead-report.md`, `proofs/run-3.md` |
| **Working material** | Update in place; archive old versions | `proofs/material/`, `numerical/implementation/`, `draft/latex/` |
| **Reference pool** | Additive — new papers added, existing ones stable | `references/<paper_id>.pdf` |
| **Method registry** | Update in place (JSON, bump version only if material change) | `Phase-2/method-registry.json` |
| **Cross-review** | Overwrite in place each run | `proofs/review.md`, `numerical/review.md` |
| **Lead highlight** | Overwrite in place each run | `proofs/lead-highlight.md`, `numerical/lead-highlight.md` |
| **Phase 5 audits** | Overwrite in place each revision run | `draft/theorist-audit.md`, `draft/analyst-audit.md`, `draft/reviewer-report.md` |

## Folder Structure Additions

The [file-system.md](./file-system.md) folder tree is extended with these files to support the read/write rules:

| New file | Location | Layer | Purpose |
|----------|----------|-------|---------|
| `papers/<source>-<id>.md` | `references/` | 2 | Per-paper summary card (YAML frontmatter + structured body) |
| `reference-index.json` | `references/` | — | Machine-readable index generated from papers/ |
| `literature-summary.md` | `references/` | 2 | Consolidated synthesis of all references |
| `reference-delta/` | `references/` | — | Staging area for paper suggestions (JSON, one per agent) + downloaded PDFs |
| `<paper_id>_highlight.md` | `references/` | 3 | Per-paper innovation tracing card |
| `highlight.md` | `Phase-1/` | 3 | Research direction potential |
| `highlight.md` | `Phase-2/` | 3 | Method pool status for UI |
| `theorist-focus.md` | `Phase-1/run-<id>/` | 2 | Lit review focused for theorist |
| `data_scientist-focus.md` | `Phase-1/run-<id>/` | 2 | Lit review focused for data_scientist |
| `general-focus.md` | `Phase-1/run-<id>/` | 2 | Lit review for general audience |
| `general-focus.md` | `Phase-1/` | 2 | Copy of latest general-audience review — UI "more details" view |
| `theorist-report.md` | `Phase-2/run-<id>/` | 1 | Theorist's method proposals & reviews |
| `data_scientist-report.md` | `Phase-2/run-<id>/` | 1 | Data scientist's method proposals & reviews |
| `review.md` | `proofs/` | 3 | Data scientist's cross-review of proofs |
| `lead-highlight.md` | `proofs/` | 3 | Research lead's user-facing proof status synthesis |
| `review.md` | `numerical/` | 3 | Theorist's cross-review of numerical work |
| `lead-highlight.md` | `numerical/` | 3 | Research lead's user-facing numerical status synthesis |
| `theorist-audit.md` | `draft/` | 2 | Theorist's audit of paper vs. proofs |
| `analyst-audit.md` | `draft/` | 2 | Data scientist's audit of paper vs. implementation |
| `reviewer-report.md` | `draft/` | 2 | Paper reviewer's independent review of paper |
