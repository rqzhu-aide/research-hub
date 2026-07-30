---
sidebar_position: 4
title: "Phase 3: Theoretical Development"
slug: /workflow/phase-3
---

# Phase 3: Theoretical Development

Phase 3 determines which mathematical claims about a method are supported. It
develops the main results, tests the logical structure of the arguments, and
relates those results to computational evidence that Phase 4 can examine or may
already have produced.

A useful Phase 3 result does not need to prove every desired claim. It must
separate proved statements from conditional results, conjectures,
counterexamples, and open questions.

## Before you launch

The current Phase 2 catalog must contain at least one valid active method. The
Phase 3 launch form shows the catalog as a read-only list. Retired or invalid
entries remain visible for context but cannot be selected. Choose an active
method to open its Phase 2 summary, mathematical definition, assumptions,
status, and version before launching.

| Your choice | What to decide |
|---|---|
| **Method to study** | Choose any active method from the current Phase 2 catalog. Compare its definition, version, assumptions, and status before selecting it. |
| **Theoretical focus** | State the central claim, difficult lemma, limiting regime, or assumption class that deserves attention. |
| **Scope of the result** | Say whether you need a full theorem, a rigorous partial result, a counterexample, a complexity analysis, or a precise account of what remains open. |
| **Prior theory context** | Use current records only, or also include archived Phase 3 summaries when they exist. The archive option is disabled for a first run. |

The selected method's canonical definition, stable identity, version, and
`definition_sha256` are frozen for this run. Every team member receives the
same sealed definition. The tuple `stable_id`, `version`, and
`definition_sha256` identifies the exact mathematical object. A later change to
the Phase 2 catalog cannot silently change the object being studied. Selecting
a method here does not alter its Phase 2 status and does not select it for every
future run.

If Phase 2 changes any calculation-defining part of the method, it advances the
version. Proofs for the earlier version remain available as historical records,
but they do not become proofs for the new version automatically. In a rerun,
the theorist and analyst check each carried assumption, lemma, theorem, bound,
and complexity result against the new definition. The replacement theory
manuscript retains only results that survive that check.

By default, the run receives frozen copies of the current same-branch
`theory-manuscript.md` and Phase 4 empirical package when they exist. The new
Phase 3 record states the exact Phase 4 semantic basis available at launch. A
legacy record without this basis stays yellow until Phase 3 is rerun. Phase 4
evidence can challenge an assumption, but it cannot replace a proof.

Each stage keeps its report and any proof supplement, code, data, table, or
figure inside its assigned run folder. Research Hub inventories and hashes these
files when the stage finishes. They remain provenance records, but the next run
does not load every older artifact by default.

A Complete Phase 2 publication satisfies the normal catalog prerequisite. A
Partial publication is visible and its active methods can still be chosen, but
you must explicitly override the incomplete prerequisite before launching
Phase 3. Read the missing-work statement first and explain why theory should
proceed despite that uncertainty.

Your instructions can name claims that must not be made without proof,
assumptions that are scientifically implausible, or computational constraints
that matter for the intended application.

Launching Phase 3 authorizes only this phase. It does not establish its
conclusions, start Phase 4, or prevent you from starting Phase 4 independently.

## What the team does

Phase 3 is a fixed three-stage, cumulative discussion. The theorist performs the
primary mathematical work. The analyst then stress-tests that work, and the lead
prepares the decision summary.

1. **Theorist.** States the mathematical object, assumptions, claims, and
   regimes; derives lemmas and theorems; supplies proofs or explicit proof gaps;
   and records counterexamples and unresolved questions.
2. **Data Analyst.** Reads the theorist's report, checks computability, time and
   memory complexity, numerical stability, edge cases, and empirical
   distinguishability. The analyst identifies hidden assumptions or unsupported
   proof steps and records where the computational analysis agrees or conflicts.
3. **Research Lead.** Reads both reports, checks that each scientific claim has
   an appropriate basis, relates the result to the literature and available
   same-branch empirical evidence, and states the strongest defensible
   conclusion.

All three roles receive the frozen method, current theory manuscript, and
current empirical package when available. If you selected archived summaries,
they also receive that compact Phase 3 context. Within the current run, each
later stage receives the reports from earlier stages. The lead preserves
material objections, responses, and unresolved disagreements rather than
averaging them away. If an earlier role needs to respond again, carry the issue
into a rerun with focused instructions.

## Evidence you should receive

A strong Phase 3 result contains:

1. **A fixed mathematical object.** The frozen method, notation, parameter
   space, estimand or target, and relevant asymptotic regime are defined
   consistently.
2. **Explicit assumptions.** Each assumption is connected to the result that
   uses it. Restrictions with scientific or computational consequences are
   stated plainly.
3. **A result register.** Each important claim is classified as one of:
   - proved under stated assumptions;
   - dependent on a named unresolved step;
   - conjectured;
   - contradicted by a counterexample or calculation;
   - outside the scope of the run.
