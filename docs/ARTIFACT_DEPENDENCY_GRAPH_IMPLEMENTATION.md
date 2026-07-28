# Artifact Dependency Graph — Implementation Plan (Revised)

> **Status**: Ready for implementation review.
> **Supersedes**: `ARTIFACT_DEPENDENCY_GRAPH.md` (July 2026 draft).
> **Scope**: Level 1 only — derived graph from existing data, no agent prompt changes.
> **Testbed**: project-004-entangled-langevin-sampling (17 statements, 9 decision records, 7 methods).

---

## 0. What changed from the original draft

Three issues were discovered by validating the original draft against real
project-004 data and hub source code. They are all fixable without redesign:

1. **`method_selection` is `null` in all existing manifests.** The original
   design assumed `manifest["method_selection"]["stable_id"]` would be
   populated for Phase 03/04 runs. In reality, project-004's runs predate the
   method-menu publication system (commit `9f94cb4`), so the method identity
   is only recoverable by parsing the `output_root` path. The implementation
   must include a fallback parser.

2. **`evidential_basis` exists in two places and they differ.** Each
   `scientific_record_changes` entry has `evidential_basis` at both the
   top level AND inside `proposed_values`. The top-level version has clean,
   parseable file paths; the `proposed_values` version has triply-nested
   path corruption (a known agent output bug). The graph builder must use the
   top-level field exclusively.

3. **Decision records live at `phase-summaries/<phase>/<run_id>.decision.json`**,
   not at a location that `finalize_run_submission` already knows about. The
   update hook must construct or look up the decision record path from the run
   manifest's `decision_path` field.

Additionally, three design simplifications were made:

- **Dropped Jaccard similarity grouping** from Level 1. Exact-hash assumption
  matching is sufficient; near-duplicate detection is a Level 2 concern.
- **Staleness systems stay fully separate.** The graph does NOT modify
  `project.yaml` phase fields (`stale`, `partially_stale`, etc.). The graph's
  staleness results live entirely inside `.artifact-graph.json`. The existing
  `_stale_changed_method_descendants_unlocked` system is untouched.
- **No new fields added to `project.yaml`.** All graph state is in the derived
  `.artifact-graph.json` file, respecting the sealed-history stability principle.

---

## 1. Motivation

When a method definition, a proof assumption, or an empirical result changes,
the researcher needs to know **exactly which downstream claims, experiments,
and draft sections are affected** — not just "Phase 03 is stale."

The current system has phase-level staleness marking: when a Phase 02 method
changes, `_stale_changed_method_descendants_unlocked` marks entire dependent
phases as stale. This is correct but coarse. A revised method definition may
invalidate one theorem while leaving five other claims unaffected.

The artifact dependency graph adds **claim-level impact analysis** as a
derived, queryable layer on top of existing sealed data. It does not replace
the phase-level system — it provides finer granularity for the UI and for
researcher queries.

---

## 2. Design principles

1. **Derived, not primary.** The graph is rebuilt from existing sealed sources
   (decision records, method menu files, run manifests). It is never a source
   of truth that agents write to. If lost, it can be fully reconstructed.

2. **Updated after each run.** The graph is incrementally rebuilt inside
   `finalize_run_submission`, after the decision record is sealed. No new user
   action is required.

3. **Level 1 requires no agent prompt changes.** The graph is assembled from
   data that decision records already contain.

4. **Conservative impact analysis.** When the system cannot determine whether
   a statement depends on a changed node, it flags it as "potentially
   affected" rather than silently ignoring it.

5. **Append-only history.** Like decision records, the graph preserves
   superseded nodes. A withdrawn or revised statement remains visible with its
   successor link.

6. **Failure-isolated.** Graph build failures are logged but never block run
   finalization. A corrupt or missing decision record degrades gracefully —
   the graph is built from whatever records are valid.

---

## 3. Primary data sources (verified against project-004)

### 3.1 Decision records

**Location**: `<project_dir>/phase-summaries/<phase_slug>/<run_id>.decision.json`

> ⚠️ **Correction from original draft**: The original draft's integration code
> implied decision records would be read via `_read_decision_record_file()`
> inside `finalize_run_submission`. In reality, `finalize_run_submission` does
> not currently read decision records. The update hook must read the decision
> record from the path stored in the run manifest's `decision_path` field, or
> construct it from the standard `phase-summaries/` layout.

