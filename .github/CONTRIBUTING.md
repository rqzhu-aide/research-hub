# Contributing to Research Hub

## Development setup

```bash
git clone <repo-url> research-hub
cd research-hub
make install-dev   # creates .venv, installs runtime + test deps
```

## Running tests

```bash
make test
```

All tests must pass before a pull request can be merged. The test suite
covers the full run lifecycle, state migration, manifest sealing, and
config validation. A contract suite verifies that the shipped `config.yaml`
works with every code path.

## Project layout

See the [Repository structure](../README.md#repository-structure) section
of the README. Key conventions:

- **`core/`** is the application package — all internal modules use
  `from core import ...` or `from core.<module> import ...`. No `sys.path`
  hacks.
- **`config/`** holds playbooks and team definitions. Phase slugs are
  opaque identifiers; the `name` field in `config.yaml` is the display name.
- **`tests/`** imports via `from core import ...`, never via `sys.path`
  manipulation.

## Before submitting a pull request

1. Run `make test` — all tests must pass.
2. Run `make check` — validate `config.yaml`.
3. If you added a new phase or changed phase behavior, add or update tests
   in `tests/test_shipped_config_contract.py`.
4. If you changed `config.yaml` folder paths or phase slugs, update the
   README examples to match.
5. Do not commit `hub.db`, `.venv/`, or project runtime data.
