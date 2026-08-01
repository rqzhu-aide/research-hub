# Research Hub — File System Design

## Overview

The Research Hub file system is organized into three conceptual layers, from raw artifacts up to concise UI-facing highlights. The folder structure follows a project → phase → method hierarchy, where each method branch independently through proofs, numerical validation, and drafting.

---

## Three-Layer Architecture

| Layer | Content | Typical Size | Purpose |
|-------|---------|-------------|---------|
| **Layer 1** | Raw outputs, artifacts, original sources, code, data | Any | Ground truth — everything else derives from these |
| **Layer 2** | Structured summary files | 2–16 KB | The "working knowledge" layer — technically self-contained, detailed enough for another role to audit without reading Layer 1. Also what the agent reads to resume work across runs. |
| **Layer 3** | Abstract-level highlights | 200–400 words | UI-facing display and high-level status snapshots |

### Layer 2 — Summary File Types

Each summary file (~2–16 KB) falls into one of these categories:

| Type | Description | Example |
|------|-------------|---------|
| **Paper summary** | Distillation of a single paper: innovation, method, performance | `references/<paper>.md` |
| **Literature review** | Synthesis of all papers in the pool, current state of the field | `references/literature-summary.md` |
| **Method description** | Mathematical framework, innovative points, computational advantages of a proposed method | `<stable_id>.md` (per-method root) |
| **Proof summary** | Key assumptions, proof framework, key results, open items | `proofs/proof_status.md` |
| **Implementation outline** | Optimization strategy, computational framework, current status | `numerical/numerical_status.md` |
| **Draft status** | Current state of the paper draft | `draft/draft_status.md` |

**Layer 2 writing requirements:** Every Layer 2 summary must be:

- **Technically self-contained** — another role's agent can understand the work without reading Layer 1 raw material
- **Precise** — assumptions, definitions, and results are stated explicitly, not assumed from context
- **Auditable** — a cross-phase agent can verify consistency between phases (e.g., a proof's assumptions vs. the numerical implementation's parameterization)

This is especially important between Phase 3 and 4: the theorist writes `proof_status.md` assuming the data_scientist may audit it; the data_scientist writes `numerical_status.md` assuming the theorist may audit it.

### Layer 3 — Highlight Purposes

Concise 200–400 word summaries used for:

1. **Web UI display** — the summary paragraph shown on the project dashboard
2. **Paper highlights** — higher-level summary constructed from a Layer 2 paper summary
3. **Theoretical readiness** — higher-level summary of a method's proof status
4. **Numerical status** — higher-level summary of current simulation/experiment results
5. **Draft status** — higher-level summary of current paper draft progress

---

## Project Folder Structure

