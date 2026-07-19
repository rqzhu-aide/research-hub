# Phase: Literature Review

## Goal
Build a comprehensive, organized bibliography for the project — first an
initial survey, then (as the project matures) deep targeted searches that
keep the references current and relevant to what's actually been proposed.

## Gating
**None.** Literature review can run at any time — at project start, and at
any later point when the project has matured.

## Two modes
- **Run (initial scan):** broad survey from each agent's lens — classical
  works, recent high-impact papers, and papers directly relevant to the
  project's stated goals.
- **Deep run (re-scan):** context-aware targeted search. Each agent first
  inspects the current project state (proposed method, theory, code, data),
  then pulls in papers that directly relate to what has actually been done.

## Folder
All outputs land in `references/literature-review/`. Each run creates its
own numbered subfolder so history accumulates rather than overwrites:
- `references/literature-review/run/01/`, `…/02/`, …
- `references/literature-review/deep-run/01/`, `…/02/`, …

## Profiles
`research_lead`, `theorist`, `data_scientist` — each searches in parallel
from their own lens. The three lenses are complementary, not overlapping:
- **research_lead** — domain significance (what field, what matters)
- **theorist** — theoretical / methodological foundations
- **data_scientist** — computational / implementation landscape

## When to use which mode
- **Run** at project start, or when entering a new sub-area.
- **Deep run** after Method Development / Theoretical Justification have
  produced concrete proposals, so the targeted search has something to
  target. A deep run with nothing to inspect degenerates into a regular run.
