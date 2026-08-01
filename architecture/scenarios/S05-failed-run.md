# S05: Failed Run Preserves Current State

## Purpose

Verify that incomplete or invalid work cannot displace a valid current record.

## Initial state

- A valid current P3 record exists for a method.

## User action

The user launches a P3 rerun. A tool failure stops execution before the data
analyst and research lead can complete their required work, so no valid lead
submission exists.

## Expected behavior

- The run folder preserves the completed role artifacts, event record, and
  operational failure reason.
- The run enters `failed` without entering validation or promotion.
- The previous P3 current record remains unchanged.
- The failed attempt is visible in run history but is not a default scientific
  input.
- The UI reports what failed, what run-local work remains available, and the
  smallest user-controlled rerun action.

## Prohibited behavior

- An incomplete role sequence cannot become current.
- The system cannot hide or delete the failed attempt.
- Failure cannot launch a repair run automatically.
- A complete negative or inconclusive scientific result cannot be mislabeled as
  an execution failure.
