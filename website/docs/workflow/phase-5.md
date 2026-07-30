---
sidebar_position: 6
title: "Phase 5: Paper Assembly & Review"
slug: /workflow/phase-5
---

# Phase 5: Paper Assembly & Review

Phase 5 turns the completed literature, method, theory, and empirical evidence
into a coherent manuscript. It also provides a context-separated internal review
and a revision step when you choose that mode.

This internal review is not external peer review. It does not replace review by
human coauthors, domain experts, statisticians, journal referees, or other
specialists required by the study.

## Before you launch

Phase 5 requires a usable current record from each of Phases 1 through 4. Its
launch form uses the Phase 2 catalog to identify the selected method.

For that method, the recorded Phase 2 literature basis must match both the
current Phase 1 reference collection and the current literature synthesis.
Research Hub uses the method's own review-source run as the Phase 2 prerequisite,
not simply the newest Phase 2 run in the project. This matters after a focused
Phase 2 run, because the newest run may have reviewed a different method.

The current Phase 3 theory and Phase 4 empirical packages must match the method
and the decision-relevant sibling conclusions and evidence recorded by each
phase. Phase 4 must have no outdated or unresolved evidence. Research Hub
rebuilds this alignment before launch.

A usable current Phase 1 record, the selected method's Phase 2 review, and its
Phase 4 result may have scientific outcome Complete or Partial. A current Phase
3 theory package must have outcome Complete. A Failed result never qualifies.
Partial means that the retained result has scientific limitations; it does not
mean that a technically failed run was accepted.

Research Hub does not combine theory for one method with empirical results for
another, and a result bound to an older method definition does not silently
satisfy the current branch.

Phase 5 fixes the exact current Phase 1 reference collection and literature
synthesis at launch. It also reads the current method definition, complete
current theory manuscript, current empirical synthesis and evidence index, and
their verified supporting artifacts. The method's definition source and review
source may be different runs. Older run summaries remain provenance records,
but they are not substitutes for the current packages.

If the selected method's Phase 2 literature status is yellow, Phase 5 is
unavailable until you choose a full-catalog or focused Phase 2 rerun that reviews
that method against the current Phase 1 basis. If the method is retained without
a definition change, matching Phase 3 and Phase 4 results remain aligned. If the
definition changes, Phase 3 and Phase 4 require review against the new
definition.

Phase 5 is also unavailable if either Phase 3 or Phase 4 is yellow. A yellow
Phase 5 manuscript means that one of its recorded inputs changed and it may need
Assembly or, when the current manuscript remains valid, Review & Revision. A red
record has an integrity failure. No status launches a run. You explicitly
choose whether to run or rerun any phase.

| Choice | When to use it | Who works |
|---|---|---|
| **Assembly** | Usable current results from Phases 1 through 4 have not yet been combined into one manuscript, or that evidence has changed substantially. The Phase 3 and Phase 4 results match the selected method snapshot. | Research Lead |
| **Review & Revision** | The branch has a verified current `manuscript.md` that you want independently reviewed and revised. | Paper Reviewer, then Research Lead |

In your launch instructions, identify the intended audience or venue, the claims
that need particular scrutiny, sections that remain uncertain, and any reporting
standards relevant to the statistical, machine-learning, mathematical, or
biological application.

Launching Phase 5 starts only the selected run. It does not determine that the
manuscript is ready for submission, submit it, or initiate any outside review.

## What the team does

### Assembly

The Research Lead prepares one manuscript from the compatible branch evidence:

- the Introduction motivates the problem and positions the contribution using
  the literature record;
- the Method section states the selected method precisely;
- the Theory section reports only results supported by Phase 3, with assumptions
  and unresolved claims preserved;
- the empirical sections use the implementation, protocol, measurements, and
  uncertainty from Phase 4;
- the Discussion separates conclusions, limitations, and open questions.

The lead reconciles notation, aligns claims with evidence, preserves negative
results, and combines the references. Assembly does not include a reviewer
stage.

### Review & Revision

This mode uses the branch's verified current manuscript:

1. **Context-separated internal review.** The Paper Reviewer uses a separate
   Hermes profile and evaluates the assembled manuscript for soundness, clarity,
   significance, originality, evidential support, and reporting completeness.
   The reviewer ranks the issues and recommends specific changes.
2. **Revision.** The Research Lead addresses every material point. The lead may
   correct it, revise the claim, defer it with a reason, or disagree with a
   scientific justification. The run replaces the branch's one current
   `manuscript.md`, records the response, and writes an exact
   `manuscript-post-review.diff`.

