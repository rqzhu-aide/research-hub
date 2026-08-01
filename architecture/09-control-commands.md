# Control Commands

## 1. Purpose

Control commands change formal project state without performing scientific work.
They are distinct from a `RunCommand` and must never create a research run, a run
workspace, or role execution.

Version 1 defines two commands:

1. `MethodLifecycleCommand` retires or reactivates one method through an atomic
   Phase 2 catalog transaction.
2. `FormalGenerationWithdrawalCommand` withdraws one exact formal generation
   through an atomic authority transaction.

These commands use separate schemas because they have different scientific
meanings. Method retirement is a reversible portfolio decision about whether a
method is available for ordinary work. Generation withdrawal is an irreversible
correction to the authority of exact published content. A common API may accept a
discriminated union of the two command types, but it must not replace them with a
generic target-state command.

## 2. Shared command requirements

Both commands contain:

| Field | Type | Requirement |
|---|---|---|
| `schema_version` | schema version | Required |
| `command_type` | discriminator | Required and fixed by command schema |
| `command_id` | stable ID | Required and globally unique within the project |
| `idempotency_key` | string | Required and unique for one intended user action |
| `project_id` | stable ID | Required |
| `expected_control_head` | object | Required optimistic-concurrency basis |
| `reason` | object | Required structured reason and explanation |
| `requested_by` | actor object | Required authenticated user authority and optional delegated operator |
| `content_sha256` | SHA-256 | Required digest of canonical command JSON with this field omitted |
| `requested_at` | date-time | Required |

`requested_by` has the same semantics as `RunCommand.requested_by`. A delegated
operator records both the user authority and the operator identity. The service
must reject any command outside the delegation.

`reason` contains:

```json
{
  "code": "user_portfolio_decision",
  "explanation": "This method is no longer part of the active research portfolio."
}
```

Both fields are nonempty. A client-generated label is not sufficient as the
formal explanation.

`expected_control_head` contains:

```json
{
  "current_index_generation_id": "generation.current_index.040",
  "current_index_sha256": "...",
  "last_event_sequence": 40,
  "event_root_sha256": "..."
}
```

The service compares all four values before preparing the transaction and again
at commit.

## 3. MethodLifecycleCommand

### 3.1 Purpose and fields

`MethodLifecycleCommand` changes whether one stable method is active in the
research portfolio. Its `command_type` is `method_lifecycle_change`.

In addition to the shared fields, it requires:

| Field | Type | Meaning |
|---|---|---|
| `method_id` | stable ID | Permanent method ID |
| `expected_method` | object | Exact current method-record generation shown to the user |
| `expected_catalog` | object | Exact current method-catalog generation shown to the user |
| `target_lifecycle_state` | enum | `retired` or `active` |

`expected_method` contains:

```json
{
  "record_id": "record.method.example",
  "generation_id": "generation.method.example.004",
  "content_sha256": "...",
  "method_identity": {
    "stable_id": "method.example",
    "version": 2,
    "definition_sha256": "..."
  },
  "lifecycle_state": "active"
}
```

`expected_catalog` contains `record_id`, `generation_id`, and `content_sha256`.

### 3.2 Legal transitions

Only these transitions are legal:

| Expected state | Target state | Operation |
|---|---|---|
| `active` | `retired` | Retire method |
| `retired` | `active` | Reactivate method |

`proposed` activation remains a Phase 2 research publication. A withdrawn formal
generation cannot be reactivated. A new command requesting the state already in
force fails with `NO_STATE_CHANGE`. Repeating a previously committed command with
the same idempotency key returns its original receipt.

### 3.3 Validation and transaction effects

The service must verify that:

1. The expected method generation is the current formal `method_record` for
   `method_id`.
2. The expected catalog is the current formal `method_catalog`.
3. The catalog points to the expected method generation and lifecycle state.
4. The method identity, mathematical definition, version, definition digest,
   scientific content, provenance, assumptions, and limitations will remain
   unchanged.
