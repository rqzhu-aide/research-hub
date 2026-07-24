# Phase: Paper Writing

## Goal
Produce a complete, coherent manuscript draft in which the claims are consistent
with the theory, empirical evidence, interpretation, and stated limitations. The
draft must be readable as a paper, not merely a collection of separately
authored sections.

The research lead is responsible for the manuscript structure, assembly,
abstract, introduction, related work, method, discussion, and conclusion. The
theorist is responsible for the theory section. The data analyst is
responsible for experiments and results. The paper reviewer provides an initial
independent reading and a full scientific assessment of the manuscript.

## Prior information
This phase normally uses approved, current Phase 03 and Phase 05 runs. When
either source is unavailable or out of date, the web UI explains the limitation
and the user may choose to proceed. The lead must disclose any missing basis and
must not fill a theoretical, empirical, interpretive, or citation gap with
invented support.

Use available Phase 01, Phase 02, and Phase 04 work for literature positioning,
method specification, and empirical detail. Earlier aspirations never override
the current Phase 04 results, their stated uncertainty and scope, or the Phase 05
interpretation.

For a Phase 06 rerun, initialize the accepted scientific record from a trusted,
current approved Phase 06 result when one exists. A stale Phase 06 result is
comparison only. When no trusted Phase 06 record exists, use the accepted
scientific record from a current user-approved Phase 05 result when available.
Otherwise initialize a proposed scientific record and state that no approved
baseline is available. The manuscript claim-evidence table begins as a view of
the accepted scientific record, not an independent record. Record specialist
corrections and manuscript-specific statements as proposed changes, and keep
them distinct from accepted entries until user approval. Phase 06 outputs never
alter an approved earlier summary or its evidence.

## Full writing sequence
**Sequential.** Keep these five stages in this exact order:
1. Research lead defines the manuscript plan and drafts all sections assigned to
   the research lead in stage 1.
2. Theorist drafts the theory section and integrates complete proofs for every
   central mathematical result in stage 2.
3. Data analyst drafts experiments and results in stage 3.
4. Paper reviewer records an independent first reading in stage 4. This task
   receives only the sealed manuscript, reviewer instructions, and reviewer
   role instructions. It does not receive the project brief, author reports,
   user direction, phase summaries, or the accepted scientific record.
5. Paper reviewer performs the context-aware scientific assessment in stage 5.
   This separate task receives the preserved stage 4 report, its hash, the same
   sealed manuscript, the sealed stage 1 through 3 author reports, and the
   internal scientific record and relevant phase summaries.

After stage 3, the lead assembles one manuscript before beginning the reviewer
assessment. Call it complete only if every central mathematical result has a
complete proof in the main text or appendix. If a central proof is missing,
preserve the explicit gap, give the mathematical statement logical status
`unproved`, assess any scientific statement that depends on that proof as `Not
assessable`, and carry a Partial outcome through the remaining review stages.
After stage 5, the lead determines the scientific
consequences of the review findings and reports any limited revisions within the
lead's responsibility. These steps do not add another author stage. Do not
skip, combine, reorder, or parallelize the
configured stages.

## Review-only sequence
A user may select an existing `manuscript-post-review.md` in the web UI and
start a review-only run. The system copies that exact source, verifies its
user-visible SHA-256, and preserves the copy as the new run's review manuscript.
The source and copy must remain unchanged. A review-only run contains only the
two reviewer stages above. It does not repeat or overwrite author work and does
not create a new post-review manuscript.

The exact manuscript version read by the reviewer must be preserved unchanged.
Any post-review revision creates a new version plus a diff and remains
explicitly unreviewed until the user begins another Phase 06 run that reviews it.

## Manuscript plan
At the start, state the research question or estimand, the proposed method or
mechanism, the scientific or statistical contribution, and the conditions and
scope of validity.

