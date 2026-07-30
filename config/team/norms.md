# Shared Research Standards

## User decisions
- Only the user starts a phase or rerun, selects any configurable round count,
  chooses a method for a method-bound run, selects run scope and optional
  context, overrides a recommended prerequisite, or chooses the next phase.
- Work only within the run initiated by the user. On completion, submit the
  result and stop. A valid result may update that phase's canonical current
  record according to its storage policy, but no submission starts another
  phase or makes a downstream scientific decision.
- State the phase-appropriate options for proceeding, rerunning, returning to an
  earlier phase, revising the current record, preparing a manuscript for
  submission, or deferring further work.
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
for a new or revised statement in the staged current run, **Current** for a
statement represented in the canonical current record, and **Superseded** for an
earlier formulation replaced or narrowed by a valid current result. Use
**Withdrawn** only when the current record explicitly removes a statement
without replacing it. Withdrawal preserves the
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

## Canonical current records

The project keeps canonical current records for decision making and immutable
run records for provenance. A new valid phase result updates its canonical
record according to the phase-specific policy below. Failed, invalid, or
incomplete replacement work never displaces a valid current record. Updating a
current record is an automatic run lifecycle operation.

- **Phase 01, literature:** the reference library is cumulative. A run stages a
  `reference-delta/` containing unique new cards and a complete current
  literature synthesis. Promotion never replaces or deletes an existing card
  and rejects duplicate canonical identities.
- **Phase 02, methods:** the current published menu is the working catalog. In a
  full-catalog run, the team may add, revise, merge, retain, or retire methods.
  In a focused-method run, only the selected active method may change; no method
  may be added, removed, renamed, merged, or retired, and every nonselected file
  remains byte-for-byte unchanged. The run never selects a downstream method.
- **Phase 02 method versions:** each method file has exactly one authoritative
  `## Mathematical definition` section. Put every calculation-defining object
  in that section, including the estimator or objective, algorithm or update
  rule, tuning definition, and any assumption that changes a computed
  quantity. Advance the version whenever that section changes mathematically.
  Keep the version unchanged for status, literature-positioning, explanation,
  or formatting changes made outside that section when the calculation is
  unchanged. Leave the authoritative section exactly unchanged when retaining
  the version. Research Hub computes the definition digest and records the
  version history.
- **Phase 03, theory:** each method has one complete current
  `theory-manuscript.md`. A valid Complete run replaces it atomically. By
  default, a rerun uses this current manuscript and current sibling evidence.
  Archived Phase 3 summaries are supplied only when the user selects
  `include_archived_summaries` at launch.
- **Phase 04, empirical work:** each method has one cumulative current
  `evidence-index.json` and `empirical-synthesis.md`. Existing evidence IDs and
  immutable artifact identities remain in the index. Scientific outputs and
  method implementations are bound to the exact method version that produced
  them and become `outdated` after a calculation-defining revision. Raw source
  data and generic infrastructure may remain reusable only when their
  mathematical independence from the revised method is stated explicitly. A
  reanalysis or revalidation receives a new evidence ID; an old non-current ID
  never returns to `current`.
- **Phase 05, manuscript:** each method branch has one current `manuscript.md`.
  Assembly and review-revision runs update that draft in place through an atomic
  replacement. Reviews, diffs, and run summaries remain immutable records, but
  old manuscript generations are not normal scientific inputs.

Use the exact canonical records supplied in the run manifest. When several
current inputs overlap, preserve their identities and record conflicts rather
than blending incompatible statements. Run summaries are explanatory records,
not substitutes for current scientific packages.

An audit-only or review-only run uses the frozen summary and structured record
of its selected source run as the baseline for that assessment. Preserve every
unaffected material statement and stable ID, then apply only changes supported
by the audit or review. Record whether the source was **current** or
**historical** separately from scientific provenance. An audit or review
fragment is not a complete replacement record unless its phase protocol
explicitly produces and validates the full current object.

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
it. An ID introduced in a staged or failed run remains reserved and is not
assigned to a different statement.

Keep the same statement ID when only its evidence, assessment, or uncertainty
changes. A material change to wording or scope creates a new statement ID and
records the preceding ID as its parent or replaced statement. The preceding
statement becomes Superseded only when a valid replacement becomes current.
Use operation `withdraw` only with the existing ID and proposed formulation
state `Withdrawn`. Use operation `revise` only for a same-ID change that leaves
wording and scope unchanged. A wording or scope replacement uses operation
`add`, a new ID, and the preceding ID as `parent_statement_id`.
The final summary labels its consolidated table **Current scientific record**
when the phase maintains statement-level records. A valid promotion makes new or
revised statements Current and their replaced formulations Superseded. The
immutable run summary still records what changed. Failed or invalid work does
not alter the canonical current record.

Each role report contains **Scientific record changes**, not a reconstruction
of the full record. A deliberately context-restricted first-reading report is
the sole exception: it does not see the record, and the later context-aware
assessment states any resulting changes. Use one compact record per affected
statement: statement ID, operation, changed fields only, proposed wording or
status, evidential basis, and reason. State `No change to the scientific record`
when appropriate. The final phase summary reconciles the changes proposed by
each role and records unresolved conflicts. Except in Phase 02, it also contains
the **Current scientific record**. A Phase 02 summary instead contains the
**Published method menu**; publication makes methods available but does not
establish their claims.

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
authorization to start another phase.

