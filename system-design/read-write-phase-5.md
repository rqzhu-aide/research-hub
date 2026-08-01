# Phase 5 — Paper Drafting (Read/Write Rules)

References [file-system.md](./file-system.md) for the canonical folder layout.
See [read-write-overview.md](./read-write-overview.md) for output types, cross-phase dependencies, and update semantics.

**Goal:** Assemble a publication-ready paper from all project artifacts. Gated: cannot run until both Phase 3 and Phase 4 have completed at least one run each.

## Folder context

```
<method_stable_id>/draft/
├── draft_status.md                # Layer 2 — current draft status; frontmatter records method_version (updated each run)
├── highlight.md                   # Layer 3 — user-facing draft status (updated each run)
├── theorist-audit.md              # Layer 2 — theorist's audit of the paper (updated each revision run)
├── analyst-audit.md               # Layer 2 — data_scientist's audit of the paper (updated each revision run)
├── reviewer-report.md             # Layer 2 — paper_reviewer's independent review (updated each revision run)
├── latex/                         # LaTeX source, .bib, figures/
├── archived/
└── run-1.md, run-2.md, ...
```

## Run 1 — Initial Draft

The first run produces a complete initial draft — no revision, just writing.

### Step 1 — Lead scaffolding

The research_lead receives instructions, loads the paper writing skill, reads Layer 2 summaries from all phases, and creates the paper scaffolding (section structure, key points per section).

**Input:**

```
Run-specific instruction
<method_stable_id>/<stable_id>.md              # Method definition (Layer 2)
<method_stable_id>/proofs/proof_status.md      # Layer 2 — proof summary
<method_stable_id>/numerical/numerical_status.md # Layer 2 — numerical summary
references/literature-summary.md               # Layer 2 — literature synthesis
```

**Output:**

```
<method_stable_id>/draft/
├── latex/                         # Scaffolding: section structure, .bib skeleton
└── draft_status.md                # Layer 2 — sections planned, gaps, todo
```

### Step 2 — Lead writes sections

The research_lead reads full detailed material from all phases and writes each section in detail.

**Input:**

```
<method_stable_id>/draft/draft_status.md        # Current scaffolding plan
<method_stable_id>/proofs/material/             # Full proof material (Layer 1)
<method_stable_id>/numerical/implementation/    # Full code (Layer 1)
<method_stable_id>/numerical/results/           # Full results (Layer 1)
references/                                      # Full reference pool
```

**Output:**

```
<method_stable_id>/draft/
├── latex/                         # Complete initial draft
├── draft_status.md                # Updated — sections done, remaining gaps
├── highlight.md                   # Layer 3 — draft progress for UI
└── run-1.md                       # Run report
```

## Run N — Revision Run

Revision runs involve auditing by all roles, an independent review, and lead revision.

### Step 1 — Theorist audit

The theorist loads their context and the paper-proofcheck skill, audits the paper against the proofs, and writes a Layer 2 audit.

**Input:**

```
Run-specific instruction
<method_stable_id>/draft/latex/                 # Current paper draft
<method_stable_id>/proofs/proof_status.md       # Layer 2
<method_stable_id>/proofs/material/             # Full proof material (Layer 1)
Phase-1/run-<latest>/theorist-focus.md          # Literature grounding
```

**Output:**

```
<method_stable_id>/draft/theorist-audit.md      # Layer 2 — audit of paper vs. proofs
```

### Step 2 — Analyst audit

The data_scientist loads their context, audits the paper against the implementation and results, and writes a Layer 2 audit.

**Input:**

```
Run-specific instruction
<method_stable_id>/draft/latex/                     # Current paper draft
<method_stable_id>/numerical/numerical_status.md   # Layer 2
<method_stable_id>/numerical/implementation/        # Full code (Layer 1)
<method_stable_id>/numerical/results/               # Full results (Layer 1)
Phase-1/run-<latest>/data_scientist-focus.md        # Literature grounding
```

**Output:**

```
<method_stable_id>/draft/analyst-audit.md           # Layer 2 — audit of paper vs. implementation/results
```

### Step 3 — Paper reviewer review

The paper_reviewer loads reviewer skills and independently reviews the paper. Does not read the theorist or analyst audits — acts as an independent reviewer.

**Input:**

```
Run-specific instruction
<method_stable_id>/draft/latex/                 # Current paper draft (only)
```

**Output:**

```
<method_stable_id>/draft/reviewer-report.md     # Layer 2 — independent full review
```

### Step 4 — Lead revision

The research_lead loads the paper writing skill, reads all audit and review comments, and revises the paper.

**Input:**

```
Run-specific instruction
<method_stable_id>/draft/latex/                 # Current paper draft
<method_stable_id>/draft/theorist-audit.md      # Layer 2 — theorist's audit
<method_stable_id>/draft/analyst-audit.md       # Layer 2 — analyst's audit
<method_stable_id>/draft/reviewer-report.md     # Layer 2 — independent review
```

**Output:**

```
<method_stable_id>/draft/
├── latex/                         # Revised draft (archive old)
├── draft_status.md                # Updated in place
├── highlight.md                   # Updated in place
└── run-<N>.md                     # New run report
```
