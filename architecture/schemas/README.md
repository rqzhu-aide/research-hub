# Machine-readable schemas

## Purpose

These JSON Schema Draft 2020-12 files define the persisted shapes of the
architecture. The prose specifications define scientific meaning. An
implementation must satisfy both.

A schema-valid object is structurally eligible for semantic validation. It is
not automatically scientifically correct, aligned, current, or publishable.

## Schema inventory

| Schema | Object |
|---|---|
| `common-definitions.schema.json` | Shared IDs, exact method identity, states, artifact pointers, alignment, attention, and outcome definitions |
| `run-command.schema.json` | Authenticated user authorization for one run |
| `control-command.schema.json` | Strict union of non-run control commands |
| `method-lifecycle-command.schema.json` | User authorization to retire or reactivate one exact method |
| `formal-generation-withdrawal-command.schema.json` | User authorization to withdraw one exact formal generation |
| `run-manifest.schema.json` | Immutable prepared run basis and exact role execution plan |
| `run-state.schema.json` | Run lifecycle projection and append-only lifecycle events |
| `role-profile.schema.json` | Versioned stance, instruction, output contract, memory, skills, knowledge, tools, and stage scope |
| `method.schema.json` | Immutable method generation with research-run or lifecycle-command lineage |
| `literature-source.schema.json` | Immutable cumulative literature identity and search provenance |
| `scientific-record.schema.json` | Immutable run-local candidate or formal scientific generation |
| `statement.schema.json` | Immutable addressable scientific statement generation |
| `evidence.schema.json` | Immutable evidence item and creation-time exact-method applicability |
| `attention-item.schema.json` | Immutable version of a research question or defect requiring attention |
| `handoff.schema.json` | Immutable run-local communication between roles |
| `decision-record.schema.json` | Immutable lead synthesis for a user decision |
| `review-issue.schema.json` | Immutable Phase 5 review issue and disposition generation |
| `publication-receipt.schema.json` | Atomic proof of one research-run or control-command transaction |
| `authority-event.schema.json` | Append-only change to derived publication, position, alignment, attention, or eligibility state |
| `record-state.schema.json` | Rebuildable current state for a record generation or evidence item |
| `current-index.schema.json` | Rebuildable mapping from each logical current slot to one formal generation |
| `phase-contract.schema.json` | Executable Phase 1 to Phase 5 behavior, prepared contexts, roles, validation, and publication |

## Immutable research objects and derived current state

Content generations preserve the scientific state at creation. Depending on the
object, this includes `authority_at_creation`, `alignment_at_creation`,
`research_attention_at_creation`, and `applicability_at_creation`. These fields
never change after the object is sealed.

Later publication, supersession, method change, attention, withdrawal,
invalidation, or evidence reclassification creates an append-only
`AuthorityEvent`. `RecordState` folds the ordered events into current publication
state, record position, alignment, research attention, and evidence eligibility.
`CurrentIndex` identifies current formal slots and cites the `source_event_ids`
that support each slot.

Deleting and rebuilding derived projections from the same event journal must
produce the same digests. A formal generation must remain byte-identical while
its derived current state changes.

## Independent state dimensions

Do not reintroduce one generic `status` field.

- Creation authority states how the immutable bytes were created.
- Derived publication state records whether the object is run-local, submitted,
  validated, formal, withdrawn, or invalid.
- Derived record position records current, historical, or none.
- Derived alignment records exact, compatible, unassessed, outdated, or not
  applicable.
- Research attention records unresolved work and severity.
- Scientific outcome records what the phase established.
- Evidence eligibility records whether a P4 item may enter the exact-method
  current evidence index.

These dimensions are independent. A generation may remain current in position,
be outdated in alignment after a method change, retain its earlier scientific
outcome, and carry new research attention through derived state.

## Method version and Phase 5 target rules

`method_identity.version` is a positive integer.

- Each calculation-defining change increments it by exactly one and changes the
  definition digest.
- A prose-only or bibliographic revision leaves the identity unchanged.
- Retirement or reactivation creates a lifecycle-only replacement generation. It
  preserves the exact method identity, definition, and scientific content while
  naming the predecessor generation and authorizing control command.
- Withdrawal is not a lifecycle transition and cannot be reversed through method
  reactivation.
- A changed mathematical-definition digest can never be compatible.
- A P3 replacement reassesses the complete theory for the new identity.
- Selected-method P4 results are recomputed for the new identity and receive new
  evidence IDs.
- Phase 5 assembly requires the exact current method, theory, and empirical
  basis.
- Phase 5 review-revision may freeze an older manuscript only within the same
  stable method lineage. This selects the document to revise and does not relax
  the exact-current basis required for the revised manuscript.