**Verified structure** of each `scientific_record_changes[]` entry:

| Field | Location | Example | Graph use |
|---|---|---|---|
| `statement_id` | top-level | `S-P03-R001-summary-research_lead-001` | Node identity |
| `parent_statement_id` | top-level | `S-P02-R001-round01-theorist-001` | Supersedes edge |
| `operation` | top-level | `add`, `revise`, `withdraw` | Node lifecycle |
| `evidential_basis` | **top-level** | `["Theorist Round 1 proof sketch: branches/.../theorist.md §1.2–1.4"]` | Evidence edges |
| `change_origin` | top-level | `{"phase": "03-idea-evaluation", "run": "9081e83c-...", "round_or_stage": "summary", "role": "research_lead"}` | Origin metadata |
| `proposed_values.assumptions` | nested | `["Strong log-concavity: −∇²log p ⪰ ρI_d", ...]` | Assumption nodes |
| `proposed_values.statement_type` | nested | `"Mathematical statement"` | Node metadata |
| `proposed_values.wording` | nested | `"For the spectral graph coupling..."` | Node content |
| `proposed_values.scope` | nested | `"Finite N ≥ 2, strongly log-concave..."` | Node metadata |
| `proposed_values.logical_status` | nested | `"conjectured"` | Node metadata |
| `proposed_values.assessment_status` | nested | `"Untested"` | Node metadata |
| `proposed_values.source_provenance` | nested | `["Phase 03, run 9081e83c, Round 1"]` | Origin metadata |

> ⚠️ **Critical**: Use the **top-level** `evidential_basis` field, NOT
> `proposed_values.evidential_basis`. The top-level version has clean,
> parseable file paths. The `proposed_values` version has a known agent output
> bug causing triply-nested path corruption
> (`branches/X/branches/X/branches/X/evaluations/...`).

**Verified counts for project-004**: 17 statements across 9 decision records.

### 3.2 Method menu files

**Location**: `<project_dir>/ideas/methods/<stable_id>.md`

Each file has YAML frontmatter:

```yaml
stable_id: spectral-graph-coupling
number: 1
version: v1
label: Spectral graph coupling
status: recommended   # recommended | viable | retired
```

**Verified**: 7 method files in project-004.

### 3.3 Run manifests

**Location**: `<project_dir>/.research-hub-control/<project>/runs/<phase>/<run_id>.manifest.json`

Key fields:
- `run_id`, `run_number`, `phase_slug`, `output_root`
- `decision_path` — relative path to the decision record (use this to locate it)
- `method_selection` — **`null` for all project-004 runs** (see fallback below)

> ⚠️ **Fallback for method identity**: Since `method_selection` is null in
> existing data, extract the method `stable_id` from the `output_root` path.
> Method-bound runs have paths matching:
> ```
> branches/<stable_id>/evaluations/run/<NN>    (Phase 03)
> branches/<stable_id>/draft/sections/run/<NN>  (Phase 04)
> ```
> Non-method-bound phases (01, 02, 05) do not have `branches/` in their
> output roots and get no method edges.

---

## 4. Node types

```
Node
├── statement     — a scientific claim, definition, or assessment
├── method        — a method identity (stable_id + version)
├── assumption    — an explicit assumption used by a statement
└── evidence      — a supporting artifact (role report, computation, citation)
```

### 4.1 Statement node

```json
{
  "id": "S-P03-R001-summary-research_lead-001",
  "type": "statement",
  "statement_type": "Mathematical statement",
  "wording": "For the spectral graph coupling mechanism ...",
  "scope": "Finite N ≥ 2, strongly log-concave target distributions ...",
  "logical_status": "conjectured",
  "assessment_status": "Untested",
  "operation": "add",
  "status": "current",
  "origin": {
    "phase": "03-idea-evaluation",
    "run_id": "9081e83c-4264-47a8-8a0a-d7e8eae001ef",
    "round_or_stage": "summary",
    "role": "research_lead"
  }
}
```

### 4.2 Method node

```json
{
  "id": "method:spectral-graph-coupling:v1",
  "type": "method",
  "stable_id": "spectral-graph-coupling",
  "version": "v1",
  "label": "Spectral graph coupling",
  "status": "recommended"
}
```

