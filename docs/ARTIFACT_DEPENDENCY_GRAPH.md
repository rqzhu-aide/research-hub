# Artifact Dependency Graph — Implementation Design

> Status: Design proposal, not yet implemented.
> Date: July 2026
> Scope: Level 1 (derived graph from existing data). Level 2 (explicit
> agent-declared dependencies) is described as a future extension.

## 1. Motivation

When a method definition, a proof assumption, or an empirical result changes,
the researcher needs to know **exactly which downstream claims, experiments,
and draft sections are affected** — not just "Phase 03 is stale."

The current system has phase-level staleness marking: when a Phase 02 method
changes, `mark_method_dependents_stale` marks the entire Phase 03 and Phase 04
branches as stale. This is correct but coarse. A revised method definition may
invalidate one theorem while leaving five other claims unaffected. The
artifact dependency graph replaces phase-level staleness with **claim-level
impact analysis**.

The graph also makes the project's scientific record **queryable**: "show me
every claim that relies on the strong log-concavity assumption" or "what
evidence supports the spectral gap bound?" become lookups, not manual searches
through run summaries.

## 2. Design principles

1. **Derived, not primary.** The graph is rebuilt from existing primary
   sources (decision records, method menu, run manifests). It is never a source
   of truth that agents write to directly. If lost, it can be fully
   reconstructed.

2. **Updated after each run.** The graph is incrementally rebuilt inside
   `finalize_run_submission`, after the decision record is sealed. No new user
   action is required.

3. **Level 1 requires no agent prompt changes.** The graph is assembled from
   data that decision records already contain: `statement_id`,
   `parent_statement_id`, `assumptions[]`, `evidential_basis[]`, and the run
   manifest's `method_selection`.

4. **Conservative impact analysis.** When the system cannot determine whether
   a statement depends on a changed node, it flags it as "potentially
   affected" rather than silently ignoring it. The researcher confirms.

5. **Append-only history.** Like decision records, the graph preserves
   superseded nodes. A statement that was withdrawn or revised remains visible
   with its successor link, so the full reasoning chain is traceable.

## 3. What we already have

The graph's seed already exists in the structured data produced by each run's
decision record. Project-004 currently has 17 statements across 8 runs, each
carrying:

| Field | Example | Graph use |
|---|---|---|
| `statement_id` | `S-P03-R001-summary-research_lead-001` | Node identity |
| `parent_statement_id` | `S-P02-R001-round01-theorist-001` | Supersedes edge |
| `operation` | `add`, `revise`, `withdraw` | Node lifecycle |
| `proposed_values.assumptions[]` | `"Strong log-concavity: −∇²log p ⪰ ρI_d"` | Assumption nodes |
| `proposed_values.evidential_basis[]` | `"theorist.md §1.2-1.4"` | Evidence edges |
| `proposed_values.source_provenance[]` | `"Phase 03, run 9081e83c, Round 1"` | Origin metadata |
| `change_origin.phase` | `"03-idea-evaluation"` | Phase context |
| `change_origin.run` | `"9081e83c-..."` | Run link |

Method menu entries provide:

| Field | Example | Graph use |
|---|---|---|
| `stable_id` | `spectral-graph-coupling` | Method node identity |
| `version` | `v1` | Method version node |
| `sha256` | `beaaa4da...` | Content fingerprint |
| `status` | `recommended`, `viable`, `retired` | Lifecycle |

Run manifests provide:

| Field | Graph use |
|---|---|
| `method_selection.stable_id` + `version` | Links statements to method branch |
| `method_selection.definition_sha256` | Verifies method identity |

## 4. Node types

```
Node
├── statement     — a scientific claim, definition, or assessment
├── method        — a method identity (stable_id)
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
  "uncertainty": ["The rate bound is a proof sketch ..."],
  "operation": "add",
  "status": "current",
  "origin": {
    "phase": "03-idea-evaluation",
    "run_id": "9081e83c-4264-47a8-8a0a-d7e8eae001ef",
    "round_or_stage": "summary",
    "role": "research_lead"
  },
  "approved_run_id": "9081e83c-4264-47a8-8a0a-d7e8eae001ef",
  "superseded_by": null,
  "superseded_at": null
}
```

### 4.2 Method node

```json
{
  "id": "method:spectral-graph-coupling",
  "type": "method",
  "stable_id": "spectral-graph-coupling",
  "label": "Spectral graph coupling",
  "registry_number": 1,
  "current_version": "v1",
  "status": "recommended"
}
```

