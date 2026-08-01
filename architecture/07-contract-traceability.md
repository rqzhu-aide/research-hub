# Contract Traceability

## Purpose

This index connects each non-negotiable research-workflow rule to its normative
specification, persisted representation, and acceptance evidence. It gives
programmers a concrete starting point and prevents an implementation detail from
quietly changing the research process.

The word `must` identifies a conformance requirement. A feature is not complete
until every rule it touches has a passing automated test.

## Global rules

| ID | Required behavior | Primary specification | Persisted or test evidence |
|---|---|---|---|
| RH-01 | Only the user may start or rerun a phase. | System principles, run harness, UI contract | Authenticated run command and command-authorization tests |
| RH-02 | An agent writes every artifact only inside its role-specific active run root; only the harness may materialize verified outputs into shared handoff, artifact, or submission locations. | Run harness, storage and authority, role and context contract | Role-root boundary, source-digest, and harness-materialization tests |
| RH-03 | Formal inputs, selected history, prepared contexts, phase contract, role profiles, output contracts, skills, tools, and knowledge resources are frozen before role work starts. | Run harness, role and context contract | Digested run basis and immutability tests |
| RH-04 | The system validates candidate output before it creates formal generations. | Run harness, validation strategy | Validation report and lifecycle tests |
| RH-05 | Publication commits the complete validated change or commits nothing. | Run harness, storage and authority | Receipt-bound generations, event range and root, projection digests, and current-index generation; S05 and S09 |
| RH-06 | Agents propose research records, but only the harness may create formal generations or authority events. | System principles, storage and authority | Role permissions and publication tests |
| RH-07 | Current formal records are the default context. Historical work is opt-in. | System principles, phase contracts | Context policy and selected-history manifest fields; S06 |
| RH-08 | No completion, status change, or agent recommendation starts another run. | System principles, UI contract | Command-authorization tests; all scenarios |
| RH-09 | Publication authority, record position, dependency alignment, research attention, and scientific outcome are separate dimensions. | Research domain model, storage and authority, UI contract | Authority-event, record-state, scientific-record, and projection tests |
| RH-10 | Machine validation may establish structure and provenance, but not scientific truth. | System principles, validation strategy | Validator boundaries in every phase contract |
| RH-11 | A structurally complete record may report a negative, contradictory, or inconclusive scientific result. | Research domain model, phase contracts | Scientific-outcome fixtures and S10 |
| RH-12 | An operationally incomplete or invalid run cannot replace valid current state. | Run harness, storage and authority | Run lifecycle and publication-guard tests; S05 |
| RH-39 | A formal content generation is immutable. Later replacement, alignment, attention, withdrawal, invalidation, or eligibility changes append events and update projections without rewriting it. | Research domain model, storage and authority | Forbidden-field schema tests, digest-preservation tests, and negative fixture |
| RH-40 | Derived record state and the current index are reproducible by ordered whole-field folding of the authority-event journal and agree with the publication receipt. Initial evidence state is allowed only for a subject absent from the authoritative checkpoint and earlier proposed events. | Storage and authority, validation strategy | Event-root, checkpoint-seeded subject-history, intermediate-state, multi-event replay, receipt-category, and state-digest tests |
| RH-44 | Authority-event content and journal-root digests use the specified RFC 8785 payload and prior-root plus content-digest algorithm, and each event type permits only its defined change family. | Research domain model, storage and authority | Cross-implementation hash vectors and illegal-change negative tests |
| RH-47 | Method retirement and reactivation use an authenticated lifecycle command, preserve exact mathematical identity, atomically replace the method and catalog generations, and create no research run. | Control commands, run harness, UI contract | Method-lifecycle schemas, semantic checks, and S11 |
| RH-48 | Formal-generation withdrawal targets one exact formal generation, creates no replacement, never restores history as current, and records dependent impacts without launching a run. | Control commands, storage and authority, UI contract | Withdrawal schema, authority-event tests, and S11 |
| RH-49 | Control commands freeze exact target and control-head state, use idempotent compare-and-swap, produce source-discriminated receipts, and behave identically through Web and remote clients. | Control commands, run harness, UI contract | Command digest, stale-basis, receipt-source, and parity tests; S11 |

## Research-object rules

| ID | Required behavior | Primary specification | Persisted or test evidence |
|---|---|---|---|
| RH-13 | Every method has a permanent stable ID and an exact calculation-defining identity. | Research domain model, Phase 2 | Method schema; S02 and S04 |
| RH-14 | Any calculation-defining method change advances the method version; a prose-only revision does not. | Research domain model, Phase 2 | Definition-digest validator and lineage tests; S02 and S04 |
| RH-15 | Method-bound theory, computation, evidence, and manuscript records name the exact method identity used. | Research domain model, Phases 3 to 5 | Frozen-basis fields and cross-record validation |
| RH-16 | A method-version change leaves the latest method-bound generations current in position but gives them outdated derived alignment until replacement runs complete. | Storage and authority, Phases 2 to 5 | Authority-event and record-state transition tests; S04 and S07 |
| RH-17 | A newly published sibling record is available to the next P3 or P4 run but never rewrites or automatically reruns the other phase. | Phases 3 and 4 | Handoff and frozen-basis records; S03 |
| RH-18 | Material claims and decisions retain assumptions, scope, provenance, and unresolved disagreement. | Research domain model | Statement, evidence, decision, and handoff schemas |

## Phase rules

