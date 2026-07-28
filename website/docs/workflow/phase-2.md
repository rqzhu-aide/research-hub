---
sidebar_position: 3
title: "Phase 2: Method Development"
slug: /workflow/phase-2
---

# Phase 2: Method Development

## Purpose

Phase 2 builds and maintains a catalog of candidate methods. The team develops
ideas that respond to the literature, states each method precisely enough for
formal study, and records credible alternatives rather than forcing a single
winner.

A valid run publishes the updated catalog. It does not select a method or start
another phase. You choose an active method only when you start Phase 3 or Phase
4.

A current Phase 1 literature result is the preferred basis for this phase. If
you proceed without one, the team should state which novelty and differentiation
questions remain unsupported.

## How the Phase 2 page is organized

The page separates the current scientific record from instructions for new
work.

### Upper panel: current methods

The upper panel always shows the published method catalog. It is empty in a new
project until the first valid Phase 2 run publishes.

For each method, the catalog shows its stable number, name, version, status, and
definition. A method may be:

- **recommended**, **viable**, or **frontier**, all of which remain active and
  can be chosen for a Phase 3 or Phase 4 run;
- **retired**, which remains visible as history but cannot be chosen for a new
  Phase 3 or Phase 4 run.

`recommended` records the research lead's assessment. There may be zero, one,
or several recommended methods. It is not a user selection and does not bind a
later phase.

The published catalog remains visible and unchanged while a Phase 2 run is in
progress.

### Lower panel: instructions and launch

Use the lower panel to state the scientific question for a new run or rerun,
choose the number of rounds, and launch the work. The instructions should say
what needs to be added, reconsidered, or compared. Starting the run does not
select a method and does not start Phase 3 or Phase 4.

## What you decide before launch

State the design problem the team should address:

- the research question, estimand, prediction target, or biological objective;
- the gap or obstacle established by the literature review;
- the statistical or scientific advance a useful method should enable;
- required invariances, validity conditions, interpretability, or uncertainty
  guarantees;
- practical constraints such as sample size, data structure, computation,
  memory, numerical stability, or experimental feasibility;
- whether the run should search broadly or focus on named catalog methods.

Phase 2 uses 2 to 3 rounds, with 2 as the default. In round 1, the roles generate
ideas independently. A later round is useful for comparing mechanisms,
combining compatible ideas, and addressing a named weakness.

On a rerun, refer to existing candidates by their stable method number. For
example:

- "Reassess method #3 under dependent observations and state whether its
  estimand remains identifiable."
- "Develop alternatives that retain the biological interpretation of method #2
  but reduce its computational cost."
- "Compare methods #1 and #4 with the newly identified direct prior work."

## What the team does

### Independent proposals

Each role initially proposes several methods without reading the other roles'
proposals:

- **The theorist** develops mathematical mechanisms, representations,
  identities, or frameworks. Each serious idea should have a precise core
  definition, explicit assumptions, and a coherent reason it could work.
- **The research lead** develops the scientific contribution and positioning.
  The lead asks what the method would make possible, why the result would
  matter, and how it differs from the closest literature.
- **The data analyst** develops the algorithmic and computational structure.
  The analyst describes inputs, operations, outputs, rough complexity,
  numerical risks, and an empirical setting in which the method could be
  evaluated.

### Comparison and refinement

In later rounds, the roles compare their proposals. They may combine compatible
ideas, sharpen definitions, identify contradictions, and propose new candidates
prompted by the comparison. The goal is a stronger catalog, not artificial
consensus.

### Synthesis

The research lead organizes the full idea set and compares the methods using:

- novelty relative to the Phase 1 evidence;
- mathematical and statistical coherence;
- tractability of the required theory;
- computational feasibility;
- potential scientific value;
- empirical testability;
- material assumptions and failure modes.

The lead may mark methods as recommended, viable, frontier, or retired, but
does not choose one for you. The final recommendation concerns the next action:
proceed to Phase 3 or Phase 4, rerun Phase 2, return to Phase 1, or defer
further work.

## How a run updates the catalog

Each run works on an isolated copy of the complete published catalog, including
retired methods. This prevents unfinished agent work from changing what you see
or what another phase can use.

When the run ends:

| Scientific outcome | Effect on the catalog |
|---|---|
| **Complete** | The validated staged catalog becomes the current published catalog. It is ready to satisfy the normal Phase 3 and Phase 4 prerequisite. |
| **Partial** | The validated staged catalog is published, with its scientific gaps recorded. Starting Phase 3 or Phase 4 requires an explicit prerequisite override. |
| **Failed** | The staged catalog is not published. The earlier published catalog remains unchanged. |
| **Cancelled** | The staged catalog is not published. The earlier published catalog remains unchanged. |

