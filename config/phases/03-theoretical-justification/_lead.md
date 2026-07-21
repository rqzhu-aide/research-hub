# Lead Instructions: Theoretical Analysis (Sequential)

Coordinate exactly the Phase 03 plan selected by the user:

- **Standard theory**: theorist draft, research-lead assessment, then theorist
  revision.
- **Standard theory plus audit**: the same three stages followed by one
  independent paper-reviewer audit.
- **Audit existing theory only**: one paper-reviewer audit of an existing sealed
  final theorist artifact. Do not repeat or revise the theory.

For a standard theory stage, state the theoretical questions, provide each
report to the next role, and preserve the assessment of every material
scientific statement. You do not write proofs or determine their correctness.
For either audit plan, the run helper freezes the exact theory target, its hash,
and the authorized non-lead evidence inventory. Do not revise the target after
selection and do not add another theorist stage.

## Responsibilities and sequence
1. Read the frozen run plan before dispatching any role.
2. For a three-stage or four-stage plan, read the exact stable method ID and
   version frozen for this run, its specification, the accepted scientific
   record, and relevant literature. Identify whether this is the approved Phase
   02 **Method selection for downstream study** or an exact run-specific choice.
   State the principal theoretical questions and a provisional dependency
   structure.
3. For those standard stages, give the theorist the round 1 instructions, wait
   for a nonempty report, give the research lead the round 2 instructions, wait
   for a nonempty report, and then give the theorist the round 3 instructions.
4. For a four-stage plan, dispatch the paper reviewer only after round 3 is
   complete. For an audit-only plan, dispatch only the paper reviewer in round 1
   against the source identity frozen into the run.
5. Wait for every stage authorized by the selected plan. Each report must declare
   Complete, Partial, or Failed.
6. Write an evidence-weighted synthesis that states the best-supported
   conclusion, disagreement, uncertainty, and available user choices. For an
   audit-only plan, limit the synthesis and completion outcome to the audit
   scope and its consequences for the selected source analysis.

## Roles
| Role | Scientific focus | Instructions file |
|------|------|-----------|
| theorist | estimands, mathematical mechanisms, assumptions, and proofs | `theorist.md` |
| research_lead (you) | results, claims, and prior work | `research_lead.md` |
| paper_reviewer | audit of the exact final theory artifact when selected | `paper_reviewer.md` |

The round 2 research-lead report is one scientific assessment. It is distinct
from the final evidence-weighted synthesis and is not independent proof checking.

## Step 1: Read prior context
For a standard three-stage or four-stage theory plan, read:

- `setting.md`
- the shared team norms and an accepted scientific record from a trusted,
  current approved Phase 03 result on rerun; treat a stale Phase 03 result as
  comparison only, and otherwise use a user-approved, current Phase 02 record
- approved Phase 02 and Phase 01 summaries provided for this run, when available
- the exact method ID and version recorded in the approved Phase 02 **Method
  selection for downstream study**, its specification, and detailed `ideas/`
  output
- prior `draft/theory/` runs

If neither a trusted Phase 03 record nor a current approved Phase 02 record is
available, initialize a proposed scientific record and state that no approved
baseline is available.

For an audit-only plan, use the exact source run identity, theory artifact, hash,
non-lead evidence inventory, source summary, and structured source record frozen
by the run helper. Preserve every unaffected material statement and stable ID in
the complete proposed baseline, and apply only audit-supported changes. Record
the supplied source-baseline status exactly as accepted, proposed, or historical.
Keep that status distinct from the source provenance of each statement. Use the user's
direction only to define the named audit scope. Do not formulate a replacement
theory question, ask the theorist for new work, or use a prior research-lead
preference as evidence of mathematical correctness. Skip Steps 2 through 4 and
proceed directly to Step 5.

For a standard three-stage or four-stage plan, fix the exact stable method ID and
version to be analyzed. Do not infer it from a recommendation, ranking, or method
table. If the approved Phase 02 selection is missing, say so explicitly; if the
user supplied a different method for this run, identify it as a run-specific
choice rather than the approved Phase 02 selection. Identify two to four
substantive questions, such as:

- What estimand does the feasible procedure target, and under what model, design,
  and assumptions is that estimand identified?
- Which bias or approximation terms explain success and failure?
- Which operation creates the claimed adaptive or inferential mechanism?
- What boundary case makes the proposed contribution vanish or become exact?
- Which assumption is structural, and which is only technical?

Do not derive consistency or rates by default if they do not address the central
scientific question.

## Step 2: Round 1 theorist draft
Begin round 1 with the theorist and provide the following requirements:

1. the selected stable method ID, version, and claims to analyze;
2. the scientific questions;
3. the dependency structure among the proposed results;
4. assumption roles and nearest prior results;
5. logical status, result type, assumptions, and scope for each result,
   recorded separately from the assessment status of the statement it supports;
6. boundary cases and counterexamples;
7. the indispensable lemmas and proof steps for the principal result, and the
   results outside the scope of this analysis;
8. supplied user direction;
9. **Scientific record changes:** only proposed additions or changes to
   material statements.

Wait for a nonempty report before beginning round 2. A nonempty Partial or
Failed report may support later work; mark dependent conclusions as Not
assessable. A missing, empty, or unreadable report is a technical failure. Do not
begin round 2 until the report is available.

## Step 3: Round 2 research-lead assessment
Begin round 2 with the research lead. Provide the exact path to the nonempty
theorist report. Ask the research lead to:

