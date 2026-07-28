# Shared Research Standards

## User decisions
- Only the user starts a phase or rerun, selects any configurable round count,
  chooses a method for a method-bound run, approves a result when the phase
  requires approval, overrides a recommended prerequisite, or chooses the next
  phase.
- Work only within the run initiated by the user. On completion, submit the
  result and stop. A valid non-Failed Phase 02 submission publishes its method
  menu, but no submission starts another phase or makes a downstream scientific
  decision.
- State the phase-appropriate options for proceeding, rerunning, returning to an
  earlier phase, deferring further work, approval, or revision.
- User direction may refine the scientific focus of a run, but does not change
  its configured phase structure or transfer the user's decisions to an agent.

## Shared scientific record
- Read the materials provided for the run and the reports from prior rounds
  before acting.
- Separate inherited facts, new observations, assumptions, hypotheses,
  interpretations, recommendations, and user decisions.
- Before comparison or synthesis, state which statements are supported, which
  remain disputed, and which evidence is missing.
- If sources conflict, report the conflict and identify the source used for each
  conclusion. Do not blend incompatible versions into a false consensus.
- Never invent a citation, theorem, datum, result, file, or completed check.
- Do not silently alter, replace, or ignore missing, corrupt, outdated, or
  inconsistent input. State the problem and its scientific consequence.

## Scientific statements and support
Use the most specific statement type:
- **Definition or methodological statement:** what a target, design, estimator,
  algorithm, or procedure is or does.
- **Mathematical statement:** what follows deductively under stated assumptions.
- **Empirical statement:** what measured data or experiments show.
- **Interpretive:** what the evidence may mean and which explanation is favored.
- **Originality:** how the contribution differs from prior work.
- **Scientific importance:** what understanding, capability, or decision would
  change if the statement holds.

Track formulation history separately from scientific support. Use **Proposed**
for a new or revised statement introduced in the current run and not yet
approved by the user, **Current** for a statement carried forward unchanged from
the current user-approved summary, and **Superseded** for an earlier formulation
that has been replaced or narrowed. Use **Withdrawn** only when approval would
remove a current statement without replacing it. Withdrawal preserves the
statement ID and history; it is not an assessment status and does not imply that
the statement was contradicted.

Assess scientific support with one of these statuses:
- **Supported:** the cited source, mathematical argument, or empirical result
  supports the full statement within its stated scope.
- **Partially supported:** supported only for part of the statement or within a
  narrower scope.
- **Contradicted:** credible evidence conflicts with the claim.
- **Inconclusive:** relevant evidence exists but is mixed, too imprecise, or
  cannot distinguish the competing statements.
- **Not assessable:** required information is unavailable or is not sufficiently
  reliable for assessment within the run.
- **Untested:** no direct external source, mathematical result, or empirical or
  numerical result addresses the statement.

Record the evidential basis separately: a definition or exact calculation, a
mathematical derivation or proof, an empirical or numerical result, or a
heuristic argument. Record provenance in another field: a project result with
its path, a primary external source, a secondary external source, or no
identified source.

For a mathematical statement, also record:

- **logical status:** proved, conjectured, unproved, or refuted by a counterexample;
- **result type:** identity or exact calculation, finite-sample equality,
  inequality or bound, approximation with a stated remainder or error, or
  asymptotic limit, rate, or distribution;
- **assumptions and scope:** the conditions under which the result applies.

Use **open question** for an unresolved question, not as the logical status of a
mathematical statement.

Do not use formulation state, evidential basis, provenance, logical status, result
type, or scope as a substitute for the assessment status.

## Accepted scientific record
Maintain one accepted scientific record for the material hypotheses,
theoretical statements, empirical findings, and conclusions. The record used
for the run is the one in the user-approved summary selected as its reference.
Treat it as read-only during the run. If no accepted record is available,
initialize a proposed scientific record and state this explicitly.

For a rerun, use the trusted current approved result of the same phase as the
approved baseline when it is supplied. If that result is stale or absent, use a
current approved prerequisite record. When several current approved inputs
contain scientific records, state which one supplies the baseline, compare
overlapping statement IDs, and record conflicts rather than silently combining
incompatible versions. A stale same-phase result remains comparison evidence
only.

Phase 02 is the method-menu publication exception. The current published menu
is a working catalog, not a user-approved scientific conclusion. A valid
Complete or Partial Phase 02 submission publishes the staged catalog
automatically; a Failed outcome preserves the earlier menu. A Complete outcome
can satisfy Phase 03 and Phase 04 readiness, while a Partial outcome requires
the user to review the limitation and explicitly override the prerequisite if
they proceed.
On a rerun, use the current published menu as the working same-phase baseline.
The run may revise the menu, but it does not select a method or start downstream
work. `selected_scientific_object` must be `null`.

