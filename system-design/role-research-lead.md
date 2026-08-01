# Role: Research Lead

Cross-references: [file-system.md](./file-system.md), [read-write-overview.md](./read-write-overview.md)

The research_lead orchestrates the project across all phases: they are the only role that writes to the canonical reference library, decides the method portfolio, and writes and revises the paper.

---

## Phase 1 — Literature Review

[Full read/write rules](./read-write-phase-1.md)

**Discovery (parallel with theorist and data_scientist):**
- Searches for papers with a **method innovation** focus
- Writes paper suggestions (JSON) to `references/reference-delta/`
- Stages downloaded PDFs for suggested papers in `references/reference-delta/`

**Promotion (lead only):**
- Reads all deltas from all roles, deduplicates
- Moves staged PDFs from `references/reference-delta/` into `references/`
- Writes canonical per-paper Layer 2 summaries: `references/papers/<source>-<id>.md`
- Writes per-paper Layer 3 highlights: `references/<paper_id>_highlight.md`
- Regenerates `references/reference-index.json`
- Writes consolidated literature synthesis: `references/literature-summary.md`
- Clears `references/reference-delta/`
- Writes run report + three role-facing summaries: `Phase-1/run-<id>/`
- Writes phase highlight: `Phase-1/highlight.md`
- Copies the general-audience review to `Phase-1/general-focus.md` (UI details view)

---

## Phase 2 — Method Development

[Full read/write rules](./read-write-phase-2.md)

- Reads theorist and data_scientist method proposals and cross-reviews
- Decides method list: add, update version, retire, or merge
- Maintains `Phase-2/method-registry.json`
- Writes the canonical Layer 2 method description: `<method_stable_id>/<stable_id>.md` (one per-method folder at project root)
- Assigns evaluation scores and a one-sentence description for each method (UI methods table)
- Creates per-method root folders: `<method_stable_id>/<stable_id>.md`
- Writes phase highlight: `Phase-2/highlight.md`
- Writes run report: `Phase-2/run-<id>/lead-report.md`

---

## Phase 3 — Theory & Proofs

[Full read/write rules](./read-write-phase-3.md)

Does not do the proof work (theorist owns this). Participates as **Step 3 of each run**: reads `proofs/proof_status.md` (Layer 2) and `proofs/review.md` (data_scientist's cross-review), synthesizes a user-facing highlight.

**Writes:** `proofs/lead-highlight.md` (Layer 3 user-facing synthesis, each run)

---

## Phase 4 — Numerical Validation

[Full read/write rules](./read-write-phase-4.md)

Does not do the implementation work (data_scientist owns this). Participates as **Step 3 of each run**: reads `numerical/numerical_status.md` (Layer 2) and `numerical/review.md` (theorist's cross-review), synthesizes a user-facing highlight.

**Writes:** `numerical/lead-highlight.md` (Layer 3 user-facing synthesis, each run)

---

## Phase 5 — Paper Drafting

[Full read/write rules](./read-write-phase-5.md)

**Primary owner.**

**Run 1 (initial draft):** Loads the paper writing skill, reads Layer 2 summaries from all phases, creates the paper scaffolding, then writes each section in detail using full Layer 1 material. Produces a complete draft — no revision.

**Revision runs:** After theorist, data_scientist, and paper_reviewer complete their audits/review, loads the paper writing skill and revises the paper based on all comments.

**Reads:** All source artifacts (method definition, proof material, numerical material, references, audits, review report)

**Writes:** `draft/latex/`, `draft/draft_status.md`, `draft/highlight.md`, `draft/run-<N>.md`

---

## Summary

| Phase | Active? | Primary writes |
|-------|---------|---------------|
| 1 | **Yes** | Canonical reference library, literature synthesis, role-facing summaries |
| 2 | **Yes** | Method registry, method summaries, scores, per-method folders |
| 3 | **Step 3** | lead-highlight.md (user-facing synthesis) |
| 4 | **Step 3** | lead-highlight.md (user-facing synthesis) |
| 5 | **Yes (owner)** | Initial draft, revision |