### 4.3 Assumption node

Assumptions are extracted from `proposed_values.assumptions[]`. Agents do not
assign stable IDs to assumptions, so the system generates synthetic IDs:

```json
{
  "id": "asm:a3f7b2c1",
  "type": "assumption",
  "text": "Strong log-concavity: −∇²log p ⪰ ρI_d for all x with ρ > 0",
  "label": "A3",
  "status": "assumed",
  "first_seen_in": "S-P03-R001-summary-research_lead-001"
}
```

**Synthetic ID derivation**:

```
asm:<short-hash-of-normalized-text>
```

Where the hash is the first 8 hex characters of SHA-256 over normalized text:
1. Lowercase
2. Collapse all whitespace to single spaces
3. Strip leading label patterns (`A3:`, `(A3)`, `(A3)`)
4. Trim

This makes the same assumption re-stated in different runs resolve to the same
node, enabling cross-run queries like "show me every claim that relies on
strong log-concavity."

### 4.4 Evidence node

```json
{
  "id": "evidence:9081e83c:theorist:r01",
  "type": "evidence",
  "text": "Theorist Round 1 proof sketch: branches/.../theorist.md §1.2–1.4",
  "path": "branches/spectral-graph-coupling/evaluations/run/01/round-01/theorist.md",
  "section": "§1.2–1.4",
  "role": "theorist",
  "round": 1,
  "run_id": "9081e83c-4264-47a8-8a0a-d7e8eae001ef"
}
```

Evidence is parsed from the **top-level** `evidential_basis[]` strings. The
parser extracts:
- A file path (longest substring ending in `.md` or `.html`)
- An optional section reference (text matching `§...` or `Section ...`)
- A role hint (text matching `theorist`, `data_scientist`, `research_lead`)
- A round hint (text matching `Round N`)

Entries that cannot be parsed are stored as evidence nodes with `path: null`
and the full text in `text`.

---

## 5. Edge types

```
Edge
├── supersedes            — statement replaces an older version
├── depends_on_assumption — statement relies on an assumption
├── derived_for_method    — statement was developed for a specific method
└── evidence_for          — evidence artifact supports a statement
```

### 5.1 Supersedes

```
parent_statement_id ──supersedes──▶ child_statement_id
```

Directly from the `parent_statement_id` field. When statement B has
`parent_statement_id: "A"`, the edge is `A ──supersedes──▶ B`.

> **Note**: The `parent_statement_id` may reference a statement from an
> earlier phase. For example, Phase 03 statement
> `S-P03-R001-summary-research_lead-001` has parent
> `S-P02-R001-round01-theorist-001` (a Phase 02 statement). The graph
> correctly builds cross-phase edges this way.

### 5.2 Depends-on-assumption

```
statement ──depends_on_assumption──▶ assumption_node
```

Each entry in a statement's `proposed_values.assumptions[]` list becomes an
edge to the extracted assumption node. This is the most valuable edge for
impact analysis.

### 5.3 Derived-for-method

```
statement ──derived_for_method──▶ method_node
```

**Method identity resolution** (in priority order):

1. If `manifest["method_selection"]["stable_id"]` is non-null, use it
   directly (future runs with the method-menu contract).
2. **Fallback**: parse `manifest["output_root"]` for the pattern
   `branches/<stable_id>/`. This handles all existing project-004 data.
3. If neither yields a method ID, the statement gets no method edge
   (Phase 01, 02, 05 statements).

### 5.4 Evidence-for

```
evidence_node ──evidence_for──▶ statement
```

Each parsed entry from `evidential_basis[]` becomes an edge from the evidence
node to the statement.

---

## 6. Serialized format

**File**: `<project_dir>/.research-hub-control/<project_dir>/.artifact-graph.json`