### 4.3 Assumption node

Assumptions are extracted from each statement's `assumptions[]` list. Since
agents do not currently assign stable IDs to assumptions, the system generates
synthetic IDs from the parent statement and a hash of the assumption text:

```json
{
  "id": "asm:S-P03-R001-001:a3",
  "type": "assumption",
  "text": "Strong log-concavity: −∇²log p ⪰ ρI_d for all x with ρ > 0",
  "label": "A3",
  "status": "assumed",
  "first_seen_in": "S-P03-R001-summary-research_lead-001",
  "source_statement_id": "S-P03-R001-summary-research_lead-001"
}
```

The synthetic ID is derived as:
```
asm:<statement-id-prefix>:<short-hash-of-normalized-text>
```

Where the hash uses the first 8 hex characters of SHA-256 over the normalized
assumption text (lowercased, whitespace-collapsed, punctuation-stripped). This
makes the same assumption re-stated in different runs resolve to the same node,
enabling cross-run dependency queries.

### 4.4 Evidence node

```json
{
  "id": "evidence:9081e83c:theorist:r01:s1.2",
  "type": "evidence",
  "text": "Theorist Round 1 proof sketch: §1.2-1.4",
  "path": "branches/spectral-graph-coupling/evaluations/run/01/round-01/theorist.md",
  "role": "theorist",
  "round": 1,
  "run_id": "9081e83c-4264-47a8-8a0a-d7e8eae001ef"
}
```

Evidence paths are parsed from the `evidential_basis[]` strings in decision
records. The parser extracts a file path and optional section reference. Paths
that cannot be parsed are stored as raw text with no file link.

## 5. Edge types

```
Edge
├── supersedes           — statement replaces an older version
├── depends_on_assumption — statement relies on an assumption
├── derived_for_method   — statement was developed for a specific method
├── evidence_for         — evidence artifact supports a statement
└── method_version       — method version belongs to a method lineage
```

### 5.1 Supersedes

```
parent_statement_id → child_statement_id
```

Directly from the `parent_statement_id` field. When statement B has
`parent_statement_id: "A"`, the edge is `A ──supersedes──▶ B`.

Direction rationale: traversal for impact analysis goes from old to new
("what replaced this statement?"), while provenance goes from new to old
("what was this statement based on?").

### 5.2 Depends-on-assumption

```
statement ──depends_on──▶ assumption
```

Each entry in a statement's `assumptions[]` list becomes an edge to the
extracted assumption node. This is the most valuable edge for impact analysis:
when an assumption is challenged or revised, all statements that depend on it
are flagged.

### 5.3 Derived-for-method

```
statement ──derived_for──▶ method:version
```

Inferred from the run manifest's `method_selection`. All statements produced
by a method-bound run (Phase 03 or 04) are linked to the selected method and
version. Statements from non-method-bound phases (Phase 01, 02, 05) have no
method edge.

### 5.4 Evidence-for

```
evidence ──supports──▶ statement
```

Each entry in a statement's `evidential_basis[]` list becomes an edge from the
extracted evidence node to the statement.

### 5.5 Method-version

```
method:spectral-graph-coupling:v1 ──version_of──▶ method:spectral-graph-coupling
```

Links a specific version to the method lineage. When a method is revised (v1 →
v2), the new version node is added and the old one retains its edges.

## 6. Serialized format

The graph is stored as a single JSON file in the project control directory:

```
.research-hub-control/<project-dir>/.artifact-graph.json
```

```json
{
  "schema_version": 1,
  "project_dir": "project-004-entangled-langevin-sampling",
  "last_rebuilt_at": "2026-07-27T22:00:00Z",
  "last_rebuilt_from_run": "9081e83c-...",
  "nodes": {
    "S-P03-R001-summary-research_lead-001": { ... },
    "method:spectral-graph-coupling": { ... },
    "asm:S-P03-R001-001:a3": { ... },
    "evidence:9081e83c:theorist:r01:s1.2": { ... }
  },
  "edges": [
    {
      "from": "S-P02-R001-round01-theorist-001",
      "to": "S-P03-R001-summary-research_lead-001",
      "type": "supersedes"
    },
    {
      "from": "S-P03-R001-summary-research_lead-001",
      "to": "asm:S-P03-R001-001:a3",
      "type": "depends_on_assumption"
    },
    {
      "from": "S-P03-R001-summary-research_lead-001",
      "to": "method:spectral-graph-coupling:v1",
      "type": "derived_for_method"
    },
    {
      "from": "evidence:9081e83c:theorist:r01:s1.2",
      "to": "S-P03-R001-summary-research_lead-001",
      "type": "evidence_for"
    }
  ],
  "staleness": {
    "S-P04-R001-summary-research_lead-001": {
      "reason": "depends on superseded statement S-P03-R001-summary-research_lead-001",
      "flagged_at": "2026-07-27T22:00:00Z",
      "flagged_by_run": "121f087e-..."
    }
  }
}
```