5. The requested transition is legal and authorized.

The atomic transaction creates:

1. A replacement `method_record` generation with the new lifecycle state, the
   same exact method identity, and lifecycle lineage to the prior generation.
2. A replacement `method_catalog` generation that selects the new method-record
   generation and updates the active or retired portfolio view.
3. `published` authority events for the two new generations.
4. `superseded` authority events for the two prior generations.
5. Rebuilt `DerivedRecordState` projections and a complete replacement
   `FormalCurrentRecordIndex`.
6. One atomic receipt.

No Phase 2 role recommendation can authorize this transaction. Retirement and
reactivation do not change the method version or definition digest. They do not
change the publication, position, alignment, attention, or scientific outcome of
existing Phase 3, Phase 4, or Phase 5 records.

Retirement removes the method from ordinary Phase 3 and Phase 4 launch
eligibility. Reactivation restores eligibility only when all other phase
prerequisites are satisfied.

## 4. FormalGenerationWithdrawalCommand

### 4.1 Purpose and fields

`FormalGenerationWithdrawalCommand` withdraws one exact formal generation after
an authenticated scientific-correction or administrative decision. Its
`command_type` is `formal_generation_withdrawal`.

In addition to the shared fields, it requires:

| Field | Type | Meaning |
|---|---|---|
| `target` | object | Exact immutable formal generation to withdraw |
| `expected_target_state` | object | Exact derived state shown to the user |

`target` contains:

```json
{
  "record_id": "record.theory.example",
  "record_type": "theory_record",
  "generation_id": "generation.theory.example.003",
  "content_sha256": "..."
}
```

`expected_target_state` contains:

```json
{
  "publication_state": "formal",
  "record_position": "current",
  "record_state_sha256": "..."
}
```

The target may be current or historical, but its derived publication state must
be `formal` when the command commits.

### 4.2 Withdrawal rules

Withdrawal is not deletion. The immutable generation and its provenance remain
stored and addressable for audit, but the resolver must reject it as an eligible
ordinary downstream input.

A withdrawn generation cannot be reactivated. Corrected scientific content must
be published as a new generation through the applicable user-started research
run. The service must not automatically restore an older historical generation
to current position.

### 4.3 Validation and transaction effects

The service must verify that:

1. The target identity and digest resolve to one immutable generation in the
   project.
2. Its current `DerivedRecordState` matches `expected_target_state`.
3. Its publication state is `formal`.
4. The actor is authorized to perform formal correction or withdrawal.
5. Every current record with a hard or contextual dependency on the target has
   been identified before commit.

The atomic transaction:

1. Appends one `withdrawn` `AuthorityEvent` for the exact target generation.
2. Sets derived `publication_state` to `withdrawn`.
3. Sets derived `record_position` to `none` when the target was current, or
   preserves `historical` position when it was already historical.
4. Removes a withdrawn current generation from its current-index slot and does
   not fill that slot from history.
5. Appends typed alignment and attention events for affected current dependents.
6. Rebuilds affected `DerivedRecordState` projections and a complete replacement
   `FormalCurrentRecordIndex`.
7. Commits one atomic receipt.

A current hard dependent of the withdrawn generation becomes noneligible for
exact-current use. Its alignment changes to `unassessed` with cause
`withdrawn_dependency`, and its research attention becomes `blocking` until an
eligible replacement basis and an applicable user-started rerun resolve the
dependency. A contextual dependency creates explicit attention but does not by
itself erase the dependent record's scientific outcome.

The transaction creates no replacement scientific generation.

## 5. Receipt source semantics

The receipt schema represents both research-run publication and control
transactions. Its source is a discriminated union:

```json
{
  "source": {
    "kind": "research_run",
    "command_id": "...",
    "run_id": "...",
    "phase": "P4",
    "manifest_sha256": "..."
  }
}
```

