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

Phase 5 requires an intact completed result from each of Phases 1 through 4.
Its launch form uses the Phase 2 catalog to identify the selected method. The
Phase 3 and Phase 4 results must both match that method's stable ID, version,
and definition digest. Research Hub verifies the integrity of all four results
and the sibling branch match before launch.

It does not combine theory for one method with empirical results for another,
and a result bound to an older method version or definition does not silently
satisfy the current branch.

Available summaries, role reports, and supporting evidence from both sibling
phases are included as same-branch evidence. A Phase 3 or Phase 4 result must
have a complete artifact inventory to satisfy this strict gate. Older records
created before complete artifact tracking remain visible as advisory history,
but the affected phase must be rerun before Phase 5. The same applies when a
required result is missing, fails its integrity check, or is incompatible with
the selected method.

| Choice | When to use it | Who works |
|---|---|---|
| **Assembly** | Intact completed results from Phases 1 through 4 have not yet been combined into one manuscript, or that evidence has changed substantially. The Phase 3 and Phase 4 results match the selected method snapshot. | Research Lead |
| **Review & Revision** | A same-branch Assembly run already has the legacy `approved` status required by the current launcher. The phase panel does not create this status; see [Current Limitations](../known-limitations). | Paper Reviewer, then Research Lead |
| **Review target** | The selector is shown and you want a fresh assessment of one exact sealed post-review manuscript without revising it in the same run. | Paper Reviewer only, in two stages |

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

The intended sequence is review followed by revision. The current launcher
still requires a same-branch Assembly run with legacy `approved` status. The
phase panel does not provide an approval action, so this mode is not normally
available after a newly completed Assembly run. See
[Current Limitations](../known-limitations).

When the legacy gate is satisfied:

1. **Context-separated internal review.** The Paper Reviewer uses a separate
   Hermes profile and evaluates the assembled manuscript for soundness, clarity,
   significance, originality, evidential support, and reporting completeness.
   The reviewer ranks the issues and recommends specific changes.
2. **Revision.** The Research Lead addresses every material point. The lead may
   correct it, revise the claim, defer it with a reason, or disagree with a
   scientific justification. The run produces a revised manuscript and a
   revision record.

The separate reviewer profile reduces direct carryover from the authoring
conversation. It does not make the reviewer external or fully independent, and
it does not guarantee that the review identifies every error.

### Review target

The **Review target** selector has a narrower current behavior than Review &
Revision:

- It lists completed prior Phase 5 runs that contain a valid, sealed
  `manuscript-post-review.md` artifact. It does not select the `manuscript.md`
  produced by a standard assembly run.
- The selected manuscript and its hash are preserved as the exact object of
  review.
- The Paper Reviewer first records a first-reader assessment using only that
  sealed manuscript.
- The Paper Reviewer then compares the preserved first reading with the internal
  scientific record.
- No Research Lead revision occurs in this review-target run, and the selected
  manuscript is not modified.

The same Paper Reviewer profile performs both assessments. The first assessment
uses only the selected manuscript; the second uses the internal scientific
record as additional context.

Choose a Review target when you want an assessment of a specific post-review
version. Choose Review & Revision only when the legacy launch gate is already
satisfied and you want the lead to revise that Assembly after review.

There is currently no one-click continuation that revises the exact manuscript
selected as a Review target. Standard Review & Revision starts from the
Assembly recognized by the legacy gate, not from that selected post-review
manuscript.

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
- a separate revised manuscript;
- an exact record of changes from the reviewed manuscript;
- clear labeling when a changed post-review manuscript has not itself received
  another review.

### From a review-target run

- a preserved first-reader assessment of the exact selected manuscript;
- a second reviewer assessment informed by the internal scientific record;
- no automatic author revision and no change to the selected manuscript.

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

Assembly produces the manuscript and its sealed record. The current launcher
still accepts only an Assembly record with legacy `approved` status as the
source for standard Review & Revision. Because the phase panel no longer
provides an approval action, a newly completed Assembly cannot normally become
that source. This is an implementation restriction, not a scientific
acceptance step. See [Current Limitations](../known-limitations).

### After Review & Revision

Use the revised manuscript and revision record to decide whether to run another
paper-stage assessment, return to an earlier research phase, or seek human
review. Return to Phase 1, 2, 3, or 4 when the review identifies a literature,
method, proof, implementation, or empirical gap that cannot be repaired through
writing.

If important text changed during revision, consider reviewing that exact
post-review manuscript again before submission.

### After a review-target run

Use the two reviewer assessments to decide whether the selected manuscript needs
a new authoring run, work in an earlier phase, or human review. The review-target
run itself does not revise the manuscript. If you start another authoring run,
carry the reviewer comments forward explicitly and verify the manuscript version
shown as its source.

## Reruns and downstream effects

Every rerun creates a separate sealed record. Earlier manuscripts and reviews
remain available for comparison.

Research Hub does not submit a Phase 5 manuscript or represent it as accepted,
published, externally reviewed, or verified.

The same legacy gate restricts repeated Review & Revision launches. Even when an
eligible Assembly record exists, a later Phase 5 result can cause it to stop
satisfying the gate. See [Current Limitations](../known-limitations) before
planning repeated review cycles.

For artifact names, run records, manuscript variants, and branch layout, see
[Files and records](../reference/files-and-records).