## 7. Module API

New module: `core/artifact_graph.py`

### 7.1 Build

```python
def build_graph(project_dir: str | Path) -> dict[str, Any]:
    """Rebuild the complete graph from primary sources.

    Reads all decision records, the method menu, and run manifests.
    Returns the in-memory graph dict (nodes + edges + staleness).
    Does NOT write to disk — caller decides whether to persist.
    """
```

### 7.2 Serialize

```python
GRAPH_SCHEMA_VERSION = 1

def serialize(graph: dict[str, Any], project_dir: str | Path) -> Path:
    """Write the graph to .artifact-graph.json in the control directory.

    Returns the path written. Atomic write (temp + rename).
    """
```

### 7.3 Load

```python
def load(project_dir: str | Path) -> dict[str, Any]:
    """Load the cached graph, or rebuild if missing or stale.

    Stale = last_rebuilt_from_run does not match the latest finalized run
    in project state. In that case, rebuild automatically.
    """
```

### 7.4 Impact analysis

```python
def impact_set(
    graph: dict[str, Any],
    changed_node_ids: list[str],
) -> dict[str, list[str]]:
    """Compute downstream dependents of the given nodes.

    Returns a dict mapping each changed node to the list of nodes that
    directly or transitively depend on it. Traverses:
      - supersedes (reverse direction: new → old consumers)
      - depends_on_assumption (reverse: assumption → statements)
      - derived_for_method (reverse: method → statements)
      - evidence_for (reverse: statement → evidence, though evidence
        staleness is informational only)

    Conservative: if a node has unknown dependency status (e.g., a
    statement with no parsed assumptions), it is included in the impact
    set rather than excluded.
    """
```

### 7.5 Query helpers

```python
def statements_for_method(
    graph: dict[str, Any],
    method_stable_id: str,
    *,
    version: str | None = None,
    include_superseded: bool = False,
) -> list[dict[str, Any]]:
    """Return all statements derived for the given method."""

def statements_depending_on_assumption(
    graph: dict[str, Any],
    assumption_text_substring: str,
) -> list[dict[str, Any]]:
    """Find all statements whose assumptions contain the given text."""

def evidence_for_statement(
    graph: dict[str, Any],
    statement_id: str,
) -> list[dict[str, Any]]:
    """Return all evidence nodes linked to this statement."""

def assumption_registry(
    graph: dict[str, Any],
) -> list[dict[str, Any]]:
    """Return all distinct assumptions across the project, with their
    dependent statement counts. Sorted by dependency count descending."""
```

### 7.6 Update hook

```python
def update_after_run(
    project_dir: str | Path,
    run_id: str,
    decision_record: dict[str, Any],
) -> dict[str, Any]:
    """Incrementally update the graph after a run is finalized.

    1. Load existing graph (or build from scratch if absent).
    2. For each entry in decision_record['scientific_record_changes']:
       a. Create or update the statement node.
       b. If operation is 'revise' or 'withdraw', mark the predecessor
          as superseded.
       c. Extract assumptions and create/merge assumption nodes.
       d. Extract evidence references and create evidence nodes.
       e. Link to the method from the run manifest.
    3. Recompute staleness:
       a. For each superseded statement, compute impact_set and flag
          downstream nodes as potentially stale.
       b. If the run's method selection differs from prior runs on the
          same branch, flag statements from the old method version.
    4. Serialize and persist.
    5. Return the updated graph.
    """
```

## 8. Assumption extraction

Assumptions in current decision records are free-text strings:

```json
"assumptions": [
  "D_N constant in X (L_G, K constant matrices independent of particle positions)",
  "Π_N = p^⊗N product measure (i.i.d. target across particles)",
  "Strong log-concavity: −∇²log p ⪰ ρI_d for all x with ρ > 0",
  "Standard domain conditions for Bakry-Émery calculus on R^{Nd}",
  "CD(ρ_eff, ∞) curvature-dimension condition implies spectral gap bound",
  "Graph G is connected (Fiedler eigenvalue σ₂(L_G) > 0)"
]
```

