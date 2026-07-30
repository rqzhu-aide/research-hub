---
sidebar_position: 2
title: "Creating a Project"
slug: /project-setup
---

# Creating a Project

A project begins with a research brief. The brief should state the scientific question, the setting in which it will be studied, and the evidence that would justify a decision.

## Define the question before creating the project

Write down:

- the uncertainty you want the research to reduce;
- the population, system, dataset, or mathematical setting;
- the target quantity, prediction task, theorem, or scientific claim;
- the assumptions and exclusions that define the scope;
- the evidence that would support, weaken, or invalidate the proposed direction;
- practical limits on data, computation, time, privacy, or experimentation.

A useful question is precise enough to evaluate but does not prescribe the answer. For example:

> Under the stated sampling assumptions, can the proposed estimator improve uncertainty calibration relative to the specified baselines without sacrificing predictive accuracy?

This identifies a setting, a comparison, and a criterion without assuming that the proposed estimator will succeed.

## Create the project in the Web UI

1. Open [http://127.0.0.1:5055](http://127.0.0.1:5055).
2. Select **New project**.
3. Enter a short, recognizable project name.
4. Write or paste the project brief.
5. Select **Create project**.

Research Hub creates a safe folder name from the project name. The full scientific description belongs in the brief, not in the project name.

## A practical brief template

```markdown
# Project title

## Research question

State the primary question in one or two sentences.

## Scientific setting

Define the population, data, mathematical objects, or experimental system.
State the target quantity, prediction task, or theoretical result.

## Current evidence

Summarize established results, relevant references, available data, and
preliminary observations. Distinguish known facts from working hypotheses.

## Decision criteria

State what evidence would support the proposed direction, what would make the
result inconclusive, and what would rule the direction out.

## Assumptions and constraints

List important assumptions, exclusions, computational limits, data restrictions,
required baselines, and validation requirements.

## Outputs sought

State the results you need, such as a literature assessment, a formal method,
a proof, a simulation study, an empirical analysis, or a manuscript draft.
```

Include only sections that are relevant to the project. For an empirical study, specify the unit of analysis, outcome, candidate predictors or exposures, validation design, and important sources of bias. For a theoretical project, specify the mathematical setting, assumptions, comparison class, and the form of result that would be meaningful.

## What makes the brief useful

A strong brief:

- uses measurable or logically testable criteria;
- separates established evidence from hypotheses;
- names essential baselines or comparison results;
- records assumptions that could limit interpretation;
- states negative results that would still be scientifically informative;
- leaves room for the team to identify an unexpected but defensible direction.

Avoid goals such as "improve the model" or "find a novel method" without defining the quantity to improve, the comparison, and the acceptable evidence.

## Edit the brief when the question changes

Open the project **Overview** and select **Edit brief**. A saved edit applies to future runs.

A run already in progress continues with the version of the brief recorded when you started it. This preserves the scientific context used to produce that run. If the change is material, start a new run so the phase can evaluate the revised question.

## Start and review the first run

Open **Literature Review** and inspect the launch plan. Check the participating
roles, number of rounds, current reference-library baseline, and any direction
you want to add. Start the run only when they match your purpose.

When the run finishes:

1. Read the decision summary and the cited evidence.
2. Inspect important artifacts when a conclusion depends on them.
3. Note unresolved assumptions, missing comparisons, and uncertainty.
4. Decide whether the result is useful for the next question you want to study.
5. If more work is needed, start another run with clearer instructions.

You decide when to start every run or rerun. Completion of one run does not start
another phase. Research Hub assembles verified current records according to the
target phase's storage rule and applies the scope or context choice shown at
launch.

## Files and records

You do not need to manage the project directory during normal use. The Web UI
presents the brief, current record status, run summaries, history, and available
launch choices. For provenance, artifact locations, and immutable records, see
[Files and Records](./reference/files-and-records).

## Next steps

- [Pipeline Overview](./workflow/pipeline)
- [Phase 1: Literature Review](./workflow/phase-1)
- [Roles and Team](./roles)
- [Known Limitations](./known-limitations)
