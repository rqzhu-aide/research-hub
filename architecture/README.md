# Research Hub Architecture Specification

## Purpose

This directory specifies a new research pipeline. It is a greenfield design and is not a description of the current Research Hub implementation.

The specification is written for three audiences:

- Researchers, who need to understand what the system records and what decisions remain theirs.
- Developers, who need precise objects, states, transitions, and failure behavior.
- Test authors, who need observable acceptance criteria rather than implied workflow conventions.

The system is intended to support iterative statistical, machine learning, mathematical, computational, and biological research. Its central task is not merely to store agent output. It must preserve the scientific basis of each result, coordinate role-specific reasoning, and show the researcher which conclusions are current, which evidence supports them, and which questions remain unresolved.

## The five architectural concerns

The design keeps five concerns separate.

| Concern | Question answered | Canonical mechanism |
|---|---|---|
| Information layer | How much detail does this file contain? | Primary artifact, structured scientific record, or compact decision view |
| Formal authority | Has the system validated and published this record? | Immutable generations, authority events, derived state, and publication receipts |
| Scientific identity | Which exact method or research object does this result concern? | Stable identifiers, versions, and content digests |
| Scientific assessment | What does the work establish, and with what uncertainty? | Statements, evidence, alignment, attention, and outcome records |
| User control | What may happen next? | Explicit user commands through a shared command interface |

Information layers describe file format and retrieval depth only. A compact decision view can report a current conclusion, while a detailed artifact can be obsolete or invalid. No code may infer authority from file depth, location, filename, or apparent completeness.

## Core operating model

Every research run is a controlled operation:

1. The user selects the phase, scope, method when applicable, instructions, and optional context.
2. The harness freezes the exact command and contract digests, input basis, prepared contexts, role profiles, read allowlists, write roots, expected outputs, and publication plan.
3. Team members work only inside their role-specific run roots. The harness verifies and materializes accepted handoffs and submission components into shared run locations.
4. The lead submits a phase result that preserves scientific uncertainty and unresolved disagreements.
5. Validators check structure, identity, provenance, phase obligations, and publication safety.
6. The harness atomically commits formal generations, authority events, derived state, the current index, and a publication receipt.
7. The Web UI projects the resulting records and offers possible user actions. It does not select or launch the next phase.

Publication means that the result is the formal record of what the run concluded. It does not mean that the result is favorable or mathematically proven by the software. A valid result may conclude that a claim is contradicted, a proof is incomplete, or an experiment is inconclusive.

## Specification map

Read the files in this order:

1. [System principles](00-system-principles.md) defines non-negotiable invariants and actor boundaries.
2. [Research domain model](01-research-domain-model.md) defines the scientific objects and their relations.
3. [Run harness](02-run-harness.md) defines controlled execution, validation, promotion, concurrency, and recovery.
4. [Storage and authority](03-storage-and-authority.md) defines immutable generations, append-only authority events, rebuildable current state, logical paths, and phase-specific storage semantics.
5. [UI contract](04-ui-contract.md) defines how formal records and user commands are projected into the Web interface.
6. `phases/` defines the scientific and operational contract for Phases 1 through 5.
7. `contracts/` contains the executable Phase 1 to Phase 5 registry used by adapters, validators, and UI projections.
8. `schemas/` contains machine-validatable schemas for persisted objects, while `examples/` contains coherent positive and negative fixtures.
9. `scenarios/` defines end-to-end acceptance cases, including failures and method changes.
10. [Validation strategy](05-validation-strategy.md) defines how conformance is proved without treating software checks as scientific judgment.
11. [Implementation roadmap](06-implementation-roadmap.md) gives the required build order and definition of done.
12. [Contract traceability](07-contract-traceability.md) maps global rules to contracts, schemas, and tests.
13. [Role and context contract](08-role-context-and-communication.md) defines reproducible team profiles, context, handoffs, and reviewer isolation.
14. [Control commands](09-control-commands.md) defines user-authorized method lifecycle changes and formal-generation withdrawal outside research runs.
15. `tools/` contains the one-command package conformance validator.
16. `decisions/` records accepted changes to invariants, schemas, and phase behavior.

