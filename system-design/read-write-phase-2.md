# Phase 2 — Method Development (Read/Write Rules)

References [file-system.md](./file-system.md) for the canonical folder layout.
See [read-write-overview.md](./read-write-overview.md) for output types, cross-phase dependencies, and update semantics.

**Goal:** Propose, refine, score, and register candidate methods. Each surviving method gets a `stable_id` and its own folder.

## Folder context

```
Phase-2/
├── method-registry.json            # All methods: id, name, one-line description, version, sha256, scores, P3/P4/P5 status
├── highlight.md                   # Layer 3 — UI-facing summary of method pool (updated each run)
├── run-001/
│   ├── lead-report.md             # Full run report (Layer 1)
│   ├── theorist-report.md         # Full report — theorist's method proposals & reviews
│   └── data_scientist-report.md   # Full report — data_scientist's method proposals & reviews
├── run-002/
│   └── ...
└── ...

<method_stable_id>/                 # Per-method folder (created by lead at end of run)
├── <stable_id>.md                  # Layer 2 — detailed method description
├── proofs/                         # Phase 3 (created on first P3 run)
├── numerical/                      # Phase 4 (created on first P4 run)
└── draft/                          # Phase 5 (created on first P5 run)
```

### Versioning

Each method is uniquely identified by `<id, version, sha256>`. The sha256 is a content fingerprint of the canonical method description `<method_stable_id>/<stable_id>.md` — it changes on any edit to that file. The version number is bumped only when the lead determines the change materially affects computation or proofs (e.g., modified assumptions, altered algorithm, new constraints). Cosmetic edits or clarifications that don't change mathematical content update the sha256 but not the version.

**When version is bumped, downstream work is stale:** the method's proofs (`proofs/`) and numerical results (`numerical/`) were produced against an older version. They must be re-audited on the next Phase 3 or 4 run. The theorist and data_scientist check the method version in the registry against what they last worked with.

## Run 1 (initial)

### Stage 1 — Proposals (parallel — theorist, data_scientist)

Each role proposes methods with their own focus.

| Role | Reads | Writes |
|------|-------|--------|
| **theorist** | `Phase-1/run-001/theorist-focus.md`, `references/` pool | `Phase-2/run-001/theorist-report.md` — method proposals |
| **data_scientist** | `Phase-1/run-001/data_scientist-focus.md`, `references/` pool | `Phase-2/run-001/data_scientist-report.md` — method proposals |

### Stage 2 — Cross-review (parallel)

Each role reads the other's Stage 1 report and appends review comments to their own report.

| Role | Reads | Writes |
|------|-------|--------|
| **theorist** | `Phase-2/run-001/data_scientist-report.md` | Appends cross-review to `Phase-2/run-001/theorist-report.md` |
| **data_scientist** | `Phase-2/run-001/theorist-report.md` | Appends cross-review to `Phase-2/run-001/data_scientist-report.md` |

### Evaluation (lead only)

The lead receives a prompt to evaluate all proposals and produce the canonical method artifacts. Each registry entry includes a one-sentence `description` of the method — displayed in the UI methods table (see [ui-display.md](./ui-display.md)).

**Input (what the lead reads):**

```
Phase-2/run-001/
├── theorist-report.md             # Theorist's proposals + cross-review
└── data_scientist-report.md       # Data scientist's proposals + cross-review
```

**Output (what the lead writes):**

```
Phase-2/
├── method-registry.json            # All methods with id, name, one-line description, version, sha256, scores
├── highlight.md                   # Layer 3 — method pool status for UI
└── run-001/
    └── lead-report.md             # Full run report

<method_stable_id>/
└── <stable_id>.md                 # Layer 2 — detailed method description (one folder per method)
```

## Run N (re-run)

### Stage 1 — Proposals (parallel — theorist, data_scientist)

| Role | Reads | Writes |
|------|-------|--------|
| **theorist** | Latest `theorist-focus.md`, `Phase-2/method-registry.json`, existing method summaries | `Phase-2/run-<NNN>/theorist-report.md` — new proposals or revisions |
| **data_scientist** | Latest `data_scientist-focus.md`, `Phase-2/method-registry.json`, existing method summaries | `Phase-2/run-<NNN>/data_scientist-report.md` — new proposals or revisions |

### Stage 2 — Cross-review (parallel)

Each role reads the other's Stage 1 report and appends review comments to their own report.

| Role | Reads | Writes |
|------|-------|--------|
| **theorist** | `Phase-2/run-<NNN>/data_scientist-report.md` | Appends cross-review to `Phase-2/run-<NNN>/theorist-report.md` |
| **data_scientist** | `Phase-2/run-<NNN>/theorist-report.md` | Appends cross-review to `Phase-2/run-<NNN>/data_scientist-report.md` |

### Evaluation (lead only)

The lead receives a prompt to evaluate the new proposals and update the canonical artifacts.

**Input (what the lead reads):**

```
Phase-2/
├── run-<NNN>/
│   ├── theorist-report.md         # New proposals + reviews
│   └── data_scientist-report.md   # New proposals + reviews
└── method-registry.json            # Current registry

<method_stable_id>/
└── <stable_id>.md                 # Existing method descriptions
```

**Output (what the lead writes):**

```
Phase-2/
├── method-registry.json            # Updated in place (add/version/retire/merge; bump version only if material change)
├── highlight.md                   # Updated in place
└── run-<NNN>/
    └── lead-report.md             # New run report

<method_stable_id>/
└── <stable_id>.md                 # Updated for changed methods
```
