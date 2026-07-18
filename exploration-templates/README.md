# Exploration Phase Templates

These templates are read by the Research Hub orchestrator when deploying the
**exploration phase** (idea formation). The orchestrator fills `{{placeholders}}`
with project-specific values and writes the results to agent profiles and kanban
tasks.

## File Index

| File | Deployed To | Purpose |
|------|-------------|---------|
| `setting-template.md` | Project's `setting.md` (if not provided) | Scaffold for the user to fill in |
| `proposer-memory.md` | Proposer profile's `MEMORY.md` | Persistent role + project context |
| `critic-memory.md` | Critic profile's `MEMORY.md` | Persistent role + project context |
| `task-bodies/proposer-r1.md` | Kanban task body | Round 1: cold-start exploration |
| `task-bodies/proposer-rmid.md` | Kanban task body | Middle rounds: respond to critique |
| `task-bodies/proposer-rfinal.md` | Kanban task body | Final round: synthesize |
| `task-bodies/critic-r1.md` | Kanban task body | Round 1: evaluate breadth |
| `task-bodies/critic-rmid.md` | Kanban task body | Middle rounds: probe feasibility |
| `task-bodies/critic-rfinal.md` | Kanban task body | Final round: readiness verdict |

## Placeholder Reference

All templates use `{{placeholder_name}}` syntax.

### Memory templates
| Placeholder | Source | Example |
|-------------|--------|---------|
| `{{project_id}}` | DB | `1` |
| `{{project_name}}` | DB | `Constrained RL` |
| `{{settings_content}}` | `setting.md` file | (full file content) |
| `{{project_dir}}` | Hub filesystem | `/home/tez/.../project-001-constrained_rl` |
| `{{collaborator_profile}}` | Hub config | `reviewer` |
| `{{max_rounds}}` | User setting | `3` |

### Task body templates
| Placeholder | Source | Example |
|-------------|--------|---------|
| `{{round_num}}` | Loop counter | `2` |
| `{{max_rounds}}` | User setting | `3` |
| `{{output_path}}` | Hub convention | `phases/00-idea/proposer/round-02.md` |
| `{{prev_critique_path}}` | Hub convention | `phases/00-idea/critic/round-01.md` |
| `{{proposal_path}}` | Hub convention | `phases/00-idea/proposer/round-02.md` |

## Round Position Logic

The orchestrator selects the task body template by round position:

| Condition | Template suffix | Example (max_rounds=3) |
|-----------|----------------|------------------------|
| `round_num == 1` | `-r1` | Round 1 |
| `1 < round_num < max_rounds` | `-rmid` | Round 2 |
| `round_num == max_rounds` | `-rfinal` | Round 3 |

Edge cases:
- `max_rounds == 1`: the single round uses `-rfinal`.
- `max_rounds == 2`: round 1 uses `-r1`, round 2 uses `-rfinal` (no middle).
