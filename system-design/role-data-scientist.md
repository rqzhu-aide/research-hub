# Role: Data Scientist

Cross-references: [file-system.md](./file-system.md), [read-write-overview.md](./read-write-overview.md)

The data_scientist focuses on computational implementation and empirical validation. They contribute to literature discovery, propose computation-driven methods, own the numerical validation phase, cross-review proof work, and audit the paper in revision runs.

---

## Phase 1 — Literature Review

[Full read/write rules](./read-write-phase-1.md)

- Searches for papers with a **computational advantage** focus
- Writes paper suggestions (JSON) to `references/reference-delta/`
- Downloads PDFs for suggested papers
- Does NOT write to the canonical reference library — that's the research_lead's job

**Reads:** Project brief
**Writes:** `references/reference-delta/` (suggestions JSON + staged PDFs)

---

## Phase 2 — Method Development

[Full read/write rules](./read-write-phase-2.md)

- Reads `Phase-1/run-<latest>/data_scientist-focus.md` (literature grounding) and the reference pool
- Proposes new methods or revisions with a **computational focus**
- Reviews the theorist's method proposals and appends comments
- Does NOT decide the final method list — that's the research_lead's job

**Reads:** `data_scientist-focus.md`, `references/` pool, `theorist-report.md` (for review)
**Writes:** `Phase-2/run-<id>/data_scientist-report.md` (proposals + review comments)

---

## Phase 3 — Theory & Proofs

[Full read/write rules](./read-write-phase-3.md)

Does not do the proof work (theorist owns this). Participates as **Step 2 of each run**: after the theorist finishes, reads `proofs/proof_status.md` (Layer 2) and writes a cross-review.

**Reads:** `proofs/proof_status.md`
**Writes:** `proofs/review.md` (Layer 3 cross-review comment, each run)

---

## Phase 4 — Numerical Validation

[Full read/write rules](./read-write-phase-4.md)

**Primary owner.** The data_scientist implements and empirically validates a method. Runs independently from Phase 3. Runs include three steps: data_scientist writes implementation → theorist reviews → research_lead synthesizes.

**Run 1** is always a **preliminary/exploratory run**: develop first-pass implementation, test on simple cases, establish the computational framework.

**Run N** are **comprehensive runs**: full simulation studies, benchmark comparisons, publication-quality results.

**Step 1 — Implementation work:**
- Reads `data_scientist-focus.md` (literature grounding), `<stable_id>.md` (method definition), `proofs/highlight.md` (awareness, if exists)
- Writes `numerical/implementation/` (Layer 1), `numerical/results/` (Layer 1), `numerical/numerical_status.md` (Layer 2 — must be auditable by theorist), `numerical/highlight.md` (Layer 3), `numerical/run-<N>.md`

**Step 2 and 3:** Done by theorist and research_lead — data_scientist's work is complete after Step 1.

---

## Phase 5 — Paper Drafting

[Full read/write rules](./read-write-phase-5.md)

**Revision runs only.** Loads context, audits the paper against the implementation and results, and writes a Layer 2 audit.

**Reads:** `draft/latex/` (paper draft), `numerical/numerical_status.md`, `numerical/implementation/`, `numerical/results/`, `data_scientist-focus.md` (literature grounding)

**Writes:** `draft/analyst-audit.md` (Layer 2 audit)

---

## Summary

| Phase | Active? | Primary writes |
|-------|---------|---------------|
| 1 | **Yes** | Paper suggestions to delta (computation focus) |
| 2 | **Yes** | Method proposals (computation focus), review of theorist proposals |
| 3 | **Step 2** | Cross-review of proofs (review.md) |
| 4 | **Yes (owner)** | Implementation, results, numerical status, highlight, run reports |
| 5 | **Yes (revision)** | Paper audit vs. implementation/results |
