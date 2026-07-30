# Research Hub

Research Hub is a local Web UI for running structured research workflows with [Hermes](https://hermes-agent.nousresearch.com). A research lead, theorist, data analyst, and context-separated paper reviewer work through five phases while the user chooses when to start or rerun each phase and how to use its results.

Research Hub preserves the inputs and records associated with each run. The resulting evidence remains subject to scientific review by the user.

[Read the documentation](https://rqzhu-aide.github.io/research-hub/)

## Platform support

Linux is the only currently supported Research Hub platform. Native Windows,
WSL2, and macOS remain experimental or unvalidated. See [Operating
Systems](https://rqzhu-aide.github.io/research-hub/docs/operating-systems).

## Research workflow

| Phase | Purpose |
|---|---|
| **1. Literature Review** | Establish the relevant literature, evidence boundaries, and unresolved questions |
| **2. Method Development** | Build and maintain a catalog of candidate contributions or methods |
| **3. Theoretical Development** | Choose an active method, examine its assumptions, derive results, test proofs, and identify failure modes |
| **4. Implementation & Experiments** | Independently choose an active method, implement it, and evaluate it with prespecified diagnostics and experiments |
| **5. Paper Assembly & Review** | Combine compatible theoretical and empirical work from one method branch into a manuscript, then review and revise it |

No phase starts automatically. Phase 2 publishes a valid Complete or Partial
method catalog automatically after validation. After Phase 2, the user may
independently start Phase 3 or Phase 4 by choosing an active method from the
read-only catalog in that phase. Research Hub freezes the method and version for
the run, including the exact digest of its authoritative mathematical
definition, and keeps work for the same method in one durable branch. Each sibling
phase can use available prior results and discussion from both phases on that
branch.

A calculation-defining Phase 2 change advances the method version. Earlier
Phase 3 proofs and Phase 4 code or results remain historical until a rerun
checks or recomputes them for the new version.

Phase 5 requires usable current results from Phases 1 through 4. Every
phase, including Phase 3, may be Complete or Partial — a Partial theory feeds
Phase 5 with its stated limitations carried forward; Failed never qualifies. The Phase 3 and Phase 4 results must be tied to the same
selected method snapshot. A Partial Phase 2 result requires an explicit
prerequisite override before Phase 3 or Phase 4 can start.

Read [Current Limitations](https://rqzhu-aide.github.io/research-hub/docs/known-limitations) before relying on the full workflow.

## Linux quick start

### Requirements

- Linux
- Python 3.10 or later
- Hermes Agent available as `hermes`
- One Hermes profile for each research role

```bash
git clone https://github.com/rqzhu-aide/research-hub.git
cd research-hub
./setup.sh
```

Map the four research roles to Hermes profiles in `config.yaml`, then start the interface:

```bash
.venv/bin/python webapp.py
```

Open [http://127.0.0.1:5055](http://127.0.0.1:5055).

## Useful commands

| Command | Purpose |
|---|---|
| `./setup.sh` | Create the environment, install Research Hub, initialize the registry, and validate the setup |
| `make run` | Start the local Web UI |
| `make check` | Validate `config.yaml` |
| `make test` | Run the test suite |

## Documentation

- [System Requirements](https://rqzhu-aide.github.io/research-hub/docs/system-requirements)
- [Install Research Hub](https://rqzhu-aide.github.io/research-hub/docs/setup)
- [Set Up Hermes Profiles](https://rqzhu-aide.github.io/research-hub/docs/profile-setup)
- [Create a Project](https://rqzhu-aide.github.io/research-hub/docs/project-setup)
- [Direct and Remote Operation](https://rqzhu-aide.github.io/research-hub/docs/operation-modes)
- [Agent Instructions, Memory, and Skills](https://rqzhu-aide.github.io/research-hub/docs/team-resources)
- [Review Results and Choose What Happens Next](https://rqzhu-aide.github.io/research-hub/docs/workflow/decisions)
- [Workflow Overview](https://rqzhu-aide.github.io/research-hub/docs/workflow/pipeline)
- [Configuration Reference](https://rqzhu-aide.github.io/research-hub/docs/reference/config)
- [Architecture and Integrity](https://rqzhu-aide.github.io/research-hub/docs/reference/architecture)

## License

[MIT](LICENSE)