- relate every result to the Phase 02 methodological and contribution statements
  in the accepted scientific record for this run;
- determine whether each result establishes identification, characterizes the
  estimand, explains the mechanism, or defines the scope of a scientific
  statement;
- compare originality and strength with prior theory;
- examine the role and restrictiveness of the assumptions and the assessment of
  the associated scientific statement;
- identify unreported changes to the estimand, circular reasoning, or results that
  do not contribute to the central claim;
- state the mathematical changes needed and their consequences for the user's
  research choices;
- propose changes to the scientific record without reproducing the full
  accepted record.

The research lead may identify a proof gap but does not determine proof correctness.

## Step 4: Round 3 theorist revision
Begin round 3 with the theorist and provide the nonempty round 2 report,
including its completion outcome and missing work. A missing, empty, or
unreadable round 2 report is a technical failure. Do not begin round 3 until the
report is available. For every central result, require one current result record
stating:

- stable result or statement ID and exact statement;
- proof or gap finding from rounds 1 and 2;
- mathematical change, or the reason no change was made;
- current logical status, result type, assumptions, and scope;
- current assessment status of the associated scientific statement;
- unresolved step and next verification, when applicable.

Do not allow an unreported change to the estimand, method, assumption, or claim.
The theorist must state every such change and its consequence. Stop when all
mathematical statements and remaining gaps are explicit and further progress
requires a new idea or a user decision.

## Step 5: Independent proof audit
Perform this step only when an audit appears in the frozen run plan. In the
four-stage plan, the target is the exact round 3 theorist artifact from this run.
In the audit-only plan, the target is the exact sealed final theorist artifact
identified by the frozen source run ID. Dispatch no other role in an audit-only
run.

The reviewer task directive must define the audit scope: statement IDs and exact
wording, proof locations, assumptions, dependency sources, and recorded hashes.
Do not include a research-lead preference or recommendation in the audit packet.
Require the reviewer to assess the proof target and cited mathematical sources
before consulting the mapping to scientific claims, reconstruct the
dependencies, check indispensable steps and assumptions, attempt informative
boundary checks, and state what could not be checked. The audit reports findings;
it does not rewrite the analysis or certify every proof. Audit Complete means
that every prespecified check for the named results was performed, not that the
result was verified or the full theory certified.

## Step 6: Final synthesis
Write the HTML summary to the exact path supplied for this run and preserve that
version unchanged after submission.
Begin with the User Decision Brief. Place the Comparison with the approved run
second and the phase completion outcome third, using the definitions in the
team norms.
Separate:

1. **Theoretical results and research-lead assessment**.
2. **Evidence-weighted synthesis** stating the best-supported conclusion,
   disagreements, uncertainty, and available user choices.

Include:

1. selected stable method ID, version, and theory questions;
2. dependency structure among the results;
3. main results in plain language with logical status, result type, assumptions,
   scope, and the assessment of each associated scientific statement;
4. table of assumptions and their mathematical roles;
5. indispensable lemmas and proof steps, resolved gaps, and unresolved problems;
6. boundary cases and counterexamples;
7. one consolidated set of Scientific record changes, the complete Proposed
   scientific baseline, and comparison with prior theory. State that approval
   accepts the proposed baseline as a whole, while revision or rerun retains
   the previously approved baseline;
8. if selected, the audit scope and target identity, completion outcome, checks
   performed, findings, remaining uncertainty, and contribution to the
   consolidated Scientific record changes; otherwise, any recommended later
   audit and reason;
9. explicit user options:
   - approve this analysis as the current theoretical basis;
   - request a named revision;
   - rerun the phase around a different theory question;
   - narrow or change the method in Phase 02;
   - search a specific gap in the Phase 01 literature again;
   - proceed later to numerics while retaining named theoretical limitations;
   - select the optional independent proof-audit stage in a rerun only when no
     adequate audit was completed, the selected audit was incomplete, or a
     distinct named central result remains unaudited.

For an audit-only plan, replace items that imply new theory development with:

- source run ID, exact target path, source stage, and SHA-256;
- the named audit scope and checks completed;
- result-by-result audit findings and their consequences for the source
  analysis;
- unresolved checks and the smallest next verification;
- the complete carried-forward source baseline, with unaffected statement IDs
  preserved and audit-supported changes identified separately;
- explicit user choices to accept the audit as evidence about the source
  analysis, request a named correction, rerun a different audit scope, or run
  the standard theory plan. Do not present the source theory as newly derived or
  revised in this run.

For any proposed proof audit, identify the exact statement IDs, assumptions,
proof locations, and unresolved steps, and state why an existing audit does not
already resolve that scope. Present it as an optional user decision. Do not imply
that the research lead has certified the proof.

Do not select an option for the user. Submission does not approve the theory or
start Phase 04.

## Scientific requirements
- Preserve the exact three-stage, four-stage, or audit-only plan selected by the
  user.
- Follow the shared team norms and the accepted scientific record for this run.
- Require role reports to propose only Scientific record changes. Reconcile
  those changes in the final summary without editing an earlier approved summary.
- Prefer results that characterize the estimand or explain the mechanism to a
  larger number of weakly informative theorems.
- Keep logical status, result type, assumptions, scope, and assessment
  status separate.
- Use the supplied user direction in every standard round and in the sealed
  scope of the optional proof audit.
