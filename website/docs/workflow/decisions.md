---
sidebar_position: 2
title: "Review Results and Choose What Happens Next"
slug: /workflow/decisions
---

# Review results and choose what happens next

Research Hub leaves scientific judgment and control with you. A completed run
makes its summary and supporting material available for inspection. It does not
establish that the result is correct, start another run, or commit you to a
particular research direction.

After reading the result, you decide whether to use it as context, rerun the
phase with new direction, start another eligible phase, or stop.

## What completion means

A completed status means that the requested team workflow finished and
submitted its output. It does not mean that:

- every claim is supported;
- every disagreement is resolved;
- the method is worth pursuing;
- later work should rely on the result; or
- another phase should start.

Treat the summary as a guide to the run, not a substitute for the underlying
proofs, sources, code, diagnostics, and experimental results.

## Inspect the scientific material

Begin with the phase summary, then inspect the evidence needed to assess the
consequential claims. Ask:

1. **What was actually examined?** Compare the completed work with the scope,
   method, run settings, and direction supplied at launch.
2. **What is supported?** Separate established facts, new results, conjectures,
   failed attempts, and recommendations.
3. **What remains uncertain?** Identify missing sources, unresolved
   disagreements, untested assumptions, failed analyses, and weak
   generalization.
4. **What could use this result?** Apply greater scrutiny when it will inform a
   method choice, theorem claim, primary experiment, or manuscript conclusion.
5. **What changed?** On a rerun, compare the new result with the earlier
   material and identify both retained and revised conclusions.

Each phase guide provides a specific review checklist:

- [Phase 1: Literature Review](./phase-1)
- [Phase 2: Method Development](./phase-2)
- [Phase 3: Theoretical Development](./phase-3)
- [Phase 4: Implementation and Experiments](./phase-4)
- [Phase 5: Paper Assembly and Review](./phase-5)

## Choose the next action

| Action | Choose it when | Effect |
|---|---|---|
| **Let the result inform later work** | The material is relevant and sufficiently reliable for the next question you want to study. | Eligible material is assembled automatically for later runs. Inspect the context shown before launch; Research Hub freezes what the run receives. |
| **Rerun the phase** | A new pass could resolve a gap, test a changed assumption, use new evidence, or examine a different scope. | A new run is created. Earlier runs remain available for comparison. |
| **Start another eligible phase** | The available evidence is sufficient for that phase's purpose and its required conditions are satisfied. | Only the phase you explicitly start will run. |
| **Stop or defer** | The evidence is insufficient, the direction is not useful, or no further work is currently warranted. | Nothing else starts. The completed material remains available for later inspection. |

These choices are not mutually exclusive over the life of a project. A result
can inform later work, the same phase can be rerun, and an earlier question can
be reopened when new evidence warrants it.

## Review the assembled context

Before launch, inspect the context shown in the run form. The current release
assembles eligible prerequisite and same-branch material automatically. The
launch form does not yet let you include or exclude individual prior results.
If the assembled context is unsuitable, do not launch until you have rerun the
relevant phase, chosen another method where applicable, or narrowed the new
run's question and instructions. Required inputs and integrity checks cannot be
removed.

Research Hub copies and hashes the context used by the run. Later edits to live
project files do not silently change a run that is already active or completed.
The preserved record therefore shows which evidence was available to that run,
but it does not certify the scientific validity of that evidence.

When a newer result changes an assumption, method definition, dataset,
implementation, or conclusion used by earlier work, inspect the affected
downstream material again. The earlier result remains part of the history. You
decide whether the change is immaterial, whether a focused rerun is sufficient,
or whether a broader investigation is needed.

## Rerun with a specific purpose

A useful rerun states what should be reconsidered and what evidence could
change your next decision. Appropriate reasons include:

- the research question or scope changed;
- new literature, data, or assumptions alter the evidence;
- a later phase exposed a gap in earlier work;
- the candidate method or evaluation design changed;
- a derivation, implementation, or comparison needs a focused check; or
- the earlier run was too incomplete to support the intended use.

Give observable direction. For example:

- "Compare the estimand and assumptions directly with Smith et al., and state
  whether the originality claim survives that comparison."
- "Check whether the rate requires strong convexity or only a spectral gap.
  Provide either a proof or a counterexample."
- "Repeat the benchmark with independent repetitions, uncertainty intervals,
  and the number of observations reported for every condition."
- "Restrict the manuscript claim to the population and conditions supported by
  the theoretical and empirical results."

Avoid instructions such as "make it better" or "do more analysis." Name the
claim, evidence, calculation, experiment, or explanation that should change.

## Method choices after Phase 2

Phase 2 publishes the current catalog of candidate methods. From the Phase 2
page, you may rerun method development or retire an individual method. Retiring
a method removes it from future selections without deleting its definition,
branch, or run history.

Phase 3 and Phase 4 each display the active catalog as a read-only list. When
starting either phase, you choose one active method. The run freezes that
method's stable ID, version, and definition and writes to its durable branch.
Either sibling phase can run first, and either can be rerun independently.

## Conditions for later phases

Phase 1 has no prerequisite. Phase 2 can use available Phase 1 evidence.
Phase 3 and Phase 4 require an active Phase 2 method, but neither requires the
other to have run.

Phase 5 has stricter conditions. It requires an intact completed result from
each of Phases 1 through 4. The Phase 3 and Phase 4 results must match the same
selected method stable ID, version, and definition digest. These integrity and
method-matching requirements cannot be overridden.

Meeting a launch condition does not determine whether starting the phase is
scientifically appropriate. It only establishes that the required records are
available and consistent. You still decide whether to start the run.

## No automatic progression

Every run and rerun requires a separate action from you. Completing a phase
does not start another phase, select a method, retire a method, or schedule a
rerun.

Only one run can be active in a project at a time. Separate projects can be
managed independently.

For the records retained after runs and reruns, see
[Files and research records](../reference/files-and-records).