```json
{
  "schema_version": 1,
  "project_dir": "project-004-entangled-langevin-sampling",
  "last_rebuilt_at": "2026-07-28T05:00:00Z",
  "last_rebuilt_from_run": "75cfd941-ad0c-4795-8d32-714c7cea431e",
  "nodes": {
    "S-P03-R001-summary-research_lead-001": { ... },
    "method:spectral-graph-coupling:v1": { ... },
    "asm:a3f7b2c1": { ... },
    "evidence:9081e83c:theorist:r01": { ... }
  },
  "edges": [
    { "from": "S-P02-R001-round01-theorist-001", "to": "S-P03-R001-summary-research_lead-001", "type": "supersedes" },
    { "from": "S-P03-R001-summary-research_lead-001", "to": "asm:a3f7b2c1", "type": "depends_on_assumption" },
    { "from": "S-P03-R001-summary-research_lead-001", "to": "method:spectral-graph-coupling:v1", "type": "derived_for_method" },
    { "from": "evidence:9081e83c:theorist:r01", "to": "S-P03-R001-summary-research_lead-001", "type": "evidence_for" }
  ],
  "staleness": {}
}
```

The `staleness` dict maps statement IDs to staleness records (see §9). It is
**separate** from the phase-level staleness in `project.yaml`.

**Write method**: atomic (temp file + `os.replace`), same pattern as
`_save_unlocked` in `project_state.py`.

---

## 7. Module API

New module: `core/artifact_graph.py`

### 7.1 Build

```python
def build_graph(project_dir: str | Path) -> dict[str, Any]:
    """Rebuild the complete graph from primary sources.

    Reads:
      - All decision records: <project_dir>/phase-summaries/<phase>/*.decision.json
      - Method menu files: <project_dir>/ideas/methods/*.md
      - Run manifests: <control_dir>/runs/<phase>/*.manifest.json

    Returns the in-memory graph dict (nodes + edges + staleness).
    Does NOT write to disk — caller decides whether to persist.
    """
```

Implementation notes:
- Deduplicate decision records by `(phase, run_id)` — the same record may be
  copied to multiple downstream run contexts.
- Skip decision records that fail JSON parsing (log a warning, continue).
- For method identity, use the fallback `output_root` parser when
  `method_selection` is null.

### 7.2 Serialize / Load

```python
GRAPH_SCHEMA_VERSION = 1

def serialize(graph: dict[str, Any], project_dir: str | Path) -> Path:
    """Write the graph to .artifact-graph.json in the control directory.
    Atomic write (temp + rename). Returns the path written.
    """

def load(project_dir: str | Path) -> dict[str, Any]:
    """Load the cached graph, or rebuild if missing or stale.

    Stale = last_rebuilt_from_run does not match the latest finalized run
    in project state. In that case, rebuild automatically.
    """
```

### 7.3 Impact analysis

```python
def impact_set(
    graph: dict[str, Any],
    changed_node_ids: list[str],
) -> dict[str, list[str]]:
    """Compute downstream dependents of the given nodes.

    Returns a dict mapping each changed node to the list of nodes that
    directly or transitively depend on it.

    Traverses edges in reverse direction:
      - supersedes: find consumers of a superseded statement
      - depends_on_assumption: find statements using a changed assumption
      - derived_for_method: find statements bound to a changed method

    Conservative: a statement with no parsed assumptions is included in
    impact sets (flagged "potentially affected"), never silently excluded.
    """
```

### 7.4 Query helpers

```python
def statements_for_method(
    graph, method_stable_id, *, version=None, include_superseded=False
) -> list[dict]:
    """All statements derived for the given method."""

def statements_depending_on_assumption(
    graph, assumption_text_substring
) -> list[dict]:
    """All statements whose assumptions contain the given text."""

def evidence_for_statement(graph, statement_id) -> list[dict]:
    """All evidence nodes linked to this statement."""

def assumption_registry(graph) -> list[dict]:
    """All distinct assumptions, sorted by dependent-statement count descending."""
```

### 7.5 Update hook

```python
def update_after_run(
    project_dir: str | Path,
    run_id: str,
) -> dict[str, Any] | None:
    """Incrementally update the graph after a run is finalized.

    1. Load existing graph (or build from scratch if absent).
    2. Read the run's decision record (from manifest's decision_path).
    3. For each scientific_record_changes entry:
       a. Create or update the statement node.
       b. Extract assumptions → create/merge assumption nodes.
       c. Extract evidence from top-level evidential_basis → evidence nodes.
       d. Resolve method identity (manifest method_selection or output_root fallback).
    4. Recompute staleness for any superseded statements.
    5. Serialize and persist.
    6. Return the updated graph, or None on failure.

    All exceptions are caught by the caller (finalize_run_submission),
    which wraps this call in try/except. This function should not raise.
    """
```

