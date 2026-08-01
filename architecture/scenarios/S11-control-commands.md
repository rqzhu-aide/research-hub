# S11: User-Controlled Lifecycle and Withdrawal

## Purpose

Verify that method retirement, method reactivation, and formal-generation
withdrawal are explicit user-authorized control transactions rather than research
runs.

## Initial state

- Method `method.overlap_stabilized_score` is active at one exact current
  `method_record` generation.
- The current `method_catalog` identifies that generation as active.
- Current Phase 3 and Phase 4 records exist for the method.
- The UI has resolved current-index generation `generation.current_index.040`,
  event sequence 40, and the corresponding index and event-root digests.

## Retirement and reactivation

The user submits a `MethodLifecycleCommand` that names the exact method-record and
catalog generations, the exact control head, expected state `active`, target state
`retired`, and a reason.

The service validates the command and atomically publishes lifecycle-only
replacement generations for the method record and catalog. Their `published` and
`superseded` authority events, rebuilt projections, current index, and receipt
commit together. The method identity, version, definition digest, and scientific
content do not change. Existing Phase 3 and Phase 4 records remain formal and
unchanged, but ordinary launches for the retired method become ineligible.

Repeating the same idempotency key and command digest returns the same receipt.
A reactivation command based on the earlier control head returns `409 CONFLICT`
and changes nothing. After refresh, a new exact command may change `retired` to
`active` and restore ordinary launch eligibility when all other prerequisites are
satisfied.

## Formal-generation withdrawal

The user selects the exact current Phase 3 generation and submits a
`FormalGenerationWithdrawalCommand` with its content digest, formal current
`DerivedRecordState` digest, current control head, authenticated actor, and
scientific-correction reason.

The service appends one `withdrawn` event for the exact generation, removes it
from current resolution without restoring an older generation, records typed
alignment and attention impacts for dependents, rebuilds projections and the
current index, and commits one receipt. The withdrawn generation's immutable
bytes and provenance remain available for audit but cannot serve as an eligible
ordinary input. Correction requires a new generation from a later user-started
Phase 3 run.

## Acceptance checks

- Both commands validate only against their distinct schemas and the
  `ControlCommand` union.
- The lifecycle command permits only `active` to `retired` and `retired` to
  `active`.
- A no-op lifecycle command is rejected before any formal change.
- Withdrawal requires an exact target whose derived publication state is
  `formal`.
- A nonformal withdrawal request is rejected before any formal change.
- Every transaction compares the exact current-index generation and digest,
  event sequence and root, target generations, and target state before commit.
- Any stale basis returns `409 CONFLICT` without a generation, event, receipt, or
  index change.
- Retirement preserves downstream scientific records but disables ordinary
  Phase 3 and Phase 4 launches for that method.
- Withdrawal preserves immutable bytes, blocks target eligibility, propagates
  dependency effects, and never restores an older generation as current.
- Neither command creates a run ID, run workspace, run manifest, handoff, role
  profile, or role execution.
- Neither command launches a later phase.