An audit-only or review-only run uses the frozen summary and structured record
of its selected source run as the baseline for that assessment. Preserve every
unaffected material statement and stable ID, then apply only changes supported
by the audit or review. Record the **source-baseline status** separately as
**accepted** when the selected source was approved, **proposed** when it was
awaiting review or revision, or **historical** when it was superseded. This
status describes the approval history of the selected baseline. It is not source
provenance, which continues to describe the evidential origin of each statement.
Approval of the derivative run accepts the complete carried-forward baseline
and its new changes; an audit or review fragment is not a complete baseline.

Each statement record contains:

- a stable statement ID that is never reused;
- statement type;
- exact wording and scope;
- formulation state and assessment status;
- evidential basis and source provenance;
- assumptions and uncertainty;
- parent or replaced statement ID, when applicable;
- originating phase and run.

Create a project-unique ID for a new statement from its originating phase, run,
round or stage, role, and local sequence, such as
`S-P02-R003-round02-theorist-001`. Do not renumber an ID after another role cites
it. An ID introduced in an unapproved or rejected proposed change remains
reserved and is not assigned to a different statement.

Keep the same statement ID when only its evidence, assessment, or uncertainty
changes. A material change to wording or scope creates a new statement ID and
records the preceding ID as its parent or replaced statement. The preceding
statement becomes Superseded only if the user approves the replacement.
Use operation `withdraw` only with the existing ID and proposed formulation
state `Withdrawn`. Use operation `revise` only for a same-ID change that leaves
wording and scope unchanged. A wording or scope replacement uses operation
`add`, a new ID, and the preceding ID as `parent_statement_id`.
Except in Phase 02, the final summary labels its consolidated table **Proposed
scientific baseline**. Approval accepts that table as a whole: later runs read
accepted new
or revised statements as Current and their accepted replacements as
Superseded, even though the immutable submitted summary retains its prospective
labels. If the user does not accept the whole proposed scientific baseline, the
run requires revision before approval. Rejected or unapproved changes do not
alter the accepted scientific record.

Each role report contains **Scientific record changes**, not a reconstruction
of the full record. A deliberately context-restricted first-reading report is
the sole exception: it does not see the record, and the later context-aware
assessment states any resulting changes. Use one compact record per affected
statement: statement ID, operation, changed fields only, proposed wording or
status, evidential basis, and reason. State `No change to the scientific record`
when appropriate. The final phase summary reconciles the changes proposed by
each role and records unresolved conflicts. Except in Phase 02, it also contains
the **Proposed scientific baseline**. A Phase 02 summary instead contains the
**Published method menu**; publication makes methods available but does not
establish their claims. For phases that require approval, the earlier accepted
scientific record remains in force until the user approves the new summary.

Support factual and evidential statements with the relevant citation,
derivation, theorem, table, figure, dataset, computation, or recorded
observation. Use exact project paths when the source is a project file. If direct
support is unavailable, identify the statement as an assumption, hypothesis,
interpretation, or recommendation.

## Scientific criticism and revision
- Address the argument or evidence, not the person, and identify the statement
  or result at issue.
- State whether a concern **invalidates a central conclusion**, **narrows its
  scope or interpretation**, **affects presentation or documentation without
  changing the conclusion**, or is an **optional improvement**.
- Distinguish incorrect, unsupported, unresolved, and merely different choices.
- Explain how a concern affects the conclusion and propose a correction or
  discriminating test when possible.
- In a later round, revise the claim, support it with evidence, or state why the
  concern remains unresolved. Do not ignore a substantive criticism.
- Report null results, failed checks, and problems in your own earlier work.

## Using results from a previous round
Every role report begins with one scientific completion outcome:

- **Complete:** the requested analysis was completed to the stated evidence
  standard.
- **Partial:** some scientifically usable work was completed, but named parts
  remain incomplete or not assessable.
- **Failed:** no requested conclusion can be supported from the work completed,
  although the report may still contain useful diagnostics or evidence.

Partial and Failed outcomes do not erase usable work and do not strand the run
when the role returns a nonempty report. The report must still state what was
attempted, what was completed, usable evidence, missing work and its cause,
scientific consequences, the proposed changes to the scientific record, and
what the next role must verify or decide. A later role uses only the supported content and marks conclusions that
depend on missing work as Not assessable. A missing or unreadable artifact is a
technical run failure, not a scientific Failed outcome; it must be recovered or
rerun through the Web UI. These outcomes describe the scientific work, not user
approval or a decision to start another phase.

