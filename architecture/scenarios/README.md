# Acceptance Scenarios

These files describe normative researcher workflows. They are not illustrative
stories. Each scenario must become an automated end-to-end test.

## Scenario format

Every scenario defines:

1. purpose;
2. initial formal state;
3. user action;
4. frozen run basis;
5. expected role execution;
6. expected run-local outputs;
7. validation and promotion result;
8. expected formal state;
9. expected UI communication;
10. prohibited behavior.

## Scenario index

| ID | Scenario | Primary contract |
|---|---|---|
| S01 | First project through P1 and P2 | Cumulative literature and method catalog |
| S02 | Full-catalog and focused P2 reruns | User scope and catalog isolation |
| S03 | P4 runs before P3 | Independent sibling phases |
| S04 | Calculation-defining method change | Exact method identity and invalidation |
| S05 | Failed run preserves current state | Promotion safety |
| S06 | Optional historical context | Lean current context and user control |
| S07 | P4 evidence revalidation | Immutable evidence lineage |
| S08 | P5 assembly and review-revision | Exact manuscript basis and review trace |
| S09 | Interrupted promotion recovery | Atomic publication and recovery |
| S10 | Complete negative scientific result | Scientific outcome is not execution state |
| S11 | User-controlled lifecycle and withdrawal | Typed no-run control commands and atomic authority transactions |
