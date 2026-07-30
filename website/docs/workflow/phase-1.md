---
sidebar_position: 2
title: "Phase 1: Literature Review"
slug: /workflow/phase-1
---

# Phase 1: Literature Review

## Purpose

Phase 1 determines what is already known, what the proposed research can
legitimately build on, and where the important uncertainty remains. Its purpose
is not to produce a long bibliography. It is to establish an evidence base from
which you can judge the contribution and design the next stage of the research.

No earlier phase is required. You can use Phase 1 for an initial survey or for
a focused update at any point in the project.

## The decision this phase supports

After reviewing the result, you should be able to decide:

- whether the closest prior work has been identified;
- whether the proposed contribution is stated precisely enough to compare with
  that work;
- which mathematical and scientific foundations can be reused;
- which implementations, datasets, and evaluation practices already exist;
- which originality or contribution statements are supported, qualified,
  contradicted, or still unresolved;
- whether the evidence is adequate for method development.

The team may recommend proceeding, improving the literature review, or
reconsidering the research direction. The recommendation informs your decision
but does not replace it.

## What you decide before launch

Choose the scope of the run.

### Initial survey

Use an initial survey when the project is new or the surrounding field has not
yet been mapped. State, as clearly as possible:

- the research question, estimand, or prediction target;
- the proposed method, mechanism, or representation;
- the anticipated statistical, mathematical, computational, or biological
  advance;
- the population, data-generating setting, or biological system of interest;
- the conditions under which the advance is expected to hold.

Unclear items can be included as questions for the team.

### Focused literature update

Use a focused update when a particular uncertainty has emerged. Name the gap,
such as:

- a possible overlap with a newly found paper;
- a theorem or assumption that needs source verification;
- an unfamiliar method family that may contain a direct precedent;
- an implementation that may already realize part of the proposed method;
- a biological setting or dataset that was absent from the initial review.

Select 1 to 5 rounds, with 2 as the usual starting point. A later round is most
useful when the first round identifies a specific conflict or missing source
that another targeted search can resolve.

Use the direction field to state what deserves emphasis. Do not direct the team
toward a preferred conclusion. Ask for evidence that could support or weaken
the proposed contribution.

## What the team does

In the first round, three roles examine the literature independently:

- **The theorist** compares the proposed mathematical object, estimand,
  identity, algorithm, and guarantee with primary theoretical results. The
  theorist records assumptions, proof dependencies, counterexamples, and
  failure regimes.
- **The research lead** identifies the closest scientific contributions and
  evaluates the proposed positioning. The lead distinguishes importance from
  originality and asks what claim remains defensible after comparison with
  prior work.
- **The data analyst** examines existing implementations, benchmark practice,
  datasets, computational costs, and evaluation protocols. The analyst checks
  whether software or empirical practice already implements the claimed
  advance.

In later rounds, the roles compare their findings. They investigate named
disagreements, follow backward and forward citations, test alternative search
terms, and close consequential evidence gaps. Repeating the same broad search
is not a useful additional round.

The research lead then produces an evidence-weighted synthesis. A conflict
between roles should remain visible unless a source or argument resolves it.

## Literature evidence standard

Judge the Phase 1 result by the quality and relevance of its evidence, not by
the number of references.

### Define the comparison precisely

The review should distinguish:

1. **Direct prior work:** the same target, construction, formula, estimand, or
   scientific conclusion for the same purpose.
2. **Theoretical foundations:** established results that the project can use
   but should not present as new.
3. **Related methods:** similar mathematical or computational ideas used for a
   different target, setting, or scientific purpose.
4. **Existing implementations:** code, packages, analysis procedures, datasets,
   or benchmarks that implement part or all of the proposed approach.

Shared vocabulary or similar notation is not sufficient to establish
equivalence. The comparison should examine the actual target, mathematical
definition, assumptions, computation, and intended use.

### Prefer evidence close to the claim

Use primary papers for scientific and mathematical claims, original
repositories for software claims, and official documentation for documented
behavior. A review article can orient the search but should not be the sole
support for a central comparison.

For a theorem or guarantee, record the exact result and its assumptions. For an
algorithm, record the operative computation and target. For an empirical or
biological claim, record the study population or model system, data source,
outcome, design, sample size where relevant, and uncertainty. Check whether
apparently similar findings depend on different measurements, interventions,
or validity conditions.

### Make the search reproducible

The report should preserve a compact search account containing:

- databases, indexes, repositories, or other sources searched;
- search dates;
- query families, formulas, and important synonyms;
- backward and forward citation paths;
- software and implementation searches;
- restrictions on language, date, venue, population, or study type;
- the stopping rule.

A defensible stopping rule is evidence saturation: further targeted searches
no longer change the closest-work set, the contribution boundary, important
assumptions, or material uncertainty.

### Calibrate negative and originality statements

Failure to find a paper is not proof that none exists. Use language such as
"not found within the searched scope," followed by the scope and remaining
uncertainty. Treat unresolved overlap as unresolved. Do not convert a narrow or
unsuccessful search into a claim of originality.

