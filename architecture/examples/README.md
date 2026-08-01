# Coherent example record set

These 33 valid examples describe one fictional statistical method, one
user-launched Phase 4 preliminary run, one independent two-event replay vector, and two user-authorized control commands.
They are one connected representation test, not evidence that the fictional
scientific claim is true.

## Phase 4 research transaction

Read the main transaction in this order:

1. `run-command.example.json` records the user's exact authorization.
2. `run-manifest.example.json` binds that command to the split Phase 4 contract,
   frozen inputs, one profile artifact per role, unique role write roots, expected
   outputs, and six exact publication bindings.
3. `role-profile.example.json` gives the fully instantiated data-analyst profile.
   The other role profiles are frozen manifest artifacts, but their internal
   profile content is not claimed to be validated by this example set.
4. `handoff.example.json`, `statement.example.json`, `scientific-record.example.json`,
   `evidence.example.json`, `attention-item.example.json`, and
   `decision-record.example.json` show the communication, scientific content,
   formal attention, and lead decision produced around the run.
5. The six `authority-event*.example.json` files are the complete committed event
   range. They publish four current record generations, index one evidence item,
   and publish one immutable attention-item version.
6. The five Phase 4 `record-state*.example.json` files replay every changed record or
   evidence item at the final event root. `current-index.example.json` selects
   the four current formal records.
7. `publication-receipt.example.json` accounts for every committed event, formal
   record change, cumulative evidence or attention object, projection digest,
   and the replacement current index.
8. `run-state.example.json` records the separate controlled-run lifecycle from
   creation through atomic publication.

The command digest, manifest digest, authority-event content hashes and roots,
run-state event hashes, immutable object hashes, state-projection hashes, and
current-index hash are calculated from canonical JSON. Hashes inside illustrative
artifact pointers represent external content and are not repository-file hashes.

## Independent multi-event replay

The replay vector uses two authority events for one newly published theory
generation. The first establishes formal current publication with alignment
unassessed. The second changes only alignment to exact and binds the
intermediate state digest. The final record state and current index must carry
forward publication, position, and attention from the first event while taking
alignment from the second. Its receipt categorizes publication and state-only
events separately and accounts for both exactly once.

## Supporting research objects

- `method.example.json` is a formal Phase 2 method generation with exact method
  identity and research-run lineage.
- `literature-source.example.json` shows cumulative Phase 1 source provenance.
- `review-issue.example.json` shows one run-local Phase 5 issue version before
  lead consolidation and formal publication.

The phase contracts define how every phase publishes lead-consolidated attention
items. Phase 5 separately publishes lead-consolidated review-issue versions and
builds a deterministic current ledger from the prior ledger plus those formal
versions.

## Control commands

- `method-lifecycle-command.example.json` retires one exact active method without
  changing its mathematics or starting a research run.
- `formal-generation-withdrawal-command.example.json` withdraws one exact formal
  generation without deleting its immutable bytes or restoring an older version.

Both commands freeze the full current-index and event-journal head. The receipt
schema has separate source branches for a research run, method lifecycle command,
and generation withdrawal command.

## Rejected fixtures

The `invalid/` directory contains twelve near-valid objects that must be rejected:

- `authority-replay-existing-evidence-reset.invalid.json`;
- `authority-event-alignment-missing-prior-state.invalid.json`;
- `authority-event-cross-family.invalid.json`;
- `authority-event-evidence-reclassification-missing-prior-state.invalid.json`;
- `authority-event-withdraw-current.invalid.json`;
- `decision-auto-action.invalid.json`;
- `formal-withdrawal-nonformal.invalid.json`;
- `method-lifecycle-no-op.invalid.json`;
- `publication-receipt-research-run-withdraw.invalid.json`;
- `record-state-old-method-included.invalid.json`;
- `run-manifest-current-only-history.invalid.json`;
- `scientific-record-mutable-position.invalid.json`.

Passing package validation establishes representation, provenance, authority, and
workflow consistency. It does not establish scientific truth.