Use the accepted scientific record for this run to construct a
manuscript-specific claim-evidence table. Give every material claim one
stable statement ID and record the exact sealed manuscript path, hash, and claim
location to which the row applies. Give every material claim one assessment
status from the shared vocabulary and state its evidential basis separately: a definition or
exact calculation, mathematical derivation or proof, empirical or numerical
result, or heuristic argument. Record source provenance separately. For each
mathematical result, also record logical status, result type, assumptions, and
scope as defined in the shared norms.

No section may present one form of evidence as another.

For each important intellectual unit, present the scientific need, obstacle,
representation, essential notation, result, interpretation, and scope in that
order when it clarifies the argument. Not every paragraph needs all seven parts,
but the reader should encounter each before being asked to accept the
corresponding scientific statement.

## Folder
All round reports land in `draft/run/NN/`:
- `round-01/research_lead.md`: manuscript plan and sections written by the
  research lead
- `round-02/theorist.md`: theory section, complete central proofs, and plans for
  noncentral appendix material
- `round-03/data_scientist.md`: experiments and results section
- `round-04/paper_reviewer.md`: independent first reading in a sealed reviewer
  workspace containing only the exact manuscript and reviewer instructions, without
  internal project context
- `round-05/paper_reviewer.md`: context-aware scientific assessment of the
  same manuscript
- the HTML summary written to the path provided for this run and preserved
  unchanged after submission

For a full writing run, three fixed paths are provided under `draft/run/NN/`:
- `manuscript-review.md`: the exact version provided to the reviewer, which
  must remain unchanged;
- `manuscript-post-review.md`: any limited revisions made by the research lead;
- `manuscript-post-review.diff`: the exact difference between those versions.

Round reports must cite the exact assembled manuscript path and any section
source paths. The review path must never be overwritten after the reviewer
receives it.

For a review-only run, only `manuscript-review.md` is created in the new run. It
is an exact copy of the user-selected post-review source. A new post-review file
and diff are not applicable because the run performs no author revision.

## Expected scientific output
By the end of a full writing run, the project should have:
1. a complete assembled manuscript with abstract, introduction, related work,
   method, theory, experiments, results, discussion, conclusion, needed appendix
   structure, and complete proofs for every central mathematical result;
2. one explicit central statement of the research question or estimand, method
   or mechanism, contribution, and scope, with ranked secondary statements;
3. section plans and a manuscript view of the accepted scientific record with
   exact paths;
4. assessment status, evidential basis, source provenance, logical status,
   mathematical result type, and scope kept distinct;
5. consistency among the stated claims, theorems, experiments, interpretations,
   and limitations;
6. a separately dispatched and preserved independent reading completed before
   the reviewer receives the internal interpretation;
7. prioritized scientific concerns and a plan for the corresponding revisions;
8. preserved reviewed and post-review versions, with a diff that makes clear
   which version received independent review;
9. clear options for user-directed revision or reruns.

The final summary begins with the **User Decision Brief**, followed immediately
by the **Comparison with the approved run**, phase outcome, consolidated
**Scientific record changes**, and **Proposed scientific baseline**. State that
approval accepts the proposed baseline as a whole.

Every stage report and final summary states one completion outcome: **Complete**,
**Partial**, or **Failed**. For a full run, Complete means that the manuscript,
including complete proofs for every central mathematical result, sealed
independent reading, context-aware assessment, and version record were completed.
A missing central proof requires a Partial outcome, logical status `unproved`,
and assessment status `Not assessable` for any scientific statement whose support
depends on that proof. For a review-only run, Complete means that the selected
manuscript was faithfully preserved and both reviewer assessments were completed;
it does not mean that the manuscript's conclusions are scientifically adequate.
A nonempty Partial or Failed report preserves usable work, identifies what is
missing, and states the scientific consequence. A missing artifact is a technical
run failure under the shared norms, not a scientific completion outcome.

Follow the shared team charter and norms supplied with the run. The user starts
every run and decides whether to approve, revise, rerun, or pursue submission.
This phase never submits the paper or starts any external action automatically.
