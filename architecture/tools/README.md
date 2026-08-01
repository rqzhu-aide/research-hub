# Architecture validation tools

After changing a split phase contract, rebuild the aggregate:

```text
python architecture/tools/build_contract_registry.py
```

Then run the package validator from the repository root:

```text
python architecture/tools/validate_package.py
```

The current validator checks:

- 22 valid JSON Schema Draft 2020-12 definitions;
- 33 complete valid examples and 12 rejected negative fixtures;
- exact registration of every positive and negative fixture file;
- exact equality between the five split phase contracts and `phases.json`;
- local Markdown links, forbidden long dash characters, and trailing whitespace;
- fixed phase modes, role order, stage reads and writes, prepared contexts, and
  user-controlled history;
- itemwise validation for collection outputs and exact publication coverage for
  canonical records and cumulative objects;
- one lead attention collection and one append binding in every phase;
- Phase 1 literature append, Phase 2 method upsert, Phase 4 evidence append, and
  Phase 5 review-issue append plus deterministic ledger rebuild;
- publisher prohibition on creating scientific content;
- exact command-to-contract resolution for all eight modes, both Phase 1 search
  scopes, typed required and optional choices, and focused Phase 2 method identity;
- exact command-to-manifest equality for the contract identity, selected mode,
  `choice_values`, context policy, and resource limits;
- shared network-policy vocabulary and no-broadening checks for `none`,
  `approved_resources`, and `user_authorized`;
- canonical run-command, split-contract, and manifest digests;
- every manifest publication binding, output mapping, formal reducer input,
  named bundle component, and target;
- all role-produced outputs under unique role write roots;
- one fully instantiated data-analyst profile and immutable profile artifacts for
  every other role step. It does not claim to validate profile content that is
  not instantiated in the example set;
- Phase 5 reviewer isolation and distinct theorist, analyst, and outside-reviewer
  frozen read sets;
- canonical immutable-object, authority-event, record-state, and current-index
  hashes;
- binary authority-event root chaining across the complete six-event receipt
  range;
- receipt accounting for every record change, cumulative object, derived-state-only change, authority event,
  projection digest, and current-index replacement;
- ordered whole-field event folding for the five Phase 4 state projections;
- checkpoint-seeded subject-history validation that reserves the no-prior full
  evidence form for a genuinely new subject;
- an independent two-event replay vector that carries earlier publication fields
  forward, replaces a later alignment field, verifies the intermediate-state
  digest, and accounts for state-only events;
- deterministic reconstruction of five record or evidence state projections and
  four current-index slots at the final event root;
- resolution of every formal attention reference to a receipt-published immutable
  attention-item version;
- contiguous, uniquely identified, time-ordered run-state events, legal lifecycle
  transitions, canonical event hashes, and final journal-root agreement;
- both control commands against their specific schemas and the `ControlCommand`
  union;
- canonical control-command digests, exact concurrency heads, legal lifecycle or
  withdrawal preconditions, and absence of research-run fields;
- in-memory method-lifecycle and withdrawal receipt probes against the
  discriminated receipt source and transaction-effect constraints;
- lifecycle method lineage with exact predecessor generation and unchanged method
  identity.

Passing these checks establishes representation, authority, provenance, and
research-workflow consistency. It does not establish scientific truth.