4. **Proofs and dependencies.** The theorem and lemma statements match their
   proofs, and imported results are cited with their conditions checked.
5. **Computational consequences.** Time, memory, conditioning, stability, and
   implementability are analyzed at the scale relevant to Phase 4.
6. **A discussion record.** Material objections, responses, concessions, and
   unresolved disagreements remain visible across the three ordered stages.
7. **A synthesis for your decision.** The lead states what is established, what
   is not established, and which empirical findings could challenge the
   theory.

Simulation, numerical agreement, or repeated symbolic manipulation is not a
proof. Conversely, failure to complete a proof is not a failed analysis when
the gap and its consequences are identified precisely. A run marked Complete
means that the authorized analysis was completed, not that every theorem is
correct.

## How to read the status

Read method applicability, sibling-basis alignment, and scientific outcome as
separate statements. Exact method applicability says whether the theory refers
to the current `stable_id`, version, and definition digest. Sibling-basis
alignment says whether the recorded Phase 4 context is still the current one.
The Complete, Partial, or Failed outcome describes how much of the authorized
Phase 3 work was completed. None of these statements establishes the others,
and none is a substitute for reading the proofs.

## Review checklist

Before using the result, ask:

- Are the stable ID, version, and definition digest the exact method you
  intended to study?
- Are the object of study, quantifiers, probability statements, and limiting
  regime unambiguous?
- Are all assumptions stated before they are used, and are they plausible for
  the intended statistical, machine-learning, mathematical, or biological
  setting?
- Does every theorem say exactly what its proof establishes?
- Are boundary cases, identifiability conditions, regularity conditions, and
  failure regimes addressed?
- Are citations to external theorems accurate, and are their hypotheses
  verified here?
- Are proof gaps labeled as gaps rather than hidden in phrases such as
  "standard" or "straightforward"?
- Does the computational analysis use the same frozen method and
  parameterization as the mathematical analysis?
- Are theoretical predictions stated in a form that Phase 4 can measure without
  treating empirical agreement as mathematical validation?
- Does the lead's summary narrow claims when the proof or computation is
  incomplete?

For a central or delicate theorem, human mathematical review remains important.
The team's cross-check can expose errors, but it is not a formal proof
verification guarantee.

## How to use the result

A valid Complete Phase 3 run publishes one self-contained current
`theory-manuscript.md` for the selected method. Read it with the run summary,
role reports, and supporting artifacts before deciding whether the theory is
adequate for your intended use.

### Use it in later work

The current theory manuscript is supplied to later same-branch Phase 3 and Phase
4 runs. Phase 4 does not require Phase 3 and can be launched directly from the
Phase 2 catalog. When compatible theory is available, the Phase 4 team can use it
to define diagnostics and interpret results. Availability does not certify a
proof or require later work to rely on it.

### Rerun Phase 3

Start another Phase 3 run when you want a different proof strategy, a stronger
or weaker assumption class, a corrected theorem, a more explicit proof step, a
new theoretical target, or a fresh analysis after the literature or method
catalog changed. Choose an active method in the launch form and state exactly
what the team should retain, challenge, or reconsider.

Each rerun freezes the current method, theory manuscript, and Phase 4 basis. A
valid Complete result replaces the theory manuscript with a self-contained
version and records that basis. If its scientific content changes, Phase 4 can
become yellow. You decide whether to rerun Phase 4; nothing starts automatically.
Older runs remain provenance, not working theory versions.

When the selected method version changed, use the rerun to judge the old
arguments under the new mathematical definition. The amount of repair may be
small or substantial, but the new current manuscript must state the complete
valid theory for the exact new version.

### Return to another phase

Return to Phase 2 when the method definition itself must change. Start or rerun
Phase 4 when an empirical test could distinguish competing explanations, expose
a failure regime, or evaluate a theoretical prediction. You decide when to
start either run.

## Use in Phase 5

Phase 5 requires a usable current result from each of Phases 1 through 4. The
current Phase 3 theory package must have scientific outcome Complete. The
Phase 3 and Phase 4 results must match the selected method and each other's
recorded semantic basis. Phase 4 can have no outdated or unresolved evidence.
Phase 3 alone does not make the branch ready or start Phase 5.

If the Phase 2 catalog later revises, merges, or retires the method, its earlier
Phase 3 run record remains interpretable. The current theory package no longer
matches a calculation-changing revision. Rerun Phase 3 before treating the
branch's theory as current for that version. A status or prose-only Phase 2 edit
that leaves the authoritative mathematical definition and version unchanged
does not invalidate the theory package.

If a newer Phase 3 result materially changes an assumption or conclusion,
recheck Phase 4 or Phase 5 material that relied on the earlier theory. The
original result remains preserved with its original context.

For artifact names, run records, and branch layout, see
[Files and records](../reference/files-and-records).
