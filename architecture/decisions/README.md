# Architecture Decisions

Use architecture decision records for changes that alter a system invariant,
persisted schema, phase contract, promotion rule, user decision, or scientific
status meaning.

Small wording corrections do not require a decision record. A change requires
one when two reasonable implementations would produce different formal records,
run behavior, or researcher decisions.

## Process

1. Copy `ADR-000-template.md` and assign the next number.
2. State the research and engineering problem without assuming a solution.
3. List the alternatives and their consequences.
4. Record the decision, affected contracts, schema changes, and scenario changes.
5. Mark the record Accepted before implementation begins.
6. Never rewrite an accepted decision to hide a later change. Supersede it with
   a new decision record.

## Required decision topics

Create a decision record for at least:

- adding or changing an authority state;
- changing which scientific outcomes may become current;
- changing a phase role order or run mode;
- changing method-version semantics;
- changing cumulative versus replacement storage behavior;
- changing default context or history policy;
- changing Phase 5 readiness;
- adding automated invalidation or promotion behavior;
- changing a researcher-visible status meaning;
- changing a control-command transition, concurrency basis, or withdrawal consequence.
## Accepted decisions

- [ADR-001: Contract-Bound Run Choices](ADR-001-contract-bound-run-choices.md)
- [ADR-002: Ordered Authority Replay](ADR-002-ordered-authority-replay.md)