Check the current status of central sources when possible, including corrections
or retractions that affect the result being used.

## Evidence you receive

The final summary should give you:

- a short decision brief;
- a precise statement of the candidate contribution and its validity
  conditions;
- the searched scope and stopping rule;
- a classified evidence table for direct prior work, foundations, related
  methods, and implementations;
- the closest overlapping work and the exact basis for comparison;
- source quality and uncertainty for each material conclusion;
- differences among the three role assessments;
- coverage gaps and questions for a focused update;
- proposed changes to the scientific record;
- one recommendation: **proceed**, **improve literature**, or **reconsider
  direction**, with reasons.

Source-level notes and run records remain available for checking the synthesis.
See [Files and research records](../reference/files-and-records).

## Review checklist

Before making a decision, ask:

- [ ] Is the research question, target, contribution, and scope stated
      precisely?
- [ ] Does the search cover the method names, mathematical formulations,
      scientific synonyms, and application terminology that a close precedent
      might use?
- [ ] Are central comparisons based on primary sources rather than titles,
      abstracts, or secondary summaries alone?
- [ ] Does each claimed precedent identify the same or different target,
      assumptions, computation, and purpose?
- [ ] Are foundational results separated from genuinely new claims?
- [ ] Are available code, datasets, benchmarks, and standard evaluation
      practices represented?
- [ ] For empirical or biological evidence, are the population, model system,
      measurement, design, and generalizability relevant to this project?
- [ ] Are negative findings limited to the searched scope?
- [ ] Are disagreements, missing sources, and uncertain classifications
      visible?
- [ ] Does the recommendation follow from the evidence and state what remains
      at risk?

## Inspect the result and choose the next action

A valid Phase 1 run adds its new unique sources to the cumulative reference
library and replaces the current literature synthesis. The source cards are not
regenerated or removed on later runs. Completion does not certify the literature
conclusions or require later work to rely on them.

| Action | Use it when | Direction to provide |
|---|---|---|
| **Use the result as context** | The evidence is broad and precise enough for the next question, and its important uncertainties are explicit. | Record any known gaps that later work must not treat as resolved. |
| **Rerun Phase 1** | The scope changed, new literature appeared, a later phase exposed an overlap, or the existing search cannot support the intended use. | State the new search question, likely terminology or citation path, and what evidence would change your judgment. |
| **Pause or redirect the project** | The evidence does not support the current direction or another question now has higher priority. | Preserve the useful findings and state why no immediate follow-up is warranted. |

See [Review results and choose what happens next](./decisions) for the general
control model.

## Consequences for later phases

A Phase 2 run uses Phase 1 to avoid reproducing known work, separate a new
mechanism from established ingredients, and define comparisons for theory and
experiments. At launch, Research Hub fixes the exact reference collection and
literature synthesis that the Phase 2 team will assess.

For each method covered by a valid Complete or Partial Phase 2 publication,
Research Hub records that Phase 1 basis and distinguishes:

- the **definition source**, which is the run that last changed the exact method
  definition; and
- the **review source**, which is the most recent Phase 2 run that assessed the
  method against its recorded Phase 1 basis.

A full-catalog Phase 2 run updates the review source and literature basis for
every catalog entry, including a method retained without change. A focused run
updates only the selected method. Nonselected methods retain their earlier
review sources and literature bases.

When a new Phase 1 result changes the reference collection or synthesis, the
Phase 2 literature status becomes yellow for each method whose recorded basis
no longer matches. Yellow means that the literature comparison has not yet been
reviewed against the new evidence. It does not imply that the method definition
is wrong, and it does not by itself make matching Phase 3 or Phase 4 work
yellow.

You decide whether to run Phase 2 for the full catalog, focus on one method, or
defer. No status starts a run. If the team retains a method without changing its
definition, the review source and literature basis advance while the definition
source remains unchanged. This clears the Phase 2 literature signal for the
covered method without invalidating matching Phase 3 or Phase 4 results. If the
method definition changes, those downstream results require review against the
new definition.

Phase 5 requires the selected method's Phase 2 literature basis to match the
current Phase 1 record. Phase 5 also records the exact reference collection and
literature synthesis as separate manuscript inputs. Adding one unique reference
therefore makes an existing manuscript yellow even if the synthesis text is
unchanged. Earlier Phase 1 runs remain provenance records; the current library
and synthesis are the normal basis for new work.

## Rerun guidance

Rerun Phase 1 with a named purpose. The team searches against the current
cumulative library and produces a delta containing only new unique references.
Research Hub rejects repeated reference identities before promotion. The lead
rewrites the compact current synthesis to reflect the complete expanded library.
A useful rerun should make clear:

- which part of the contribution or scope changed;
- which sources or search paths are new;
- which current conclusions remain supported;
- which conclusions changed because of the new evidence;
- whether the new evidence changes the recommendation for Phase 2.

Prior runs remain part of the provenance record, but new runs do not need to
repeat their references.