### Extraction algorithm

1. **Normalize**: lowercase, collapse whitespace, strip parenthetical
   qualifiers (text in parentheses is preserved as a `qualifier` field but
   not hashed).

2. **Hash**: SHA-256 of normalized text, first 8 hex characters.

3. **Label assignment**: if the assumption text starts with a label pattern
   like `A3:`, `(A3)`, or `(A3)`, use it. Otherwise, assign a sequential
   label `A1`, `A2`, ... per statement.

4. **Cross-run matching**: two assumptions from different statements with the
   same normalized hash are the same node. This enables:

   - Statement S1 (Phase 03 run 1) assumes "strong log-concavity −∇²log p ⪰ ρI_d"
   - Statement S2 (Phase 03 run 3) assumes "strong log-concavity −∇²log p ⪰ ρI_d"
   - Both link to the same assumption node → querying that assumption returns
     both statements.

5. **Heuristic grouping**: if two assumptions have a Jaccard token similarity
   above 0.7 but different hashes, they are stored as separate nodes but linked
   with a `related_to` edge. This catches near-duplicates like
   "strong log-concavity" vs. "strong log-concavity with ρ > 0".

### Limitations

- The extraction is heuristic. Some assumptions will be under- or
  over-merged. This is acceptable for Level 1 because the graph is advisory:
  the researcher confirms impact, and false positives (flagging something
  unnecessarily) are less costly than false negatives (missing a dependency).
- Level 2 (future) replaces this with explicit assumption IDs assigned by
  agents.

## 9. Method-reference detection

Statements produced by method-bound runs (Phase 03, 04) are linked to the
method selected in that run's manifest:

```python
manifest = read_manifest(project_dir, phase_slug, run_id)
method_sel = manifest.get("method_selection")
if method_sel and method_sel.get("stable_id"):
    method_node_id = f"method:{method_sel['stable_id']}:v{method_sel['version']}"
    # Link all statements from this run to this method node
```

For statements that mention method stable_ids in their wording (e.g., a Phase
02 statement describing a method), a secondary text-scan pass detects
references and adds `references_method` edges. This catches statements not
produced by method-bound runs but that discuss specific methods.

## 10. Update flow

```
Run lifecycle:
                                              ┌──────────────────────┐
  User launches run                           │  Run executes        │
  ─────────────────────►  ┌──────────►────────┤  (agents produce     │
                          │                   │   role reports)      │
                          │                   └──────────└───────────┘
                          │                              │
                          │                              ▼
                          │                   ┌──────────────────────┐
                          │                   │  Agent submits       │
                          │                   │  decision record     │
                          │                   └──────────└───────────┘
                          │                              │
                          │                              ▼
                          │                   ┌──────────────────────┐
                          │                   │  stage_run_submission│
                          │                   │  (seal artifacts)    │
                          │                   └──────────└───────────┘
                          │                              │
                          │                              ▼
                          │                   ┌──────────────────────┐
                          │                   │  finalize_run_       │
                          │                   │  submission()        │
                          │                   └──────────└───────────┘
                          │                              │
                          │           ┌──────────────────┼──────────────────┐
                          │           ▼                  ▼                  ▼
                          │  publish_method_menu   approve_run      ┌──────────────┐
                          │  (if Phase 02)         (if user         │artifact_graph│
                          │                        approves)        │.update_after │
                          │                                         │_run()        │
                          │                                         └──────┬───────┘
                          │                                                │
                          │                                                ▼
                          │                                    ┌──────────────────┐
                          │                                    │ .artifact-graph  │
                          │                                    │ .json rewritten  │
                          │                                    └──────────────────┘
                          │                                                │
                          └────────────────────────────────────────────────┘
```

The update hook is called inside `finalize_run_submission` in
`core/project_state.py`, after the decision record is sealed but before
control returns to the web layer. This ensures the graph is always consistent
with the sealed state.

If the graph build fails (e.g., a corrupt decision record), the error is
logged but does not block the run finalization. The graph will be rebuilt on
the next successful run or on explicit `load()` (which triggers a rebuild if
the cached graph is stale).

## 11. Integration points

### 11.1 `core/project_state.py`

Add a call to `artifact_graph.update_after_run` at the end of
`finalize_run_submission`:

```python
def finalize_run_submission(project_dir, phase_slug, run_ref, ...):
    ...
    # Existing sealing logic ...
    
    # Update artifact graph
    try:
        from . import artifact_graph
        decision_record = _read_decision_record_file(...)
        artifact_graph.update_after_run(
            project_dir, run["run_id"], decision_record
        )
    except Exception:
        logging.warning("artifact graph update failed", exc_info=True)
```

The `try/except` ensures graph failures never block run finalization.

### 11.2 Replace coarse staleness with graph-aware staleness

The existing `mark_method_dependents_stale` marks entire phases. The graph
enables finer-grained staleness:

1. When a method definition changes (Phase 02 rerun), compute the impact set
   from the graph.
2. Flag individual statements as stale, not entire phases.
3. The phase-level `stale` flag is set to `True` only if **all** statements
   in that phase/method-branch are stale. Otherwise, a new `partially_stale`
   field lists the specific affected statement IDs.

This is backward-compatible: existing code that checks `phase["stale"]`
continues to work. The new `partially_stale` field adds granularity.

### 11.3 `core/web_phase_data.py`

Add graph data to the phase panel:

```python
def prepare_phase_data(project_dir, phase_slug, ...):
    ...
    # Existing data preparation ...
    
    # Add artifact graph context
    try:
        from . import artifact_graph
        graph = artifact_graph.load(project_dir)
        phase_data["artifact_graph"] = {
            "statements": artifact_graph.statements_for_method(
                graph, selected_method_id, version=selected_method_version
            ),
            "stale_statements": [...],
            "assumption_summary": artifact_graph.assumption_registry(graph)[:10],
        }
    except Exception:
        phase_data["artifact_graph"] = None
```

### 11.4 `templates/_tab_phase.html`

A collapsible section in the phase panel showing:

- **Statements for this method branch** — list with type, status, and origin
- **Stale statements** — flagged with reason and originating run
- **Assumption registry** — top assumptions by dependency count, clickable to
  show dependent statements
- **Evidence links** — for each statement, the supporting role reports with
  file paths

### 11.5 Impact preview on approval

When a user is about to approve a run that supersedes statements, show an
impact preview:

```
This approval will supersede 2 statements:
  S-P03-R001-summary-research_lead-001 (spectral gap bound)
    → 2 downstream statements may be affected
    → S-P04-R001-summary-research_lead-001 (Phase 04 draft reference)
    → S-P03-R002-summary-research_lead-003 (Phase 03 run 2 extension)
  S-P03-R001-summary-research_lead-002 (originality claim)
    → No downstream dependents
```

## 12. Staleness computation

### 12.1 When a statement is superseded

```python
# In update_after_run, after processing all new statements:
for old_id, new_id in supersession_pairs:
    impacted = impact_set(graph, [old_id])
    for node_id in impacted.get(old_id, []):
        if node not in newly_added:  # don't flag the new statements
            graph["staleness"][node_id] = {
                "reason": f"depends on superseded statement {old_id}",
                "flagged_at": timestamp,
                "flagged_by_run": run_id,
                "supersession_chain": [old_id, new_id],
            }
```

### 12.2 When a method definition changes

When Phase 02 publishes a new method menu that revises a method's definition:

1. The old method version node (`method:spectral-graph-coupling:v1`) is marked
   superseded by the new version (`method:spectral-graph-coupling:v2`).
2. All statements with `derived_for_method` edges to the old version are
   flagged as potentially stale:

```python
for node_id, node in graph["nodes"].items():
    if node["type"] != "statement":
        continue
    method_edges = [e for e in graph["edges"]
                    if e["from"] == node_id
                    and e["type"] == "derived_for_method"
                    and e["to"] == old_version_id]
    if method_edges:
        graph["staleness"][node_id] = {
            "reason": f"method {stable_id} definition revised (v{old} → v{new})",
            "flagged_at": timestamp,
            "flagged_by_run": run_id,
        }
```

3. Cascade: statements that depend on flagged statements (via supersedes
   chain) are also flagged.

### 12.3 Resolution

A statement's staleness is resolved when:
- A new run produces a revised statement that explicitly supersedes it, OR
- The user marks it as "confirmed still valid" in the UI (a manual
  acknowledgement stored in the graph).

## 13. Migration and backward compatibility

### 13.1 Initial build

On first access (via `load()`), if no `.artifact-graph.json` exists, the
graph is built from all existing decision records, method menu, and manifests.
This is a one-time cost proportional to the number of runs in the project.
For project-004 (8 runs, 17 statements), this takes well under a second.

