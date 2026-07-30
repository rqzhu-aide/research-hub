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
choose the catalog scope and number of rounds, and launch the work:

- **Full catalog** may add, revise, merge, retain, or retire methods.
- **Focus on one method** may revise only the selected active method. It cannot
  add, remove, rename, merge, or retire methods, and all nonselected entries must
  remain unchanged.

The focused option is unavailable until the catalog contains an active method.
The instructions should say what needs to be added, reconsidered, or compared
within the selected scope. Starting the run does not choose a method for a later
phase and does not start Phase 3 or Phase 4.

## How Phase 1 evidence is attached to each method

At launch, Research Hub fixes the exact current Phase 1 reference collection and
literature synthesis for the run. Later changes to Phase 1 cannot alter that
active run.

After a validated Complete or Partial publication, Research Hub writes
system-managed provenance for each method covered by the selected scope:

| Record | Meaning |
|---|---|
| **Definition source** | The Phase 2 run that last changed the exact current method definition. |
| **Review source** | The most recent Phase 2 run that assessed the method against its recorded Phase 1 basis. |
| **Literature basis** | The exact Phase 1 reference collection and literature synthesis assessed in that review. |

The team provides the scientific assessment. Research Hub calculates the method
identity and writes these provenance fields. The agents do not maintain them.

A full-catalog run reviews every catalog entry and advances its review source
and literature basis, including entries retained without a definition change. A
focused run reviews only the selected method. Every nonselected method keeps its
earlier review source and literature basis.

The definition and review sources may therefore differ. If a method is retained
without a definition change, its review source advances but its definition
source does not. Matching Phase 3 and Phase 4 records remain aligned because the
method definition is unchanged.

## When a method version changes

Every method file has one authoritative `## Mathematical definition` section.
This section contains all material that determines the calculation, such as the
estimator or objective, algorithm or update rule, tuning definition,
normalization, and any assumption that changes a computed quantity. Research
Hub calculates `definition_sha256` from this section.

Advance the version whenever that mathematical content changes in a way that
can change a calculation. Keep the version unchanged when a rerun changes only
the method's status, literature comparison, explanatory prose, downstream
research questions, or formatting outside the authoritative section. Leave
that section exactly unchanged when retaining the version. Research Hub rejects
a changed definition published under the same version.

Downstream work uses the exact tuple `stable_id`, `version`, and
`definition_sha256`. If a new version changes the calculation, earlier Phase 3
proofs and Phase 4 method-dependent computations remain available as history,
but they are not current support for the new version. You decide whether to
rerun Phase 3, Phase 4, or both. During a rerun, the team judges how much of the
earlier reasoning or study can be reused after checking it against the new
definition.

If Phase 1 later changes, the interface marks the affected method's Phase 2
literature status yellow until that method is reviewed again. A method published
before this basis was recorded is also yellow. Yellow means that the literature
comparison needs review; it is not a claim that the method is invalid. You may
choose a full-catalog rerun, a focused rerun, or no immediate action. No status
starts a run.

Phase 5 is unavailable for a selected method while this Phase 2 literature
status is yellow or cannot be verified.

## What you decide before launch

State the design problem the team should address:

- the research question, estimand, prediction target, or biological objective;
- the gap or obstacle established by the literature review;
- the statistical or scientific advance a useful method should enable;
- required invariances, validity conditions, interpretability, or uncertainty
  guarantees;
- practical constraints such as sample size, data structure, computation,
  memory, numerical stability, or experimental feasibility;
- how the selected catalog scope should be used.

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

In full-catalog mode, each role initially proposes several methods without
reading the other roles' proposals:

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
In focused mode, each role instead develops several concrete repairs, variants,
or stress tests for the selected method. These alternatives inform one revised
method entry; they do not create additional catalog entries.


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

In full-catalog mode, the lead may mark methods as recommended, viable, frontier,
or retired. In focused mode, the lead may update only the selected active method
and must preserve every nonselected file exactly. The lead does not choose a
method for you. The final recommendation concerns the next action: proceed to
Phase 3 or Phase 4, rerun Phase 2, return to Phase 1, or defer further work.

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
- [ ] Is there one authoritative mathematical definition, and does the version
      advance exactly when its calculation changes?
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
literature comparison, or a different assessment. Every rerun starts from an
isolated complete copy of the current catalog.

Choose **Full catalog** when the run may:

- retain a method without changing it;
- revise a calculation-defining method and record a new version;
- revise only status, positioning, or explanation without changing the version;
- add a genuinely distinct method;
- merge methods that represent the same mechanism;
- retire a method with a scientific reason.

Choose **Focus on one method** when only one active method needs repair or
refinement. The selected method may receive a new version, but its stable ID is
preserved. A new version is required only for a calculation-defining change.
Every other method must remain byte-for-byte unchanged, and the run cannot
change catalog membership.

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
larger. Ask the team to compare against the current publication and explain the
changes allowed by the selected scope:

- what changed in the literature, target, or constraints;
- for a full-catalog run, which methods were retained, revised, added, merged,
  or retired;
- for a focused run, what changed in the selected method and why;
- why each material status or version changed;
- which claims remain unresolved;
- whether the catalog is ready for Phase 3 and Phase 4, or should be improved
  again.

While the rerun is active, the current published catalog remains available. A
Complete or Partial result replaces it only after validation; a Failed or
cancelled run leaves it intact.