Each report that will be used in a later round also states what changed from the
incoming version or current result and which assumptions, limitations,
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
   that the next action would carry forward;
7. the exact scientific question for a proposed rerun.

Immediately after the brief include a **Comparison with the current record**.
State changes in the scientific question, inputs, findings, current scientific
record, limitations, and recommendation. If there was no earlier current record,
state that this is the initial run. The brief informs the user's decision and
never makes it on the user's behalf.

For Phase 02, the brief asks whether to proceed to Phase 03 or Phase 04, rerun
Phase 02, return to Phase 01, or defer further work. It compares the new menu
with the current published menu and reports methods added, revised, retained,
retired, or merged. The user supplies new instructions and launches a rerun when
further work is needed.

Each final summary is accompanied by the run's structured decision record. The
summary and record must state the same scientific completion outcome, decision
requested, recommendation, main evidence, principal risk, smallest result that
would change the recommendation, consequences of each option, exact rerun
question, **Scientific record changes**, and the phase-appropriate comparison
and baseline section. Phase 02 uses **Comparison with the current menu** and
**Published method menu**; other phases use **Comparison with the current
record** and the phase's canonical record label. They provide decision support
only and never make or begin the user's chosen action.

Phase 02 never selects a scientific object. A `recommended` method status, rank,
or favorable assessment is advice only. The user selects an active method
independently in the Phase 03 or Phase 04 launch interface. A choice in one
phase does not select a method for the other phase.

Method selection is a launch input. In each Phase 03 or
Phase 04 launch form, the user chooses one active stable method ID and version.
Freeze that exact identity and definition digest in the run manifest. No role
may substitute the recommended method, change the selected version, or infer a
selection from rank or status.

Outside Phase 02, the published method catalog is read-only. A Phase 03 or Phase
04 run uses only the method definition, `stable_id`, `version`, and
`definition_sha256` frozen at its launch.

The exact downstream identity is the tuple `stable_id`, `version`, and
`definition_sha256`. Phase 03 proofs and Phase 04 method-dependent computations
apply only to that identity. After a calculation-defining Phase 02 revision,
earlier proofs, implementations, and results remain historical records. A user
may rerun Phase 03 or Phase 04 so the responsible roles can determine which
arguments or study components still apply, but the earlier work is not current
support for the new version merely because the stable ID is unchanged.

## Separate status judgments

Report these questions separately:

1. **Method and basis alignment:** does the record refer to the exact current
   method identity and the recorded current sibling basis?
2. **Research attention:** which Phase 04 evidence is outdated or unresolved
   and therefore requires reanalysis, revalidation, or an explicit limitation?
3. **Scientific completion outcome:** did the authorized work finish as
   Complete, Partial, or Failed under the phase standard?

Alignment does not establish scientific validity. Research attention does not
change a completion outcome. A Complete run can still produce weak or negative
scientific evidence, and a Partial run can still contain valid current results.

## Phase 03 and Phase 04 sibling workflow

Phase 03 and Phase 04 may each be launched directly after Phase 02. Neither is a
prerequisite for the other. Both write to the branch for the method selected in
that run.

- Phase 03 uses the fixed order theorist, data analyst, research lead. The
  theorist does the primary mathematical work.
- Phase 04 uses the fixed order data analyst, theorist, research lead. The data
  analyst does the primary implementation and empirical work.
- Every later role reads all earlier role reports from the current run. Every
  role also reads the canonical current records supplied for the exact same
  method identity.
- Phase 03 uses current-only context by default. Archived Phase 3 summaries are
  included only when the user explicitly selects that launch option.
- Phase 04 uses its cumulative evidence index and current synthesis. It does not
  reconstruct current evidence from the full run archive.
- Preserve the source status of earlier results and any disagreement between
  roles. Empirical evidence does not become a proof, and a theorem does not
  become an empirical performance result.
- The Phase 04 preliminary and comprehensive modes change study scope only.
  They do not change role order, branch identity, or prerequisites, and a
  comprehensive run does not require a preliminary run.
- Each Phase 03 and Phase 04 lead summary records unresolved disagreements, the
  scientific consequence of each, and the smallest proof, calculation, or
  experiment that could resolve it in the phase's compact current record.

Phase 05 requires all earlier phase inputs. In particular, the exact selected
method identity must have both a completed Phase 03 result and a completed Phase
04 result. Phase 05 must not combine theory from one method branch or version
with empirical evidence from another.

## Independent scientific assessment
- Independent paper review occurs only when a phase assigns work to the Paper
  Reviewer.
- The reviewer first assesses the work without adopting the team's preferred
  conclusion when the supplied materials and reading order permit.
- The reviewer does not silently fix the object under review or choose the next
  run. The review states the strengths, concerns, supporting evidence, and the
  additional results or corrections that could change the assessment.
- An independent proof audit is a separate mathematical analysis, not a research
  lead assessment. It occurs only if the user requests it and must identify the
  exact statements, assumptions, proof version, and unresolved steps examined.