```json
{
  "source": {
    "kind": "method_lifecycle_command",
    "command_id": "...",
    "command_sha256": "..."
  }
}
```

```json
{
  "source": {
    "kind": "generation_withdrawal_command",
    "command_id": "...",
    "command_sha256": "..."
  }
}
```

Only `research_run` may carry `run_id`, `phase`, or `manifest_sha256`. A control
receipt still records validation reports, prior and new current-index identities
and digests, the contiguous authority-event range and roots, derived projection
digests, exact record changes, impacts, actor command, transaction ID, and commit
time.

A method-lifecycle receipt records `replace` changes for `method_record` and
`method_catalog`. A withdrawal receipt records a `withdraw` change with
`subject_generation_id`, no `new_generation_id`, and every supporting
`authority_event_id`.

## 6. Optimistic concurrency and idempotency

Control transactions use compare-and-swap. The service first compares the
command's expected control head, exact target generations, content digests, and
derived state digests with current backend state. Immediately before commit, it
repeats the control-head comparison.

Any mismatch returns `409 CONFLICT`, appends no authority event, creates no
generation, and leaves the current index unchanged. The response identifies the
stale object and instructs the client to refresh. The service must not silently
rebase a user decision onto newer scientific state.

The idempotency key is bound to the canonical command digest. Repeating the same
key and digest returns the original outcome. Reusing the key with different
content is rejected.

## 7. UI and remote-operation behavior

The backend exposes typed action descriptors for:

- `retire_method`
- `reactivate_method`
- `withdraw_formal_generation`

Each descriptor contains the exact target identity and digest, current state,
allowed transition, expected control head, reason requirements, enabled state,
reason code when disabled, consequence summary, and affected-dependent preview.

The Phase 2 method table presents retire or reactivate according to the current
lifecycle state. Withdrawal appears in the selected formal record's correction
controls, not in the ordinary phase-run panel. The confirmation view states that:

- No research run or role execution will occur.
- Retirement preserves existing scientific records and history.
- Withdrawal removes exact content from eligible current use and may block
  dependent work.
- Neither action launches a later phase.

The Web UI and authorized remote operator use the same command service and
receive the same eligibility and conflict responses. A confirmation interaction
is not a separate approval state.

## 8. Failure behavior

Authentication, authorization, schema, transition, digest, dependency-closure,
or concurrency failure occurs before commit and changes no formal state.

If interruption occurs during commit, recovery inspects the transaction journal.
It must either complete the same prepared transaction or confirm rollback before
accepting another authority transaction. Partial generations, partial events, or
a mixed current index must never become visible.

Deterministic control validation reports are retained with a successful receipt.
Rejected commands may retain an operational audit entry, but they do not receive
a formal publication receipt and do not enter the authority-event journal.

## 9. Acceptance criteria

Implementation must prove:

1. An active method can be retired only from the exact method, catalog, and
   control-head state authorized by the user.
2. Retirement publishes lifecycle-only replacement method and catalog
   generations while preserving method identity, version, definition digest,
   scientific content, and downstream scientific records.
3. A retired method cannot be launched in ordinary Phase 3 or Phase 4 work.
4. A retired method can be reactivated by a new exact command when other
   prerequisites remain valid.
5. A recommendation from any role cannot retire or reactivate a method.
6. A formal generation can be withdrawn only by exact generation identity,
   content digest, derived-state digest, and control head.
7. Withdrawal leaves immutable bytes and provenance unchanged, removes current
   eligibility, records dependent impacts, and never restores history as current.
8. A withdrawn generation cannot be reactivated; correction requires a new
   generation from the applicable user-started research run.
9. Neither command creates a run ID, run workspace, manifest, role profile,
   handoff, or role execution.
10. A stale command returns `409 CONFLICT` and produces no generation, event, or
    index change.
11. Repeating an identical committed command returns the same receipt without
    duplicating generations or events.
12. Failure or interruption cannot expose a partial lifecycle or withdrawal
    transaction.
