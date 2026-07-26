# Research Hub

Research Hub is a local Web UI for running structured, multi-agent research workflows with [Hermes](https://hermes-agent.nousresearch.com). It coordinates specialized AI agents — a research lead, theorist, data analyst, and independent paper reviewer — through a five-phase pipeline from literature review to final manuscript.

**The central rule: nothing advances automatically.** You start every phase run, review the evidence, and decide whether to approve, revise, or rerun. Agents do the research; you control the workflow.

📖 **[Full documentation →](https://rqzhu-aide.github.io/research-hub/)**

---

## The workflow

Research Hub organizes a project into five sequential phases. Each phase produces evidence that becomes trusted context for the next — but only after you approve it.

| Phase | What happens |
|-------|-------------|
| **1. Literature Review** | Survey prior work in parallel, identify gaps |
| **2. Method Development** | Brainstorm genuinely new methods, select one |
| **3. Theoretical Development** | Prove theorems, establish rate bounds |
| **4. Implementation & Experiments** | Implement in code, run benchmarks (preliminary → comprehensive) |
| **5. Paper Assembly & Review** | Assemble manuscript, then independent review & revision |

Phases 4 and 5 each have **two run modes** with gating — you can't benchmark unvalidated code or review an unassembled paper.

See the [pipeline overview](https://rqzhu-aide.github.io/research-hub/docs/workflow/pipeline) and individual [phase pages](https://rqzhu-aide.github.io/research-hub/docs/category/workflow) for details.

---

## Quick start

### Prerequisites

| Requirement | Notes |
|---|---|
| Python 3.10+ | 3.11+ recommended |
| Hermes Agent | The `hermes` command must be on `PATH` |

You also need a Hermes profile for each research role. See the [setup guide](https://rqzhu-aide.github.io/research-hub/docs/setup).

### Install & run

```bash
git clone <repo-url> research-hub
cd research-hub
./setup.sh
```

Then configure `config.yaml` (map research roles to Hermes profiles) and start the server:

```bash
.venv/bin/python webapp.py
```

Open [http://127.0.0.1:5055](http://127.0.0.1:5055), create a project, and start a phase run.

### Commands

| Command | What it does |
|---|---|
| `./setup.sh` | First-time setup: venv, install, init, sanity check |
| `make run` | Start the web UI |
| `make test` | Run the full test suite |
| `make check` | Validate `config.yaml` |

---

## Documentation

All details live on the documentation site:

- **[Pipeline Overview](https://rqzhu-aide.github.io/research-hub/docs/workflow/pipeline)** — how the five phases connect
- **[Phase Guides](https://rqzhu-aide.github.io/research-hub/docs/category/workflow)** — per-phase breakdowns
- **[Configuration Reference](https://rqzhu-aide.github.io/research-hub/docs/reference/config)** — full `config.yaml` schema
- **[Architecture](https://rqzhu-aide.github.io/research-hub/docs/reference/architecture)** — how the system works under the hood

## License

Private project.
