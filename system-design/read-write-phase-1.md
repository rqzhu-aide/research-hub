# Phase 1 — Literature Review (Read/Write Rules)

References [file-system.md](./file-system.md) for the canonical folder layout.
See [read-write-overview.md](./read-write-overview.md) for output types, cross-phase dependencies, and update semantics.

**Goal:** Build a shared pool of references and synthesize the literature landscape.

## Folder context

```
Phase-1/                             # Literature Review
├── highlight.md                  # Layer 3 — research direction potential (updated each run)
├── general-focus.md              # Layer 2 — copy of latest run's general-audience review (UI details view)
├── run-001/
│   ├── lead-report.md            # Full run report (Layer 1)
│   ├── theorist-focus.md         # Layer 2 — lit review focused for theorist
│   ├── data_scientist-focus.md   # Layer 2 — lit review focused for data_scientist
│   └── general-focus.md          # Layer 2 — lit review for general audience
├── run-002/
│   └── ...
└── ...

references/                       # Shared across all phases
├── papers/                        # Canonical per-paper markdown cards (written by lead only)
│   └── <source>-<id>.md           # Layer 2 — per-paper summary with YAML frontmatter
├── reference-index.json           # Generated machine-readable index (built from papers/)
├── literature-summary.md          # Layer 2 — consolidated synthesis of all references
├── <paper_id>.pdf                 # Layer 1 — downloaded paper
├── <paper_id>_highlight.md        # Layer 3 — per-paper innovation highlight (written by lead)
└── reference-delta/               # Staging area — paper suggestions (JSON) + downloaded PDFs from agents
```

## Run 1 (initial)

### Discovery (parallel — theorist, data_scientist, research_lead)

Each role searches for papers with their own focus. They write suggestions and stage downloaded PDFs in the delta folder. They never touch the canonical library.

| Role | Reads | Writes |
|------|-------|--------|
| **theorist** | Project brief | `references/reference-delta/` — paper suggestions (JSON) + staged PDFs |
| **data_scientist** | Project brief | `references/reference-delta/` — paper suggestions (JSON) + staged PDFs |
| **research_lead** | Project brief | `references/reference-delta/` — paper suggestions (JSON) + staged PDFs |

### Promotion (lead only)

The lead receives a prompt to convert the collected input into the canonical output, moving staged PDFs into `references/`. Afterwards, clears the delta folder.

**Input (what the lead reads):**

```
references/reference-delta/        # All paper suggestions (JSON) + staged PDFs from all roles
```

**Output (what the lead writes):**

```
references/
├── <paper_id>.pdf                 # Layer 1 — moved from reference-delta/
├── papers/
│   └── <source>-<id>.md           # Layer 2 — one per unique paper
├── <paper_id>_highlight.md        # Layer 3 — one per paper
├── reference-index.json           # Regenerated from papers/
└── literature-summary.md          # Layer 2 — consolidated synthesis

Phase-1/
├── highlight.md                   # Layer 3 — research direction potential
├── general-focus.md               # Layer 2 — copied from run-001/ (UI details view)
└── run-001/
    ├── lead-report.md             # Full run report
    ├── theorist-focus.md          # Layer 2 — lit review for theorist
    ├── data_scientist-focus.md    # Layer 2 — lit review for data_scientist
    └── general-focus.md           # Layer 2 — lit review for general audience
```

## Run N (re-run)

### Discovery (parallel)

| Role | Reads | Writes |
|------|-------|--------|
| **all roles** | `references/reference-index.json` (current pool), `references/literature-summary.md` | `references/reference-delta/` — new paper suggestions only (skip if already in index) + staged PDFs for new suggestions |

### Promotion (lead only)

The lead receives a prompt to convert the collected input into the canonical output, moving staged PDFs into `references/`. Afterwards, clears the delta folder.

**Input (what the lead reads):**

```
references/
├── reference-delta/               # New paper suggestions (JSON) + staged PDFs
└── reference-index.json           # Current index (for dedup)
```

**Output (what the lead writes):**

```
references/
├── <paper_id>.pdf                 # Layer 1 — moved from reference-delta/ (new papers)
├── papers/
│   └── <source>-<id>.md           # Layer 2 — new papers only
├── <paper_id>_highlight.md        # Layer 3 — new papers only
├── reference-index.json           # Regenerated
└── literature-summary.md          # Updated in place

Phase-1/
├── highlight.md                   # Updated in place
├── general-focus.md               # Updated copy from latest run (UI details view)
└── run-<NNN>/
    ├── lead-report.md             # New run report
    ├── theorist-focus.md          # Updated
    ├── data_scientist-focus.md    # Updated
    └── general-focus.md           # Updated
```
