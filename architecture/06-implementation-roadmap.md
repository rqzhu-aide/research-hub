# Implementation Roadmap

## Goal

Build the research system from stable domain contracts outward. Do not begin by
coding five independent phase workflows or by binding the Web UI directly to
folders. The run harness, publication authority, and derived-state model must
work first.

## Recommended code boundaries

```text
src/
|-- domain/          # typed identities, records, statements, decisions
|-- schemas/         # schema loading and version dispatch
|-- storage/         # safe paths, immutable artifacts, event journal
|-- harness/         # run lifecycle, freezing, validation, publication, recovery
|-- phases/          # one adapter per executable phase contract
|-- alignment/       # dependency effects and authority-event construction
|-- projections/     # derived state and researcher-facing view models
`-- application/     # commands and services used by Web and remote control
```

Dependencies should point inward. Phase adapters may depend on domain, storage,
and harness interfaces. Domain code must not depend on phases or the Web UI.
Projections may depend on domain objects and ordered authority events, but
canonical generations must never depend on a UI representation.

## Milestone 0: specification baseline

Deliver:

- reviewed system principles;
- accepted domain vocabulary;
- accepted prose and executable phase contracts;
- valid schemas, positive examples, and targeted negative examples;
- acceptance scenarios assigned stable IDs;
- recorded decisions for any unresolved policy;
- a passing `python architecture/tools/validate_package.py` check.

Exit criterion: two programmers can independently describe the same commands,
state transitions, role visibility, expected formal generations, and derived
current state, and the package validator reports no inconsistency.

## Milestone 1: domain and schema library

Implement:

- IDs, digests, exact method identity, and logical artifact references;
- authenticated run and control commands, immutable run manifest, cryptographic
  run-state journal, and source-discriminated publication receipt with committed
  event and projection proofs;
- immutable scientific record, statement, evidence, decision, attention,
  review issue, literature source, method, and handoff models;
- append-only authority-event and rebuildable record-state models;
- current-index models that cite their source authority events;
- versioned role profiles with exact stage scope, instructions, immutable output
  contract, memory policy, skills, tools, knowledge resources, visibility, and
  output obligations;
- immutable artifact pointers and digests for every required output contract,
  skill, tool, and knowledge resource;
- run-manifest role steps with stage ID, execution group, exact input IDs,
  expected outputs, and role-specific write root;
- exact manifest bindings from each contract-selected input, prepared context,
  and expected output to its executable-contract obligation;
- executable, mode-scoped publication bindings from contract output IDs to append or current-slot operations, target types and slots, named bundle components, and expected prior generations;
- command envelopes that bind one exact phase-contract version, digest, and mode,
  with typed phase-specific `choice_values`;
- executable phase-contract loading by version and digest, including
  mode-scoped harness-prepared contexts;
- schema and cross-object semantic validation.

Exit criterion: every example validates, every negative fixture is rejected,
all models round-trip without information loss, immutable content schemas reject
mutable current-state fields, and every run can name the exact contract,
execution plan, and role resources it used.

## Milestone 2: storage, events, and authority service

Implement:

- safe project and run paths;
- role-specific run-local write boundaries;
- content-addressed immutable artifact references;
- separate namespaces for immutable formal generations, append-only authority
  events, rebuildable record-state projections, and current indexes;
- atomic generation creation and cumulative publication primitives;
- ordered authority-event append with idempotent event IDs, RFC 8785 event payload digests, event-type change constraints, and the specified prior-root plus content-digest chain;
- deterministic event replay into record-state and current-index projections;
- historical generation retention without mutable status fields;
- replacement, retirement, withdrawal, invalidation, alignment, attention, and
  evidence-eligibility events;
- publication receipts that bind event ranges and roots to projection digests and
  current-index generations;
- withdrawal events that identify the affected generation without creating a
  replacement generation;
- conflict detection for two publications that change the same current slot;
- one atomic authority transaction service shared by research publication,
  method lifecycle changes, and formal-generation withdrawal;
- exact control-head and target compare-and-swap, idempotent command recovery,
  and no-run execution for control commands.

Exit criterion: storage tests prove that failed or interrupted publication
cannot partially replace current state, a published generation remains
byte-identical after later changes, receipts verify the exact committed state,
and deleting and rebuilding projections from the event journal yields the same
state digest. Method lifecycle and withdrawal tests must also prove that a stale
control command changes nothing and that no control transaction creates a run.

## Milestone 3: generic run harness

Implement:

- authenticated command intake, exact eight-mode contract resolution, typed
  choice validation, idempotency, and preparation;
- formal input, selected-history, prepared-context, contract, role-profile,
  output-contract, skill, tool, and knowledge-resource freezing;
- phase-contract version and digest verification;
- contract-derived prepared-context construction, stage dispatch, serial and
  parallel execution groups, role-specific read allowlists, and role-specific
  write roots;
- role-root-only artifact production, followed by harness verification and harness-owned materialization of structured handoffs and run-local submission;
- lifecycle events in the run-state journal;
- schema, phase-contract, provenance, alignment, and boundary validation;
- atomic creation of formal generations, authority events, projections, current
  index, and a receipt carrying event-range, event-root, projection, and index
  digests;
- failure, cancellation, conflict handling, event replay, and recovery;
- bounded audit and operational logs.

Use a dummy phase with one input and one output. Do not proceed until the dummy
phase passes the complete lifecycle, prepared-context, role-isolation,
event-replay, receipt-verification, recovery, and concurrency tests.

## Milestone 4: Phase 1 adapter

Implement cumulative literature publication, stable source identity, duplicate
handling, corrections, synthesis replacement, and role-facing handoffs.

Exit criterion: the first-project scenario and a focused literature update both
pass without changing existing source identities. The current synthesis can be
rebuilt from its formal generation and authority events.

## Milestone 5: Phase 2 and method framework

Implement the method catalog, full-catalog and focused-method scopes, permanent
stable IDs, authoritative mathematical definitions, version advancement,
lineage, and the no-run retirement and reactivation command path.

Exit criterion: a no-change review preserves method identity, a calculation
change requires the next method version and a new definition digest, a focused
run cannot change any other method, lifecycle control preserves mathematical
identity while atomically replacing the method and catalog, and downstream
outdated alignment appears through derived state without rewriting old P3, P4,
or P5 generations. S11 must pass.

## Milestone 6: Phases 3 and 4 together

Implement the sibling workflows in the same milestone:

- P3 complete-current theory replacement;
- P4 cumulative evidence publication plus atomic replacement of the current evidence index, empirical synthesis, implementation record, and phase decision;
- fixed stage and role orders;
- exact method binding;
- sibling-basis records;
- current-only default context;
- optional user-selected historical context;
- downstream alignment and attention events.

Exit criterion: either phase may run first, later runs consume the available
current aligned sibling record, method changes mark both phases for reassessment,
and no phase is launched automatically.

## Milestone 7: Phase 5

Implement assembly and review-revision modes, exact upstream-basis checks, one
current manuscript, immutable review snapshots, issue disposition, and draft
replacement.

The review-revision mode must freeze one target from the selected stable method
lineage. It may use an older version of that same method as an explicitly
outdated target, but never a different method. The outside reviewer receives
only the frozen review packet as scientific context. No project record,
attention item, selected history, non-reviewer command detail, project memory,
or project-specific knowledge resource is injected outside that packet. System
invariants and a non-project reviewer profile remain execution metadata. The
theorist and analyst receive their declared specialist inputs, and the lead
revises only after all parallel reports are fixed.

Exit criterion: Phase 5 cannot combine method lineages or versions, the reviewer
cannot read internal specialist material, and upstream changes mark the
manuscript outdated without altering or deleting its published generation.

## Milestone 8: researcher-facing projections

Implement view models and the Web UI from structured generations and derived
state:

- method catalog;
- run controls;
- publication authority and current position;
- dependency alignment;
- research attention;
- scientific outcome;
- decision brief;
- current record and explicit history access.

Exit criterion: the UI never derives status from file existence or arbitrary
prose, never conflates scientific outcome with operational state, and never
starts work without a user action.

## Milestone 9: operational hardening

Implement:

- crash recovery;
- concurrent-run protection;
- integrity and event-replay audits;
- backup and restore verification;
- bounded logs and observability;
- migration and schema-upgrade tooling;
- performance tests for large P4 evidence collections and event journals;
- supported-operating-system tests.

Exit criterion: all failure-injection and recovery scenarios pass on supported
operating systems, and a restored project reproduces the same generations,
authority events, and current-state digest.

## Pull-request discipline

Each implementation pull request should identify:

- specification sections implemented;
- schemas added or changed;
- scenarios made executable;
- new invariants enforced;
- migration consequences;
- known scientific judgments that remain agent-reviewed rather than
  machine-checked.

No pull request should silently change a phase contract. Contract changes require
an architecture decision record and corresponding scenario updates.