| ID | Required behavior | Primary specification | Persisted or test evidence |
|---|---|---|---|
| RH-19 | P1 appends unique literature records and replaces the current synthesis. | Phase 1 | Literature generation tests; S01 |
| RH-20 | P2 supports a full catalog update or one user-selected focused method update. | Phase 2 | Scope validator; S01 and S02 |
| RH-21 | P2 presents methods but does not select a P3 or P4 branch. | Phase 2, UI contract | Catalog projection and command tests; S01 |
| RH-22 | P3 replaces the complete current theory record for one exact method identity. | Phase 3 | P3 contract tests |
| RH-23 | Each P3 run executes theorist, data analyst, then research lead. | Phase 3 | Stage and role-plan order test; S03 |
| RH-24 | P4 appends immutable evidence and atomically replaces the evidence index, empirical synthesis, implementation record, and phase decision for one exact method identity. | Phase 4, storage and authority | Four-slot publication and evidence-lineage tests; S03 and S07 |
| RH-25 | Each P4 run executes data analyst, theorist, then research lead. | Phase 4 | Stage and role-plan order test; S03 |
| RH-26 | P3 and P4 are independently user-launchable after P2. | Phases 3 and 4, UI contract | Eligibility projection tests; S03 |
| RH-27 | P5 requires current P1 and selected-method records, current P3 and P4 records for the exact method identity, readable artifacts, and no blocking integrity state. | Phase 5 | Readiness validator; S08 |
| RH-28 | P5 maintains one current complete manuscript and replaces it atomically. | Phase 5 | Manuscript slot and replacement tests; S08 |
| RH-29 | P5 review roles work from one frozen manuscript snapshot through distinct allowlists. The outside reviewer receives only the harness-prepared `p5.review_packet` as scientific context, with no project records, attention, selected history, project memory, or project-specific knowledge outside it. | Phase 5, role and context contract | Prepared-context, profile-resource, and role-specific read tests; S08 |
| RH-41 | A P5 review target may use an older version only within the selected stable method lineage. It must never come from another method. | Phase 5 | `same_stable_method` contract and negative lineage test |

## User-interface rules

| ID | Required behavior | Primary specification | Persisted or test evidence |
|---|---|---|---|
| RH-30 | The Web UI projects canonical structured records and never infers success from folder presence. | UI contract | View-model and adversarial-folder tests |
| RH-31 | Every phase explains availability, current basis, material changes, uncertainty, and available user actions. | UI contract, phase contracts | Projection fixtures and browser tests |
| RH-32 | Method tables report publication position, alignment, attention, and outcome separately for P3 and P4. | UI contract, Phase 2 | Method-overview projection tests |
| RH-33 | The Web UI and remote-control client invoke the same application commands and authorization rules. | UI contract, run harness | Command parity and authorization tests |

## Reproducibility and executable-contract rules

| ID | Required behavior | Primary specification | Persisted or test evidence |
|---|---|---|---|
| RH-34 | Every role step freezes an applicable stage ID, execution group, exact read allowlist, role-specific write root, versioned role profile, instructions, output contract, memory policy, skills, tools, knowledge resources, visibility, and output obligations. | Role and context contract, run harness | Role-profile and run-manifest schemas; execution-plan tests |
| RH-35 | A missing required output contract, skill, tool, knowledge resource, artifact digest, or role-profile digest blocks preparation rather than silently weakening the role. | Role and context contract | Resource-resolution and preparation-failure tests |
| RH-36 | Roles communicate material claims, assumptions, uncertainty, disagreement, and next checks through explicit run-local handoffs rather than hidden shared memory. | Role and context contract, phase contracts | Handoff schema, access-manifest tests, role-order tests |
| RH-37 | Prose phase contracts and the executable registry change together and remain machine-valid. | Phase contracts, executable contracts | Phase-contract schema, split-registry equality check, package validator |
| RH-38 | User authorization, immutable run basis, prepared contexts, lifecycle history, formal generations, authority events, derived state, and publication receipt remain distinct objects. | Research domain model, run harness, storage and authority | Run-command, run-manifest, run-state, scientific-record, authority-event, record-state, and publication-receipt schemas |
| RH-42 | Every harness-prepared context declares its source formal inputs, source user choices, applicable modes, immutable content requirements, and permitted role reads. | Run harness, executable contracts, role and context contract | Phase-contract prepared-context and undeclared-read tests |
| RH-43 | Every contract-selected manifest input and expected output names the exact executable-contract obligation that it materializes. Prepared contexts also retain their exact source input and user-choice IDs. | Run harness, executable contracts | Manifest-binding and contract-materialization tests |
| RH-45 | Every phase contract declares mode-scoped publication bindings from exact output IDs to append or current-slot operations, target types and slots, bundle components, and expected prior generations; the manifest seals the resolved bindings. | Run harness, executable contracts, research domain model | Publication-binding completeness, ambiguity, and stale-target tests |
| RH-46 | Shared handoff and submission artifacts are harness-owned materializations of verified immutable outputs from a producing role root, never direct role writes. | Run harness, role and context contract | Role-root escape tests and source-to-materialization digest tests |
| RH-50 | Every run command binds one exact phase-contract version, digest, and mode, and supplies only that mode's required or optional choice IDs with values of the declared kind. The manifest copies those choices exactly. | Research domain model, run harness, executable contracts | Eight-mode command resolution, P1 scope coverage, choice-type, missing-choice, stale-contract, and command-to-manifest tests |

## Change procedure

When a proposed change alters one of these rules:

1. update the governing normative document;
2. record an architecture decision when two reasonable behaviors would differ;
3. update every affected schema and example;
4. update the linked scenarios and negative tests;
5. update this table in the same change;
6. implement only after the revised contract is accepted.

If code behavior and this package disagree, the discrepancy is a contract
failure. Programmers must not resolve it by silently weakening a test.