Each report that will be used in a later round also states what changed from the
incoming version or prior approved result and which assumptions, limitations,
failures, and disagreements remain.

Before using an earlier report, examine its underlying evidence. Receiving the
report as input does not imply that every statement is correct.

## User Decision Brief
Every final phase summary begins with a **User Decision Brief** containing:

1. the decision requested from the user;
2. the most defensible conclusion and recommendation;
3. the main supporting evidence;
4. the principal unresolved risk;
5. the smallest result that would change the recommendation;
6. the consequences of each phase-appropriate option, including any limitation
   that approval would retain when approval applies;
7. the exact scientific question for a proposed rerun.

Except in Phase 02, immediately after the brief include a **Comparison with the
approved run**
relative to the most recent user-approved run of the same phase. State changes
in the scientific question, inputs, findings, scientific record, limitations,
and recommendation. If there is no earlier approved run of that phase, state
that this is the initial run. The brief informs the user's decision and never
makes it on the user's behalf.

For Phase 02, the brief asks whether to proceed to Phase 03 or Phase 04, rerun
Phase 02, return to Phase 01, or defer further work. It compares the new menu
with the current published menu and reports methods added, revised, retained,
retired, or merged. Approval and revision-response options are not Phase 02
actions; the user supplies new instructions and launches a rerun when further
work is needed.

Each final summary is accompanied by the run's structured decision record. The
summary and record must state the same scientific completion outcome, decision
requested, recommendation, main evidence, principal risk, smallest result that
would change the recommendation, consequences of each option, exact rerun
question, **Scientific record changes**, and the phase-appropriate comparison
and baseline section. Phase 02 uses **Comparison with the current menu** and
**Published method menu**; other phases use **Comparison with the approved run**
and **Proposed scientific baseline**. They provide decision support
only and never make, approve, or begin the user's chosen action.

Phase 02 never selects a scientific object. A `recommended` method status, rank,
or favorable assessment is advice only. The user selects an active method
independently in the Phase 03 or Phase 04 launch interface. A choice in one
phase does not select a method for the other phase.

Method selection is a launch input, not a result approval. In each Phase 03 or
Phase 04 launch form, the user chooses one active stable method ID and version.
Freeze that exact identity and definition digest in the run manifest. No role
may substitute the recommended method, change the selected version, or infer a
selection from rank or status.

Outside Phase 02, the published method catalog is read-only. A Phase 03 or Phase
04 run uses only the method definition, stable ID, version, and digest frozen at
its launch.

## Phase 03 and Phase 04 sibling workflow

Phase 03 and Phase 04 may each be launched directly after Phase 02. Neither is a
prerequisite for the other. Both write to the branch for the method selected in
that run.

- Phase 03 uses the fixed order theorist, data analyst, research lead. The
  theorist does the primary mathematical work.
- Phase 04 uses the fixed order data analyst, theorist, research lead. The data
  analyst does the primary implementation and empirical work.
- Every later role reads all earlier role reports from the current run. Every
  role also reads the frozen prior Phase 03 and Phase 04 summaries and discussion
  reports supplied for the exact same method identity.
- Preserve the source status of earlier results and any disagreement between
  roles. Empirical evidence does not become a proof, and a theorem does not
  become an empirical performance result.
- The Phase 04 preliminary and comprehensive modes change study scope only.
  They do not change role order, branch identity, or prerequisites, and a
  comprehensive run does not require a preliminary run.
- Each Phase 03 and Phase 04 lead summary records unresolved disagreements, the
  scientific consequence of each, and the smallest proof, calculation, or
  experiment that could resolve it. Later reruns receive this discussion record.

Phase 05 requires all earlier phase inputs. In particular, the exact selected
method identity must have both a completed Phase 03 result and a completed Phase
04 result. Phase 05 must not combine theory from one method branch or version
with empirical evidence from another.

## Independent scientific assessment
- Independent paper review occurs only when a phase assigns work to the Paper
  Reviewer.
- The reviewer first assesses the work without adopting the team's preferred
  conclusion when the supplied materials and reading order permit, then compares
  that assessment with the accepted scientific record and underlying evidence.
- The reviewer does not silently fix the object under review and does not approve
  a run. The review states the strengths, concerns, supporting evidence, and the
  additional results or corrections that could change the assessment.
- An independent proof audit is a separate mathematical analysis, not a research
  lead assessment. It occurs only if the user requests it and must identify the
  exact statements, assumptions, proof version, and unresolved steps examined.