For an initial Failed or cancelled run, the published catalog remains empty.

A Complete or Partial result is published automatically after validation. If
the catalog needs improvement, give focused instructions and run Phase 2 again.
Publication does not select a method or start another phase.

## Evidence you receive

The published catalog and run summary should provide:

- a precise mathematical definition or algorithmic specification for each
  serious candidate;
- the proposed novelty and exact relation to the closest literature;
- required assumptions and conditions of validity;
- statistical targets, invariances, or guarantees the method is intended to
  support;
- computational requirements, likely failure modes, and implementation risks;
- testable empirical or biological implications where applicable;
- questions that a Phase 3 theoretical run or Phase 4 empirical run would need
  to resolve;
- disagreements among the roles;
- a comparison with the earlier published catalog;
- methods retained, revised, added, merged, or retired;
- proposed changes to the scientific record;
- one recommended next action: **proceed**, **rerun**, **return to Phase 1**, or
  **defer**, with reasons.

The catalog may contain conjectures. They should be labeled as conjectures and
separated from facts inherited from the literature or already established
results.

For the underlying method and run records, see
[Files and research records](../reference/files-and-records).

## Review checklist

Before using a method or planning a rerun, ask:

- [ ] Is the scientific question, estimand, or prediction target explicit?
- [ ] Does each serious candidate contain enough mathematics or algorithmic
      detail to distinguish it from a general research theme?
- [ ] Are assumptions stated separately from claimed consequences?
- [ ] Is the novelty argument tied to specific Phase 1 evidence?
- [ ] Does the proposed method preserve the quantities or structures it is
      intended to preserve?
- [ ] Are identifiability, approximation, dependence, missingness, or
      distributional conditions addressed when relevant?
- [ ] Are computation, memory, numerical stability, data requirements, and
      implementation risks plausible?
- [ ] For a biological application, does the method respect the measurement
      process, biological variability, study design, and intended
      interpretation?
- [ ] Are central claims stated as testable theoretical or empirical questions?
- [ ] Are important counterexamples and failure regimes visible?
- [ ] Are active methods compared on common criteria without hiding credible
      alternatives?
- [ ] If the outcome is Partial, are the missing work and its consequence for
      Phase 3 or Phase 4 explicit?

## What you can do after publication

### Start Phase 3 or Phase 4 with an active method

Open Phase 3 or Phase 4 and choose any active method in that phase's launch
form. Both pages show the same Phase 2 catalog as a read-only list. Research
Hub freezes the method's stable identity and version for the run. Choosing a
method in one phase does not change the catalog or start the other phase.

If the current Phase 2 publication is Partial, either launch form requires you
to acknowledge the incomplete prerequisite explicitly. You can instead rerun
Phase 2 to resolve the missing work before developing theory or experiments.

### Rerun Phase 2

Rerun when the catalog needs new ideas, a sharper definition, a revised
literature comparison, or a different assessment. The new run starts from the
complete current catalog and can:

- retain a method without changing it;
- revise a method and record a new version;
- add a genuinely distinct method;
- merge methods that represent the same mechanism;
- retire a method with a scientific reason.

Stable method numbers are never reused. Retired and merged identities remain in
the catalog so that earlier work stays interpretable.

### Retire an individual method

You can retire an active method directly from the upper catalog when no project
run is active. Retirement removes it from the Phase 3 and Phase 4 choices but
does not delete its definition, identity, earlier runs, or downstream
artifacts.

Retirement can change the interpretation of later work. Completed downstream
results bound to that method remain available as history, but they no longer
correspond to an active catalog choice. Inspect the affected work and decide
whether to retain it for comparison or rerun the relevant phases.

### Defer

You can leave the catalog unchanged and take no further action. Publication
does not start another phase.

## Rerun guidance

Use a rerun to answer a specific design question, not simply to make the catalog
larger. Ask the team to compare against the current publication and explain:

- what changed in the literature, target, or constraints;
- which methods were retained, revised, added, merged, or retired;
- why each material status or version changed;
- which claims remain unresolved;
- whether the catalog is ready for Phase 3 and Phase 4, or should be improved
  again.

While the rerun is active, the current published catalog remains available. A
Complete or Partial result replaces it only after validation; a Failed or
cancelled run leaves it intact.