```
/project-<NNN>/
│
├── references/                          # Shared across all phases, runs, and roles
│   ├── papers/                          # Canonical per-paper cards (written by lead only)
│   │   └── <source>-<id>.md             # Layer 2: per-paper summary (YAML frontmatter + body)
│   ├── reference-index.json             # Machine-readable index generated from papers/
│   ├── literature-summary.md            # Layer 2: consolidated synthesis of all references
│   ├── <paper_id>.pdf                   # Downloaded paper (Layer 1, moved from delta by lead)
│   ├── <paper_id>_highlight.md          # Layer 3: per-paper innovation tracing card
│   └── reference-delta/                 # Staging: paper suggestions (JSON) + PDFs from agents
│
├── Phase-1/                             # Literature Review
│   ├── highlight.md                     # Layer 3: research direction potential (updated each run)
│   ├── general-focus.md                 # Layer 2: copy of latest run's general-audience review (UI details view)
│   ├── run-<id>/
│   │   ├── lead-report.md               # Per-run report by the research lead
│   │   ├── theorist-focus.md            # Layer 2: lit review focused for theorist
│   │   ├── data_scientist-focus.md      # Layer 2: lit review focused for data_scientist
│   │   └── general-focus.md             # Layer 2: lit review for general audience
│   ├── run-<id>/
│   │   └── ...
│   └── ...
│
├── Phase-2/                             # Method Development
│   ├── method-registry.json              # All methods: id, name, one-line description, version, sha256, scores, P3/P4/P5 status
│   ├── highlight.md                     # Layer 3: method pool status for UI (updated each run)
│   ├── run-<id>/
│   │   └── lead-report.md
│   ├── run-<id>/
│   │   └── lead-report.md
│   └── ...
│
├── <method_stable_id>/                  # Per-method folder (created end of Phase-2, one per method)
│   │
│   ├── <stable_id>.md                   # Layer 2: detailed method description
│   │
│   ├── proofs/                          # Phase 3 — Theory & Proofs (created on first P3 run)
│   │   ├── proof_status.md              # Layer 2: proof status, assumptions, dependency graph, open items
│   │   ├── highlight.md                 # Layer 3: theorist's own summary (updated each run)
│   │   ├── review.md                    # Layer 3: data_scientist's cross-review (updated each run)
│   │   ├── lead-highlight.md            # Layer 3: research_lead's user-facing synthesis (updated each run)
│   │   ├── material/                    # Single live copy — continuously improved across runs
│   │   ├── archived/                    # Retired proof material
│   │   ├── run-1.md                     # Per-run report by theorist
│   │   ├── run-2.md
│   │   └── ...
│   │
│   ├── numerical/                       # Phase 4 — Implementation & Experiments (created on first P4 run)
│   │   ├── numerical_status.md          # Layer 2: code/results status, version alignment with method
│   │   ├── highlight.md                 # Layer 3: data_scientist's own summary (updated each run)
│   │   ├── review.md                    # Layer 3: theorist's cross-review (updated each run)
│   │   ├── lead-highlight.md            # Layer 3: research_lead's user-facing synthesis (updated each run)
│   │   ├── implementation/              # Single live copy — kept current with method definition
│   │   ├── results/                     # All numerical results and simulation outputs
│   │   ├── archived/                    # Retired material (wrong impl, old version, etc.)
│   │   ├── run-1.md                     # Per-run report by data_scientist
│   │   ├── run-2.md
│   │   └── ...
│   │
│   └── draft/                           # Phase 5 — Paper Drafting (created on first P5 run)
│       ├── draft_status.md              # Layer 2: current draft status
│       ├── highlight.md                 # Layer 3: user-facing summary of draft status (updated each run)
│       ├── theorist-audit.md            # Layer 2: theorist's audit of paper vs. proofs (revision runs)
│       ├── analyst-audit.md             # Layer 2: data_scientist's audit of paper vs. implementation (revision runs)
│       ├── reviewer-report.md           # Layer 2: paper_reviewer's independent review (revision runs)
│       ├── latex/                       # LaTeX source: .tex files, .bib, figures/
│       ├── archived/
│       ├── run-1.md
│       ├── run-2.md
│       └── ...
│
├── <method_stable_id>/                  # Another method
│   └── ...
│
└── ...
```

---

## Phase → Folder Mapping

| Phase | Name | Folder | Owner Role | Key Layer 2 Artifact | Layer 3 Highlight |
|-------|------|--------|------------|---------------------|-------------------|
| 1 | Literature Review | `Phase-1/` | Research Lead | `references/literature-summary.md` | `highlight.md` |
| 2 | Method Development | `Phase-2/` | Research Lead | `method-registry.json`, `<stable_id>.md` | `highlight.md` |
| 3 | Theory & Proofs | `proofs/` | Theorist | `proof_status.md` | `lead-highlight.md` (UI); `highlight.md` (owner's own) |
| 4 | Numerical Validation | `numerical/` | Data Scientist | `numerical_status.md` | `lead-highlight.md` (UI); `highlight.md` (owner's own) |
| 5 | Paper Drafting | `draft/` | Research Lead | `draft_status.md` | `highlight.md` |

---

## Design Conventions

### Stable IDs
- Each method gets a unique, permanent `stable_id` assigned at the end of Phase 2
- The `stable_id` is used as the per-method folder name at the project root (folder created at the end of Phase 2)
- This ID remains fixed across all subsequent phases — even if the method is renamed

### Archive Strategy
- Each work area (`proofs/`, `numerical/`, `draft/`) maintains exactly **one live working copy**
- Old or retired versions go into `archived/` — never deleted
- Per-run reports (`run-N.md`) provide the chronological record of what was done each run

### References Pool
- The `references/` folder at the project root is **universally shared** — every phase, every run, every role reads from it
- Each paper gets one PDF (Layer 1), one Layer 2 summary card under `papers/` (with YAML frontmatter), and one Layer 3 innovation highlight (`<paper_id>_highlight.md`)
- `reference-index.json` is machine-generated from `papers/`; `reference-delta/` is the staging area for agent paper suggestions (cleared by the lead after each promotion)

### Run Reports vs. Status Files vs. Highlights
- **Run reports** (`run-N.md`) are append-only chronological records of a single run's work — "what was done this run"
- **Status files** (`proof_status.md`, `numerical_status.md`, `draft_status.md`) are living Layer 2 documents (~2–16 KB) that summarize the *current* state — rewritten/updated each run to reflect the latest
- **Highlight files** are living Layer 3 documents (200–400 words) — rewritten each run. The phase owner writes their own `highlight.md`; the **web UI displays the research lead's synthesis** — `lead-highlight.md` for `proofs/` and `numerical/`, and `highlight.md` for Phase-1, Phase-2, and `draft/` (where the lead authors it directly)