If prose, an executable contract, and a schema disagree, implementation must stop until the inconsistency is resolved. None is silently treated as more authoritative. Schemas constrain representation, executable contracts drive deterministic behavior, and prose defines scientific meaning.

## Programmer starting point

1. Run `python architecture/tools/validate_package.py` and keep it passing.
2. Implement the typed domain objects, schema and contract loaders, immutable storage, authority-event journal, deterministic state projector, logical reference resolver, and typed control commands in Milestones 1 and 2.
3. Implement the generic harness with a dummy phase. Prove user authorization, frozen inputs, prepared contexts, role isolation, validation, atomic publication, event replay, conflict handling, and recovery before adding scientific phases.
4. Add phase adapters in roadmap order. Each adapter loads its executable contract, derives mode, role, and publication plans from structured fields, and is accepted only through its linked scenarios.

When a phase contract changes, edit its file under `contracts/phases/`, run `python architecture/tools/build_contract_registry.py`, update the corresponding prose and scenarios, and rerun package validation.

## Recommended logical project layout

The specification uses logical paths so that storage can later be implemented on a local filesystem, object store, or database without changing the domain model.

```text
project/
  project.json
  records/
    literature/current/
    method-catalog/current/
    methods/{method_id}/
      definition/current/
      theory/current/
      empirical/current/
      manuscript/current/
  generations/
    {record_type}/{record_id}/{generation_id}/
  runs/
    {phase_id}/{run_id}/
  control/
    current-index/
      current.json
      generations/{index_generation_id}.json
    record-state/{subject_kind}/{subject_id}.json
    authority-events/{sequence}-{event_id}.json
    publication-journal/{publication_id}.json
    replay-checkpoints/{checkpoint_id}.json
```

These paths express responsibilities, not permission by convention. The run harness is the only component allowed to create formal generations, append authority events, or update derived projections under `records/`, `generations/`, or `control/`. Agents receive write access only to their allocated role roots under `runs/`.

Formal objects should refer to one another with stable logical references rather than operating-system paths. Examples include:

```text
record://literature/current
record://method/{method_id}/definition/current
record://method/{method_id}/theory/current
generation://{record_type}/{record_id}/{generation_id}
run://{run_id}/artifact/{artifact_id}
```

The resolver maps each reference to its physical representation and verifies its digest. See [Storage and authority](03-storage-and-authority.md).

## Phase semantics at a glance

The five phases do not share one generic replacement rule.

| Phase | Formal object maintained | Update semantics |
|---|---|---|
| Phase 1 | Literature corpus and synthesis | Cumulative, deduplicated expansion with explicit corrections and withdrawals |
| Phase 2 | Method catalog and method definitions | Full-catalog or focused-method publication with method lineage |
| Phase 3 | Current theory record for one method | Complete replacement by a new validated generation |
| Phase 4 | Empirical evidence registry plus current evidence index, synthesis, and implementation record for one method | Immutable evidence accumulation plus four atomically replaced current slots, including the phase decision |
| Phase 5 | Current manuscript for one method | Complete replacement tied to exact upstream generations |

The detailed input, role, validation, promotion, and user-decision rules belong in the phase specifications.

## How developers should use this package

For each feature, developers should proceed in this order:

1. Identify the applicable invariant and phase contract.
2. Implement or update the persisted schema.
3. Implement a typed domain representation.
4. Implement validation without adding scientific meaning not present in the contract.
5. Implement state transitions through the run harness.
6. Add positive, negative, conflict, and recovery tests.
7. Add the UI projection only after the backend record is authoritative.

A feature is not complete when a page renders or a file is written. It is complete when its state transitions, invalid inputs, interrupted publication, scientific uncertainty, and user-visible consequences have all been tested.

## Normative language

The words **must**, **must not**, **should**, and **may** are normative:

- **Must** and **must not** define required behavior.
- **Should** defines the preferred behavior; deviations require a documented reason.
- **May** defines optional behavior that must not change the meaning of required behavior.

Invariant identifiers, object names, and state names are stable interfaces. Renaming them requires a specification change and migration plan.