JSON Schema checks local shape. A semantic validator checks transitions and
cross-object identities.

## Run object separation

The run objects have different mutation rules.

- `RunCommand` is one user authorization for scientific work. It binds the exact phase contract and mode, then records phase-specific inputs in `choice_values` without duplicating them as generic scope or method fields.
- `MethodLifecycleCommand` and `FormalGenerationWithdrawalCommand` are user
  authorizations for formal state changes without a research run.
- `RunManifest` is sealed after preparation.
- `RunState` records lifecycle events and their current projection.
- `PublicationReceipt.source` distinguishes a research run, method lifecycle
  command, or generation withdrawal command. The receipt identifies the exact
  event range, event-root digest,
  projection digests, and current-index generation committed by publication.

This separation supports reproducibility, optimistic concurrency, and crash
recovery. The original launch command authorizes preparation, execution,
validation, and publication when all declared checks pass. No second generic
approval state is inserted.

## Reproducible role execution

A role profile freezes exact `applicable_stage_ids` and immutable artifact
pointers for its stance, instruction, output contract, skills, tools, and
knowledge resources.

The run manifest freezes for each role step:

- `stage_id` and `execution_group_id`;
- serial or parallel execution;
- role and profile input;
- exact `input_ids` and `output_ids`;
- one unique `role_write_root` within the run root.

A phase contract may declare a harness-prepared immutable context. The Phase 5
`p5.review_packet` is one such object and becomes a frozen manifest input of kind
`prepared_context`. In a stage with `role_reads`, those role-specific read sets
replace a shared read set. The outside reviewer receives only
`p5.review_packet`; the theorist and data analyst receive their declared internal
sets.

## Downstream effects

Each executable phase effect represents alignment and research attention
separately:

- `alignment_effect` preserves or sets derived alignment;
- `attention_effect` records no item, an item if scientifically identified, or a
  required reassessment item;
- `automatic_run` is always `false`.

Preserving alignment does not prevent a phase from recording useful research
attention. No effect may launch another phase.

## Required semantic validators

JSON Schema cannot establish all cross-object invariants. The implementation
must also provide named validators for at least:

- canonical serialization and digest verification;
- exact command-to-manifest binding and resource-policy no-broadening;
- control-command transition, idempotency, authorization, and optimistic-concurrency checks;
- exact receipt-source discrimination for research runs and control commands;
- exact publication bindings from validated role outputs to formal targets, with
  deterministic publishers prohibited from creating scientific content;
- stable-ID uniqueness and reference resolution;
- immutable creation fields and rejection of mutable current-state fields in
  content generations;
- authority-event sequence continuity, root-digest chaining, and deterministic
  record-state reconstruction;
- agreement among record-state, current-index, event IDs, and publication
  receipt;
- method definition normalization and exact version advancement;
- prohibition on compatible alignment for a changed definition digest;
- run-state transition legality and agreement with the last lifecycle event;
- equality among manifest phase, mode, contract version, contract digest, run ID,
  and write root;
- exact stage order, execution groups, role-specific reads, frozen profiles,
  declared outputs, and unique role write roots;
- stage-compatible profiles and immutable output-contract, skill, tool, and
  knowledge-resource digests;
- prepared-context sources, mode scope, and immutable materialization;
- selected-history agreement with the user command;
- expected target generation and optimistic-concurrency checks;
- one current generation per logical slot;
- evidence-ID immutability and exact-method eligibility;
- compact summary agreement with structured statements and evidence;
- Phase 5 exact-basis readiness, same-stable-method manuscript targeting, and
  outside-reviewer isolation;
- separate downstream alignment and attention effects with no automatic run;
- atomic publication, receipt reconstruction, and recovery by event replay.

Each validator returns a stable code, object location, violated contract rule,
and smallest correction. It must not claim to prove scientific truth.

## Examples

The sibling `../examples/` directory contains 33 valid examples covering every
persisted schema except `common-definitions` and `phase-contract`. The five split
phase contracts instantiate `phase-contract`, and their aggregate is rebuilt as
`contracts/phases.json`.

Twelve targeted invalid fixtures test explicit user control, current-only history
isolation, lifecycle and withdrawal preconditions, prior-state binding, event-family isolation, the immutable-generation boundary, and exclusion of older-method
evidence from exact current state.

Run `python architecture/tools/validate_package.py` from the repository root to
check the complete package.

## Schema evolution

- Every object declares `schema_version`.
- Representation migration and scientific revision are separate operations.
- A representation-only migration cannot change a method definition digest or
  scientific outcome.
- A schema change that alters persisted meaning requires an architecture
  decision, updated examples, updated scenarios, and a migration rule.
- Unknown scientific semantics are rejected rather than guessed from prose.