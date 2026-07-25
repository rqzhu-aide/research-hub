# Phase: Scientific Interpretation

## Goal
Interpret the Phase 04 numerical findings, including the outcomes of their
validity checks, failures, and qualifications, without changing their source
files. Determine what was observed, which
explanations remain plausible, what the findings imply for the research claims,
and which scientifically defensible interpretations the user can choose.

Phase 04 performs the specified checks of implementation and numerical validity.
Phase 05 interprets the resulting evidence. If this phase identifies a validity
problem or requires a new experiment, state the concern and specify a targeted
Phase 04 rerun. Do not alter or rerun experiments within Phase 05.

## Prior information
This phase normally uses an approved, current Phase 04 run. When that evidence
is unavailable or out of date, the web UI explains the limitation and the user
may choose to proceed. The lead must then state exactly which results form the
common Phase 04 evidence summary and which interpretations cannot be assessed.

Current Phase 02 and Phase 03 outputs are useful for recovering intended claims
and theoretical predictions. They do not override what Phase 04 actually found.
For a rerun, use the accepted scientific record from a trusted current approved
Phase 05 result as the baseline. Treat a stale Phase 05 result only as
comparison evidence.

## Study structure
**Structured scientific discussion.** Keep the configured participants and
user-selected round count:
- theorist: theory, mechanism, assumptions, and prediction alignment;
- research lead: evidence for claims, scientific importance, and alternative
  interpretations;
- data analyst: evidence quality, sensitivity, and discriminating diagnostics.

In round 1, participants interpret the same evidence independently. In every
later round, each participant reads the other current outputs, compares their
interpretation with the strongest competing explanation, and updates or defends
it with evidence. Do not force agreement when the evidence leaves a genuine
split.

## Common Phase 04 evidence summary
Before round 1, prepare one common record from the current **accepted scientific
record** and the underlying Phase 04 evidence. If the approved Phase 04 summary
already supplies that record, use its **Scientific record changes** only to
trace statement revision history; do not apply the changes a second time. The
common record must
contain:
- exact Phase 04 scientific statements and assessment statuses;
- numerical values, uncertainty, units, and comparison definitions;
- paths to the code, configuration, tables, figures, and raw results;
- agreement between the stated method and its implementation, comparator
  fairness, reference-estimate uncertainty, computational budgets, and other
  validity qualifications;
- positive, null, negative, failed, and untested findings;
- the specific properties and settings that Phase 04 did and did not assess.

Participants may calculate a transparent diagnostic from the unchanged Phase 04
results only when they cite the source, calculation, and output and label it as
an exploratory Phase 05 diagnostic. The diagnostic is evidence, but it must not
be presented as prespecified or independently confirmed. Write any diagnostic
code and output under the current Phase 05 run. Never modify or replace Phase 04
code or result files.

Do not reopen a resolved validity or interpretation issue unless new evidence or
a new argument could change the conclusion. Record the prior resolution and the
new basis for reconsidering it.

## Scientific interpretation
For every finding that could change a central conclusion, its scope, or a user
decision, separate:
1. **Observation:** what was measured, including magnitude and uncertainty.
2. **Explanation:** candidate mechanisms that could produce the observation.
3. **Implication:** which claim or decision changes if an explanation is right.

Aggregate accuracy and decomposition accuracy are different. A method can match
an aggregate statistic while recovering the wrong components, transitions,
mechanism, or attribution. Interpret each claim at the level it actually names.

Retain one to three genuinely plausible explanations for each consequential
finding. Select them by their consistency with the evidence and their potential
to change the conclusion. Do not build a full explanation matrix for a finding
that cannot change the conclusion or continue discussing an explanation already
excluded by the evidence.

## Folder
All outputs land in `draft/analysis/run/NN/`:
- `round-NN/theorist.md`
- `round-NN/research_lead.md`
- `round-NN/data_scientist.md`
- the HTML summary written to the path provided for this run and preserved
  unchanged after submission

## Expected scientific output
By the end of this phase, the project should have:
1. one common and consistently cited Phase 04 evidence summary;
2. observation, explanation, and implication kept distinct;
3. aggregate and component-level accuracy assessed separately;
4. plausible competing explanations compared against the evidence;
5. every material scientific statement assessed as supported, partially
   supported, contradicted, inconclusive, untested, or not assessable, with its
   empirical basis stated separately;
6. discriminating follow-up diagnostics with predicted outcomes;
7. scientifically defensible interpretations with explicit scope and
   limitations;
8. **Scientific record changes** containing only additions or changes to the
   **accepted scientific record**;
9. a **User Decision Brief** with clear options to approve, proceed with
   limitations, revise, or rerun a relevant phase.

## Completion outcomes
Apply the shared completion outcomes to this phase. Mark it **Complete** only
when the selected rounds returned nonempty reports and all material
interpretations have been assessed. Mark it **Partial** when all selected rounds
ran but named scientific work or a consequential interpretation remains
incomplete. Mark it **Failed** when the completed reports provide no defensible
common evidence basis or material interpretation. A missing report or unfinished
task is a technical run failure, not a scientific completion outcome. A Partial
or Failed phase still requires a final summary that preserves usable analysis,
identifies the missing work and its scientific consequence, and presents options
to the user.

Follow the team charter and norms supplied with the run. The user starts
every run and makes every phase and interpretation decision. Completion never
approves the interpretation or starts paper writing automatically.