### 13.2 Schema versioning

The graph file has `schema_version: 1`. Future changes to the node/edge model
bump the version and trigger a full rebuild from primary sources.

### 13.3 Coexistence with existing staleness

The existing `phase["stale"]` / `phase["stale_reason"]` / `phase["stale_by_run"]`
fields remain. The graph adds a parallel, finer-grained staleness layer. The
two systems coexist:

- Phase-level staleness: coarse, used by prerequisite checks and launch gates.
- Graph-level staleness: fine, used by the UI for impact display and
  context assembly.

A phase is marked stale at the phase level only when the majority of its
statements are stale at the graph level, or when the method identity itself
is uncertain.

### 13.4 No changes to agent prompts

Level 1 requires no changes to any agent prompt, playbook, phase config, or
team norm. The graph is derived entirely from the structured data that agents
already produce in their decision records.

## 14. Testing strategy

### 14.1 Unit tests (`tests/test_artifact_graph.py`)

- **Build**: construct a project with multiple decision records and verify the
  graph has the expected nodes and edges.
- **Assumption extraction**: verify that identical assumptions in different
  statements resolve to the same node; near-duplicates get `related_to` edges.
- **Impact set**: supersede a statement and verify all downstream dependents
  are returned.
- **Method staleness**: revise a method definition and verify only affected
  statements are flagged.
- **Serialize/load round-trip**: build → serialize → load → compare.
- **Incremental update**: build from 2 runs, then add a 3rd run's decision
  record, verify the graph is correct.
- **Conservative behavior**: a statement with no parsed assumptions is
  included in impact sets, not excluded.
- **Graceful failure**: corrupt decision record does not crash the build;
  the graph is built from the remaining records.

### 14.2 Integration test

- Build the graph for a synthetic project that mirrors project-004's structure
  (Phase 01 → 02 → 03 → 04, with method branches and supersession chains).
- Verify that revising a Phase 02 method flags the correct Phase 03/04
  statements.

### 14.3 Backward compatibility test

- Load project-004's actual decision records.
- Verify the graph builds without errors.
- Verify impact analysis produces sensible results for known supersessions.

## 15. Future: Level 2 (explicit agent-declared dependencies)

Level 2 makes the graph precise by having agents declare dependencies
explicitly in their decision records:

### 15.1 New fields in scientific_record_changes

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
    ],
    "evidential_basis": [
      {
        "path": "branches/spectral-graph-coupling/draft/sections/run/02/round-01/data_scientist.md",
        "sha256": "abc123...",
        "role": "data_scientist",
        "section": "§2.1"
      }
    ]
  }
}
```

### 15.2 Benefits over Level 1

- **Precise dependencies**: `depends_on` is an explicit list of statement IDs,
  not inferred from text or run context.
- **Assumption inheritance**: an assumption can be declared as inherited from
  a specific prior statement, so the chain is exact.
- **Verifiable evidence**: evidence links include SHA-256 checksums for
  machine verification.

### 15.3 Migration path

Level 2 is backward-compatible with Level 1:
- Decision records with the new fields use them directly.
- Decision records without the new fields fall back to Level 1 extraction.
- The graph handles both transparently.

Level 2 requires updates to:
- Decision record schema (v3 → v4, adding `depends_on` and structured
  assumptions/evidence)
- Agent prompts (team norms, phase configs, lead instructions)
- `validate_decision_record` in `project_state.py`

## 16. Implementation order

| Step | Component | Estimated effort |
|---|---|---|
| 1 | `core/artifact_graph.py` — node/edge data model, `build_graph` | Core module |
| 2 | Assumption extraction + cross-run matching | Within step 1 |
| 3 | `impact_set` + staleness computation | Within step 1 |
| 4 | `update_after_run` + hook in `finalize_run_submission` | Integration |
| 5 | `serialize` / `load` with atomic write | Within step 1 |
| 6 | `tests/test_artifact_graph.py` | Testing |
| 7 | `web_phase_data.py` — add graph data to phase panel | UI integration |
| 8 | `_tab_phase.html` — collapsible graph section | UI |
| 9 | Impact preview on approval | UI |
| 10 | Replace coarse staleness with graph-aware staleness | Refinement |

Steps 1–6 deliver the core value (queryable dependencies + impact analysis)
with no UI changes. Steps 7–10 make it visible in the web interface.
