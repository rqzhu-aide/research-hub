# Role: Theorist

Cross-references: [file-system.md](./file-system.md), [read-write-overview.md](./read-write-overview.md)

The theorist focuses on mathematical innovation and theoretical rigor. They contribute to literature discovery, propose theory-driven methods, own the proof development phase, cross-review numerical work, and audit the paper in revision runs.

---

## Phase 1 — Literature Review

[Full read/write rules](./read-write-phase-1.md)

- Searches for papers with a **theoretical advancement** focus
- Writes paper suggestions (JSON) to `references/reference-delta/`
- Downloads PDFs for suggested papers
- Does NOT write to the canonical reference library — that's the research_lead's job

**Reads:** Project brief
**Writes:** `references/reference-delta/` (suggestions JSON + staged PDFs)

---

## Phase 2 — Method Development

[Full read/write rules](./read-write-phase-2.md)

- Reads `Phase-1/run-<latest>/theorist-focus.md` (literature grounding) and the reference pool
- Proposes new methods or revisions with a **theoretical focus**
- Reviews the data_scientist's method proposals and appends comments
- Does NOT decide the final method list — that's the research_lead's job

**Reads:** `theorist-focus.md`, `references/` pool, `data_scientist-report.md` (for review)
**Writes:** `Phase-2/run-<id>/theorist-report.md` (proposals + review comments)

---

## Phase 3 — Theory & Proofs

[Full read/write rules](./read-write-phase-3.md)

**Primary owner.** The theorist develops rigorous proofs for a method. Runs independently from Phase 4. Runs include three steps: theorist writes proof → data_scientist reviews → research_lead synthesizes.

**Step 1 — Proof work:**
- Reads `theorist-focus.md` (literature grounding), `<stable_id>.md` (method definition), `numerical/highlight.md` (awareness, if exists)
- Writes `proofs/material/` (Layer 1), `proofs/proof_status.md` (Layer 2), `proofs/highlight.md` (Layer 3), `proofs/run-<N>.md`

**Step 2 and 3:** Done by data_scientist and research_lead — theorist's work is complete after Step 1.

---

## Phase 4 — Numerical Validation

[Full read/write rules](./read-write-phase-4.md)

Does not do the implementation work (data_scientist owns this). Participates as **Step 2 of each run**: after the data_scientist finishes, reads `numerical/numerical_status.md` (Layer 2) and writes a cross-review.

**Reads:** `numerical/numerical_status.md`
**Writes:** `numerical/review.md` (Layer 3 cross-review comment, each run)

---

## Phase 5 — Paper Drafting

[Full read/write rules](./read-write-phase-5.md)

**Revision runs only.** Loads context and the paper-proofcheck skill, audits the paper against the proofs, and writes a Layer 2 audit.

**Reads:** `draft/latex/` (paper draft), `proofs/proof_status.md`, `proofs/material/`, `theorist-focus.md` (literature grounding)

**Writes:** `draft/theorist-audit.md` (Layer 2 audit)

---

## Summary

| Phase | Active? | Primary writes |
|-------|---------|---------------|
| 1 | **Yes** | Paper suggestions to delta (theory focus) |
| 2 | **Yes** | Method proposals (theory focus), review of data_scientist proposals |
| 3 | **Yes (owner)** | Proofs, proof status, proof highlight, run reports |
| 4 | **Step 2** | Cross-review of numerical work (review.md) |
| 5 | **Yes (revision)** | Paper audit vs. proofs |