---

## 8. Assumption extraction algorithm

```
Input: assumptions[] (list of free-text strings from proposed_values)

For each assumption string:
  1. EXTRACT LABEL: if text starts with pattern like "A3:", "(A3)", "(A3)"
     → label = "A3", remainder = text after label
     Otherwise → label = None (assigned sequentially later: A1, A2, ...)

  2. NORMALIZE for hashing:
     - Lowercase
     - Collapse all whitespace to single spaces
     - Strip label patterns (A3:, (A3), etc.)
     - Strip trailing/leading punctuation
     - Strip Unicode math symbols (ρ, ⪰, etc.) — normalize to ASCII equivalents

  3. HASH: SHA-256 of normalized text → first 8 hex chars
     → node_id = "asm:<hash>"

  4. MATCH: if node_id already exists in graph, this assumption is shared.
     Update first_seen_in if this is an earlier run.
     Otherwise create new assumption node.

  5. ASSIGN DISPLAY LABEL: if no label was extracted, assign sequential
     A1, A2, ... per statement. If label was extracted, use it.
```

**What was dropped from the original draft**: the Jaccard token-similarity
grouping with `related_to` edges. With 6 assumptions per statement and ~17
statements, exact-hash matching is sufficient. Near-duplicate detection adds
implementation complexity for marginal benefit and belongs in Level 2.

**Known limitation**: Math notation varies across runs
(`−∇²log p ⪰ ρI_d` vs `-∇² log p(x) ≥ ρ I_d`). The normalizer strips Unicode
math symbols, but semantic equivalence (⪰ vs ≥) may cause under-merging. This
is acceptable for Level 1: false positives (over-flagging) are less costly
than false negatives (missed dependencies).

---

## 9. Staleness computation

### Design decision: graph staleness is self-contained

The graph maintains its OWN staleness dict inside `.artifact-graph.json`. It
does **not** modify `project.yaml` and does **not** interact with the existing
`_stale_changed_method_descendants_unlocked` phase-level system. The two
systems coexist:

- **Phase-level staleness** (`project.yaml`): coarse, used by prerequisite
  checks and launch gates. Unchanged.
- **Graph-level staleness** (`.artifact-graph.json`): fine-grained, used by
  the UI for impact display and researcher queries.

### 9.1 When a statement is superseded

When a new run produces a statement that supersedes an existing one
(via `parent_statement_id`):

1. The old statement's node status changes to `"superseded"`.
2. `impact_set` computes all downstream dependents of the old statement.
3. Each dependent is added to the graph's staleness dict:

```json
"S-P04-R001-summary-research_lead-001": {
  "reason": "depends on superseded statement S-P03-R001-summary-research_lead-001",
  "flagged_at": "2026-07-28T05:00:00Z",
  "flagged_by_run": "75cfd941-...",
  "supersession_chain": ["S-P03-R001-summary-research_lead-001", "S-P03-R002-summary-research_lead-001"]
}
```

### 9.2 When a method definition changes

When Phase 02 publishes a new method menu that revises a method's definition:

1. The old method version node is marked superseded by the new version.
2. All statements with `derived_for_method` edges to the old version are
   flagged as potentially stale.
3. Cascade: statements that depend on flagged statements (via supersedes
   chain) are also flagged.

### 9.3 Resolution

