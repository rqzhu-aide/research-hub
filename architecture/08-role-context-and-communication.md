# Role, Context, and Communication Contract

## 1. Purpose

Research quality depends on more than assigning a task to an agent. Each role
must receive a reproducible scientific stance, phase instruction, context,
memory policy, skills, knowledge resources, tools, and output contract.

This document makes those inputs part of the controlled run. It does not define
the final prompt wording. It defines what a programmer must assemble, freeze,
expose, and validate.

## 2. Versioned role profile

Every role stage uses a versioned `RoleProfileManifest`. The manifest records:

- profile ID, version, and content digest;
- role, applicable phases, applicable modes, and exact `applicable_stage_ids`;
- scientific stance, also called the role's soul;
- phase-specific task instruction;
- required output and handoff contracts as immutable artifact pointers with digests;
- context visibility and isolation rules;
- memory policy;
- required and optional skills with immutable version and digest pointers;
- knowledge resources, retrieval policies, and immutable adapter-manifest version and digest pointers;
- allowed tools, libraries, execution limits, and immutable tool-manifest version and digest pointers;
- reviewer-isolation rules when applicable.

The scientific stance describes durable commitments, not a fictional persona. It
states the questions the role habitually asks, the evidence it treats as
decisive, the errors it must actively seek, and the claims it must not make.

A profile update creates a new immutable version. Every run freezes the exact
profile manifest used by each role. A completed run is never reinterpreted under
a later profile.

### 2.1 Frozen run role step

Every `RunRoleStep` freezes:

- `stage_id` and `execution_group_id`;
- serial or parallel execution;
- exact role-profile artifact version and digest;
- the exact artifact input allowlist with versions, digests, and locators;
- output and handoff identifiers and schemas;
- one role-specific run-local write root.

A role cannot resolve an input outside its allowlist or write outside its root. It writes handoffs and proposed publication components under that same root. After the role step closes, the harness verifies them and copies or content-addresses accepted outputs into harness-owned shared run locations.
Sharing an execution group permits parallel execution but does not grant mutual
visibility. Every parallel role receives the same frozen group-start state.

## 3. Role-specific scientific stance

| Role | Primary responsibility | Required challenge |
|---|---|---|
| Research lead | Integrate the scientific argument, preserve disagreement, and present the user's decision | Do not choose a branch, hide uncertainty, or publish directly |
| Theorist | Define mathematical objects, assumptions, claims, proofs, counterexamples, and boundaries | Do not treat simulation or empirical performance as proof |
| Data analyst | Define study design, implementation, data provenance, computation, uncertainty, and reproducibility | Do not treat a successful computation as a general theorem |
| Outside reviewer | Assess the frozen manuscript as an independent first-time reader | Do not edit the manuscript or inspect excluded internal deliberation |

Phase instructions narrow these responsibilities without changing them. For
example, the theorist performs primary work in Phase 3 and a mathematical
fidelity audit in Phase 4.

## 4. Context assembly

The harness builds a role-specific context packet from only the items authorized by that role's frozen read allowlist, in this order:

1. system invariants and the active phase contract;
2. the resolved user command and scope;
3. the exact current formal records required by the phase;
4. role-specific structured summaries and current attention items;
5. user-selected optional context and exact selected history;
6. accepted handoffs from earlier roles in the same run;
7. on-demand references to permitted primary artifacts;
8. the frozen role profile, skills, tools, and knowledge resources.

This sequence is not a grant of access. An item is omitted when the role's allowlist does not authorize it. For the Phase 5 outside reviewer, steps 2 through 7 are represented only by `p5.review_packet`. No project formal record, attention item, selected history, non-reviewer command detail, project memory, or project-specific knowledge resource is injected outside that packet. System invariants and a non-project reviewer profile may accompany it as execution metadata.

Each packet records artifact identities and digests. The sealed run manifest
also binds every contract-selected input and expected output to its exact
executable-contract ID. A prepared context additionally records the formal
inputs and user choices from which the harness constructed it. A mutable current
pointer, unindexed transcript, folder scan, or unstated agent memory is not a
valid scientific input.

The normal context is current and lean. Historical runs are excluded unless the
user selects them or the phase contract names a specific historical object. A
role may inspect a permitted primary artifact when a summary is insufficient,
but the material conclusion must be returned through a structured statement,
evidence item, issue, or handoff.

## 5. Instruction precedence

When instructions conflict, apply this order:

1. system invariants, safety, and access boundaries;
2. the versioned phase contract;
3. the resolved user command within that contract;
4. the role profile and phase instruction;
5. suggestions contained in scientific context.

Scientific evidence does not become weaker because it appears lower in this
instruction order. The order governs actions and scope, not the weight of
evidence. A role must report a scientific conflict rather than following a
lower-level instruction that would conceal it.

## 6. Memory policy

The system distinguishes three kinds of memory.

### 6.1 Run working memory

Run working memory supports reasoning inside one role workspace. It is
diagnostic, run-local, and not a future scientific dependency unless material
content is promoted through a structured output.

### 6.2 Project preference memory

Project preference memory may record stable user choices such as notation,
target audience, biological terminology, computing constraints, or preferred
reporting conventions. It is versioned, visible to the user, and frozen when
used. It cannot change phase scope, method identity, or scientific outcome.

### 6.3 Scientific project memory

Persistent scientific knowledge consists of formal project records, statements,
evidence, attention items, decisions, and handoffs. Free-form chat history and
private agent memory are not substitutes for this record.

