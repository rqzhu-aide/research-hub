# Invalid fixtures

Each file isolates one authority or workflow violation. Package validation must
reject all twelve.

| Fixture | Expected rejection |
|---|---|
| `authority-replay-existing-evidence-reset.invalid.json` | A complete initial evidence projection cannot reset a subject already present at the authoritative checkpoint. |
| `authority-event-alignment-missing-prior-state.invalid.json` | A state-dependent alignment update must bind the immediately prior subject state. |
| `authority-event-cross-family.invalid.json` | An alignment event cannot also change research attention. |
| `authority-event-evidence-reclassification-missing-prior-state.invalid.json` | A noninitial evidence reclassification must bind the immediately prior subject state. |
| `authority-event-withdraw-current.invalid.json` | Withdrawal cannot leave a generation formal and current. |
| `decision-auto-action.invalid.json` | A displayed action cannot authorize automatic execution. |
| `formal-withdrawal-nonformal.invalid.json` | A withdrawal command must freeze a target whose derived publication state is formal. |
| `method-lifecycle-no-op.invalid.json` | A lifecycle command must change active to retired or retired to active. |
| `publication-receipt-research-run-withdraw.invalid.json` | An ordinary research run cannot withdraw a formal generation. |
| `record-state-old-method-included.invalid.json` | Evidence from an older method version must be excluded and outdated, not included as exact current evidence. |
| `run-manifest-current-only-history.invalid.json` | A current-only manifest cannot include selected history. |
| `scientific-record-mutable-position.invalid.json` | Immutable scientific content cannot contain derived record position. |

These fixtures test authorization, lifecycle, event-family, immutable-content, and derived-state
boundaries. They do not test scientific truth.