A statement's staleness is resolved when:
- A new run produces a revised statement that explicitly supersedes it, OR
- The user marks it "confirmed still valid" (manual acknowledgement stored
  in the graph's staleness dict — a future UI feature).

---

## 10. Integration into the hub

### 10.1 Update hook in `finalize_run_submission`

**File**: `core/project_state.py`, function `finalize_run_submission` (line ~5454)

Add the graph update call at the **end** of the function, after all existing
state changes are saved, wrapped in try/except:

```python
# At the end of finalize_run_submission, after _save_unlocked(project_dir, data):
try:
    from . import artifact_graph
    artifact_graph.update_after_run(project_dir, run["run_id"])
except Exception:
    log.warning("artifact graph update failed", exc_info=True)
```

The hook goes after every `return True` path in the function (there are
multiple early returns for different outcomes: awaiting_review, superseded,
failed, published). The simplest approach: add a helper that wraps the call
and invoke it before each return, OR refactor the function to have a single
exit point.

> **Implementation note**: `finalize_run_submission` currently has multiple
> `return True` / `return False` exit points. Rather than scattering the hook
> at each one, consider a `_post_finalization` helper called at each exit, or
> a try/finally block. The hook should fire only on successful finalization
> (status became `awaiting_review`, `approved`, or `published`), not on
> early returns where the run was already in the wrong state.

### 10.2 What does NOT change

- `project.yaml` schema — unchanged
- `_stale_changed_method_descendants_unlocked` — unchanged
- Agent prompts, playbooks, phase configs — unchanged
- Decision record schema — unchanged
- Run manifest schema — unchanged

### 10.3 Web UI integration (later phase, after core works)

A collapsible `<details>` section in the phase panel showing:

- **Statements for this method branch** — list with type, status, origin
- **Stale statements** — flagged with reason and originating run
- **Assumption registry** — top assumptions by dependency count
- **Evidence links** — supporting role reports with file paths

This follows the existing five-element information budget: the graph section
lives inside a `<details>` toggle, not as a new top-level element.

### 10.4 Impact preview on approval (future)

When a user is about to approve a run that supersedes statements, show an
impact preview:

```
This approval will supersede 2 statements:
  S-P03-R001-summary-research_lead-001 (spectral gap bound)
    → 2 downstream statements may be affected
  S-P03-R001-summary-research_lead-002 (originality claim)
    → No downstream dependents
```

---

## 11. Evidence path parser

Evidence strings from `evidential_basis[]` are free text. The parser:

```
Input: "Theorist Round 1 proof sketch: branches/.../theorist.md §1.2–1.4"

  1. EXTRACT PATH: find the longest substring ending in .md or .html
     → "branches/spectral-graph-coupling/evaluations/run/01/round-01/theorist.md"

  2. EXTRACT SECTION: find text matching §\S+ or "Section \S+"
     → "§1.2–1.4"

  3. EXTRACT ROLE: match against known roles
     (theorist, data_scientist, research_lead, paper_reviewer)
     → "theorist"

  4. EXTRACT ROUND: match "Round \d+"
     → 1

  5. EVIDENCE NODE ID: "evidence:<run_id_prefix>:<role>:r<round>"
     → "evidence:9081e83c:theorist:r01"

  6. If no path found: store as evidence with path=null, text=full string.
```

---

## 12. Testing strategy

### 12.1 Unit tests (`tests/test_artifact_graph.py`)

| Test | Description |
|---|---|
| `test_build_from_synthetic_records` | Construct 3 decision records with known statements, assumptions, parents. Verify nodes + edges. |
| `test_assumption_deduplication` | Two statements with identical assumption text → same assumption node. |
| `test_assumption_label_extraction` | `"A3: strong log-concavity"` → label `A3`, normalized text without label. |
| `test_evidence_parsing` | Parse a real evidence string → correct path, section, role, round. |
| `test_evidence_top_level_not_proposed_values` | Verify the builder reads top-level `evidential_basis`, not `proposed_values.evidential_basis`. |
| `test_method_fallback_from_output_root` | Manifest with `method_selection: null` but `output_root` containing `branches/<stable_id>/` → method edge created. |
| `test_impact_set_supersedes` | Supersede a statement → all downstream dependents returned. |
| `test_impact_set_conservative` | Statement with no assumptions → included in impact sets, not excluded. |
| `test_serialize_load_roundtrip` | build → serialize → load → compare. |
| `test_incremental_update` | Build from 2 runs, add 3rd run's record, verify graph correct. |
| `test_corrupt_record_graceful` | One corrupt decision record → graph built from remaining records, no crash. |
| `test_staleness_on_supersession` | New statement supersedes old → old marked superseded, dependents flagged stale. |

### 12.2 Integration test with real data

```python
def test_build_project_004():
    """Build the graph from project-004's actual decision records."""
    graph = artifact_graph.build_graph(PROJECT_004_DIR)
    
    # Verify expected counts
    statements = [n for n in graph["nodes"].values() if n["type"] == "statement"]
    assert len(statements) == 17
    
    # Verify cross-phase supersedes edge
    # S-P03-R001-summary-research_lead-001 → parent S-P02-R001-round01-theorist-001
    edge = find_edge(graph, "S-P02-R001-round01-theorist-001",
                     "S-P03-R001-summary-research_lead-001", "supersedes")
    assert edge is not None
    
    # Verify method edge from output_root fallback
    edge = find_edge(graph, "S-P03-R001-summary-research_lead-001",
                     "method:spectral-graph-coupling:v1", "derived_for_method")
    assert edge is not None
    
    # Verify assumption query
    results = artifact_graph.statements_depending_on_assumption(
        graph, "log-concavity"
    )
    assert len(results) >= 1
```

### 12.3 Hook integration test

```python
def test_finalize_run_updates_graph(monkeypatch, tmp_project):
    """Verify that finalize_run_submission triggers graph update."""
    # Set up a project with a finalized run
    # Call finalize_run_submission
    # Verify .artifact-graph.json exists and contains the run's statements
```

---

## 13. Migration and backward compatibility

### 13.1 Initial build

On first access (via `load()`), if no `.artifact-graph.json` exists, the graph
is built from all existing decision records, method menu, and manifests.
For project-004 (9 records, 17 statements), this takes well under a second.

### 13.2 Schema versioning

The graph file has `schema_version: 1`. Future changes to the node/edge model
bump the version and trigger a full rebuild from primary sources.

### 13.3 No changes to sealed data

- `project.yaml` — unchanged
- Decision records — unchanged
- Run manifests — unchanged
- Agent prompts — unchanged

The graph is purely additive: a new derived file
(`.artifact-graph.json`) and a new module (`core/artifact_graph.py`).

---

## 14. Implementation order

| Step | Component | Description | Depends on |
|---|---|---|---|
| 1 | `core/artifact_graph.py` — data model | Node/edge dataclasses, node ID generation | — |
| 2 | Assumption extraction | Normalize, hash, label, deduplicate | Step 1 |
| 3 | Evidence path parser | Parse `evidential_basis[]` strings | Step 1 |
| 4 | Method identity resolver | `method_selection` → `output_root` fallback | Step 1 |
| 5 | `build_graph` | Read all decision records + method menu + manifests | Steps 2–4 |
| 6 | `serialize` / `load` | Atomic write, stale-check-and-rebuild | Step 5 |
| 7 | `impact_set` + query helpers | BFS traversal, query functions | Step 5 |
| 8 | Staleness computation | Supersession + method-change flagging | Step 7 |
| 9 | `update_after_run` | Incremental update entry point | Steps 5–8 |
| 10 | `tests/test_artifact_graph.py` | All unit + integration tests | Steps 1–9 |
| 11 | Hook in `finalize_run_submission` | try/except wrapped call | Step 9 |
| 12 | Verify on real project-004 | Build graph, validate 17 statements, check edges | Step 11 |

**Steps 1–10** deliver the core module with full test coverage and no hub
integration. **Step 11** wires it in. **Step 12** validates against real data.

**Future steps** (separate PRs, after core is validated):
- 13. Web UI: collapsible graph section in phase panel
- 14. Impact preview on approval
- 15. Level 2: explicit `depends_on` field in agent decision records

---

## 15. Future: Level 2 (explicit agent-declared dependencies)

Level 2 makes the graph precise by having agents declare dependencies
explicitly in their decision records:

```json
{
  "statement_id": "S-P04-R002-summary-research_lead-001",
  "operation": "add",
  "depends_on": [
    "S-P03-R001-summary-research_lead-001",
    "S-P03-R001-summary-research_lead-002"
  ],
  "proposed_values": {
    "assumptions": [
      {
        "id": "A3",
        "text": "Strong log-concavity: −∇²log p ⪰ ρI_d",
        "status": "inherited",
        "inherited_from": "S-P03-R001-summary-research_lead-001"
      }
    ]
  }
}
```

Level 2 is backward-compatible with Level 1:
- Records with the new fields use them directly.
- Records without the new fields fall back to Level 1 extraction.
- The graph handles both transparently.

Level 2 requires updates to:
- Decision record schema (add `depends_on`, structured assumptions)
- Agent prompts (team norms, phase configs, lead instructions)
- `validate_decision_record` in `project_state.py`