No role may silently summarize old runs into persistent memory. A proposed
scientific memory change must pass through the phase submission and promotion
contract.

## 7. Skills, tools, and knowledge resources

A skill provides a method of working, not scientific authority. The profile
manifest names each required skill by stable package identity, version, and
digest. Preparation fails with a precise message when a required skill is
missing. Optional skills are exposed to the user and recorded when selected.

Knowledge resources may include literature indexes, mathematical libraries such
as Mathlib, benchmark collections, optimization problem libraries, biological
ontologies, or approved data catalogs. Each adapter records:

- resource and version;
- query or theorem identifier;
- retrieved item identity;
- retrieval time;
- license or access restriction;
- how the item entered a statement, proof, computation, or decision.

Retrieved content cannot support a formal material claim without provenance.
A library theorem reference does not prove that the role applied it correctly.

Tools are least-privilege capabilities. The profile lists read scope, write
scope, network scope, execution limits, and secrets references. Prompt wording
alone is not a permission boundary.

## 8. Communication between roles

Roles communicate through immutable artifacts and structured handoffs. The producing role writes the handoff inside its role root. After closure, the harness verifies its schema and digest and materializes an immutable shared reference for permitted consumers. A handoff states:

- work completed and material changes;
- exact statements and evidence addressed;
- assumptions and limitations;
- unresolved issues with stable IDs and severity;
- what the next role must verify;
- links to detailed artifacts.

The phase contract controls visibility:

- Phase 1 discovery roles work independently before lead synthesis.
- Phase 2 proposal roles work independently, then exchange explicit
  cross-reviews before lead synthesis.
- Phase 3 proceeds theorist, data analyst, then research lead.
- Phase 4 proceeds data analyst, theorist, then research lead.
- Phase 5 review-revision gives the three parallel roles one frozen manuscript
  snapshot but distinct read allowlists. The theorist receives the mathematical
  internal set, the data analyst receives the empirical internal set, and the
  outside reviewer receives only `p5.review_packet`. The lead receives all fixed
  reports only in the later revision stage.

This provides round-robin scientific awareness without accumulating an
unbounded conversation. A later stage in the same run receives its accepted
handoffs. A later run receives the current formal result and only the handoffs
that a phase contract has explicitly promoted or selected, not every prior
exchange.

## 9. Lead synthesis contract

At the end of each phase run, the research lead produces a structured scientific
record and compact decision brief. The brief must state:

1. the current decision available to the user;
2. the most defensible conclusion;
3. the fundamental methodological or scientific contribution;
4. the material change from the prior current record;
5. the strongest evidence and counterevidence;
6. the main assumption, uncertainty, and unresolved disagreement;
7. the smallest next result that would change the decision;
8. the available user-controlled actions and their consequences.

The language should be compact, direct, and familiar to statistical,
mathematical, computational, and biological researchers. A summary must not
replace the proof, code, evidence, or manuscript it cites.

## 10. Validation requirements

The harness validates that:

- every role plan names an exact stage-compatible profile manifest;
- required output contracts, skills, tools, and knowledge adapters are present and match immutable versions and digests;
- each context item is authorized, frozen, and assigned a purpose;
- selected history matches the user's command;
- each role step freezes the exact stage ID, execution group, input allowlist, output IDs, and unique role-specific write root required by the phase contract;
- completed role workspaces become immutable before later roles read them;
- every required shared handoff resolves to a verified source artifact under the producing role root with the same digest;
- the outside reviewer received only `p5.review_packet` as scientific context and no project-specific memory, knowledge resource, selected history, attention item, or command detail outside it, while the theorist and data analyst received exactly their declared role-specific read sets;
- the lead disposed or preserved every material role issue;
- no formal output depends only on an unindexed transcript or hidden memory.

These checks establish reproducibility and communication discipline. They do not
establish that the role's scientific reasoning is correct.

## 11. Researcher-facing configuration

The configuration UI shows, for each role and phase:

- active profile version;
- scientific stance summary;
- required and installed skills;
- optional knowledge resources;
- tool permissions;
- memory policy;
- project-specific customizations.

A user may create a project-specific profile version. The interface validates it
before use, shows which default was changed, and warns when a required scientific
or operational capability is missing. Customization never grants direct formal
record access.

## 12. Acceptance criteria

Implementation must prove that:

1. two runs with the same frozen profile, prepared contexts, and input allowlists identify the same role inputs even if current project records later change;
2. a missing required skill blocks preparation with the affected role and phase;
3. unselected history and hidden conversation memory are absent from a role
   packet;
4. a completed role artifact cannot be rewritten by a later role;
5. P3 and P4 enforce their fixed role orders and handoffs;
6. the Phase 5 reviewer can resolve only `p5.review_packet` as scientific context and cannot resolve internal formal records, specialist artifacts, project memory, project-specific knowledge resources, selected history, or attention items;
7. a retrieved theorem, paper, dataset, or library object retains provenance;
8. a profile change creates a new version without altering earlier runs;
9. role disagreement remains visible in the lead decision brief;
10. the Web UI and remote client use the same frozen role-profile contract;
11. every role profile is rejected outside its declared `applicable_stage_ids`;
12. unlisted reads and writes outside the role-specific run root are denied at the harness boundary;
13. every harness-owned handoff or submission component resolves to one verified immutable source under a producing role root with the same digest.