The separate reviewer profile reduces direct carryover from the authoring
conversation. It does not make the reviewer external or fully independent, and
it does not guarantee that the review identifies every error.


## Evidence you should receive

### From an assembly run

- a complete manuscript with consistent notation and definitions;
- claims traceable to the recorded literature, theory, and empirical evidence;
- limitations, negative results, and unresolved theoretical statements retained
  in the paper;
- a coherent bibliography and sufficient methodological detail for the intended
  audience.

### From a Review & Revision run

- a structured internal review with issues ranked by scientific importance;
- a response or disposition for every material review point;
- an updated current `manuscript.md`;
- an exact record of changes from the reviewed manuscript;
- clear labeling when a changed post-review manuscript has not itself received
  another review.


## Review checklist

Before using an assembly or revision, ask:

- Is the central contribution stated precisely and consistently across the
  abstract, introduction, results, and discussion?
- Is every important claim supported by a theorem, empirical result, cited
  source, or clearly identified interpretation?
- Are conjectures, incomplete proofs, exploratory analyses, and post-protocol
  deviations labeled accurately?
- Do the theorem statements, assumptions, and proof scope agree with Phase 3?
- Do numerical and empirical claims report sample size, replication,
  uncertainty, missingness, and relevant sensitivity analyses from Phase 4?
- Are baseline comparisons fair and are negative or inconclusive findings
  visible?
- Are the data, code, computational environment, and reproduction steps
  described to the extent that access permits?
- For biological work, are the experimental unit, biological replication,
  technical replication, batches, confounders, and biological interpretation
  reported correctly?
- Are ethics approval, consent, data governance, conflicts of interest, funding,
  and data or code availability statements included when relevant?
- Does the review distinguish errors that can be fixed in the manuscript from
  evidence gaps that require returning to an earlier phase?
- Does the revision record show how every major concern was handled?
- If the manuscript changed after review, is it clear that the changed text has
  not automatically been reviewed?

Human authors remain responsible for factual accuracy, mathematical correctness,
authorship, citations, research ethics, journal compliance, and the decision to
submit.

## How to use the result

Every Phase 5 run produces a separate sealed record. Read the manuscript,
supporting reports, internal review when present, and revision record before
choosing the next run or using the manuscript outside Research Hub.

### After assembly

Use Assembly again when upstream evidence changed, notation or claim alignment
needs correction, or the manuscript needs a different scientific structure.
State the required changes in the new run instructions. The prior Assembly
remains available for comparison.

Assembly writes the complete result to the run's `manuscript.md`. After a valid
Complete run, Research Hub makes it the branch's one current manuscript. You can
then start Review & Revision directly, rerun Assembly after upstream changes, or
defer further work.

### After Review & Revision

Use the revised manuscript and revision record to decide whether to run another
paper-stage assessment, return to an earlier research phase, or seek human
review. Return to Phase 1, 2, 3, or 4 when the review identifies a literature,
method, proof, implementation, or empirical gap that cannot be repaired through
writing.

If important text changed during revision, consider another Review & Revision
run on the current manuscript or seek independent human review before submission.

## Reruns and downstream effects

A change in the Phase 1 reference collection or literature synthesis makes both
the selected method's Phase 2 literature status and the current manuscript
yellow. Before starting another Phase 5 run, review that method in a full-catalog
or focused Phase 2 run. If its definition remains unchanged, this updates the
literature basis without requiring Phase 3 or Phase 4 to be rerun. If the
definition changes, bring both downstream records into alignment before Phase 5.

The interface distinguishes the reference collection from the synthesis so you
can judge whether the paper's citations, positioning, or claims need revision.
A manuscript created before Research Hub recorded the collection identity is
also yellow. It remains yellow unless Phase 5 is rerun, but you may inspect it
and defer. No yellow status starts a rerun.

Every rerun creates a separate sealed run record. The newest valid Complete
result becomes the branch's one current manuscript. Earlier summaries, reviews,
and diffs remain available for provenance and comparison.

Research Hub does not submit a Phase 5 manuscript or represent it as accepted,
published, externally reviewed, or verified.

You may start another Review & Revision run whenever the branch has a verified
current manuscript and the Phase 1 to Phase 4 launch conditions remain satisfied.

For artifact names, run records, manuscript variants, and branch layout, see
[Files and records](../reference/files-and-records).
