#!/usr/bin/env bash
#
# First-time setup for Research Hub.
# Creates a virtual environment, installs dependencies, initializes the
# database, and runs a quick sanity check.
#
# Usage:
#   ./setup.sh           # use python3 (default)
#   PYTHON=python3.12 ./setup.sh   # specify a Python interpreter
#
set -euo pipefail

PYTHON="${PYTHON:-python3}"
REPO_ROOT="$(cd "$(dirname "$0")" && pwd)"

cd "$REPO_ROOT"

echo "══════════════════════════════════════════════════════════"
echo "  Research Hub — first-time setup"
echo "══════════════════════════════════════════════════════════"
echo

# -- 1. Check Python version ------------------------------------------------
if ! command -v "$PYTHON" &>/dev/null; then
    echo "ERROR: '$PYTHON' not found. Install Python 3.10+ and retry."
    exit 1
fi
PY_VERSION=$($PYTHON -c 'import sys; print(f"{sys.version_info[0]}.{sys.version_info[1]}")')
echo "Python:       $PY_VERSION  ($($PYTHON --version))"

# -- 2. Check Hermes --------------------------------------------------------
if command -v hermes &>/dev/null; then
    echo "Hermes:       $(hermes --version 2>/dev/null || echo 'found')"
else
    echo "Hermes:       NOT FOUND on PATH"
    echo "              Research Hub needs the 'hermes' command to run phases."
    echo "              Install it from https://github.com/NousResearch/hermes-agent"
    echo "              You can finish setup now and install Hermes later."
fi
echo

# -- 3. Create virtual environment -----------------------------------------
echo "▶ Creating virtual environment (.venv)…"
if [ -d .venv ]; then
    echo "  .venv already exists — reusing."
else
    "$PYTHON" -m venv .venv
fi
echo

# -- 4. Install dependencies and package -----------------------------------
echo "▶ Installing research-hub package (editable)…"
.venv/bin/pip install --upgrade pip --quiet
.venv/bin/pip install -e ".[dev]" --quiet
echo "  Done."
echo

# -- 5. Initialize database -------------------------------------------------
echo "▶ Initializing hub database…"
.venv/bin/python hub.py init
echo

# -- 6. Sanity check --------------------------------------------------------
echo "▶ Validating config.yaml…"
.venv/bin/python -c "import hub; hub.load_config(); print('  config.yaml: OK')"
echo

# -- 7. Next steps ----------------------------------------------------------
echo "══════════════════════════════════════════════════════════"
echo "  Setup complete!"
echo "══════════════════════════════════════════════════════════"
echo
echo "Next steps:"
echo
echo "  1. Edit config.yaml — set your workspace directory and"
echo "     map research roles to your Hermes profiles."
echo
echo "  2. Start the web UI:"
echo "       .venv/bin/python webapp.py"
echo
echo "  3. Open http://127.0.0.1:5055"
echo
if ! command -v hermes &>/dev/null; then
    echo "  4. Install Hermes Agent and create the profiles referenced"
    echo "     in config.yaml before running your first phase."
    echo
fi
