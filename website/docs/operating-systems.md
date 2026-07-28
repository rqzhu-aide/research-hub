---
sidebar_position: 2
title: "Operating Systems"
slug: /operating-systems
---

# Operating Systems

Research Hub is currently developed and validated primarily on Linux. The
Python runtime contains Windows-aware path, locking, and process-management
code, but native Windows does not yet have a supported installer or complete
end-to-end validation.

This page describes platform differences. See
[System Requirements](./system-requirements) for the software, storage, network,
and permission requirements that apply on every platform.

## Current status

| Platform | Status | Recommendation |
|---|---|---|
| Linux | Supported development and validation target | Use for research work |
| WSL2 | Linux-like but not validated as a complete Research Hub environment | Use only for careful evaluation |
| Native Windows | Partial implementation, no supported installer, incomplete migration validation | Treat as experimental |
| macOS | POSIX-compatible in part, but not validated | Treat as experimental |

## Important platform differences

| Area | Linux and POSIX | Native Windows |
|---|---|---|
| Shipped setup | `./setup.sh` | No `setup.ps1` or supported automated setup |
| Virtual environment Python | `.venv/bin/python` | `.venv\Scripts\python.exe` |
| Default Hermes root | `~/.hermes` | `%LOCALAPPDATA%\hermes` |
| Locks and process cleanup | POSIX locks and process groups | Windows locks, process groups, and Job Objects |
| Open project folder | `xdg-open`, or `open` on macOS | Explorer |

Research Hub and Hermes should run in the same platform environment. Profile
locations, memories, skills, process identifiers, and filesystem paths are not
interchangeable between native Windows and WSL2.

## Linux

The documented installation, commands, paths, and launch procedure target
Linux. Follow [Install Research Hub](./setup).

The project requires Python 3.10 or later, Git, and a working Hermes Agent
installation. Individual distributions, desktop environments, filesystems, and
hardware still differ. Confirm the complete workflow with a small project
before starting a long run.

Use a local Linux filesystem for the checkout, workspace, and Hermes profiles.
If the application runs on a remote Linux server, its Web UI still binds only
to that server's loopback interface. Research Hub does not provide a public
remote Web service.

## WSL2

WSL2 may be closer to the documented environment than a native Windows
installation, but it has not been validated as a supported Research Hub
configuration. Hermes has its own
[WSL2 guide](https://hermes-agent.nousresearch.com/docs/user-guide/windows-wsl-quickstart),
but that does not establish Research Hub compatibility.

If you evaluate WSL2:

1. Install Python, Git, Hermes, Research Hub, and all four scientific profiles
   inside the same WSL distribution.
2. Keep the active checkout and workspace in the Linux filesystem rather than
   splitting one project across Windows and WSL paths.
3. Use the WSL Hermes root and profiles. Do not expect native Windows profiles
   under `%LOCALAPPDATA%` to appear automatically.
4. Test browser access to the WSL loopback server, background task execution,
   cancellation, and cleanup.
5. Back up the workspace before upgrading either environment.

## Windows

Native Windows is experimental.

The runtime includes native handling for Hermes profile paths, file locks,
Windows reparse points, detached workers, process trees, command-length limits,
and Explorer integration. Most of the Python test suite can run on Windows.
This does not constitute a supported end-to-end release.

Current gaps include:

- no PowerShell setup script;
- Linux-oriented Makefile and command examples;
- incomplete validation of cancellation and cleanup across all failure modes;
- an unresolved migration case for older sealed records containing
  Windows-style absolute paths;
- no complete native Windows profile, browser, phase-run, upgrade, and recovery
  test.

For development evaluation only, the Linux setup steps translate approximately
to:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe hub.py init
.\.venv\Scripts\python.exe -c "import hub; hub.load_config(); print('config.yaml: OK')"
.\.venv\Scripts\python.exe webapp.py
```

These commands are not a supported Windows installer. Install and configure
Hermes separately using the current [Hermes native Windows
guide](https://hermes-agent.nousresearch.com/docs/user-guide/windows-native), then
test a
disposable project before using research data.

## macOS

macOS has not been validated. Its POSIX shell and virtual-environment layout may
allow parts of the Linux instructions to work, and the Web UI knows how to open
a project folder with `open`. The Hermes integration, locks, background
processes, cancellation, browser behavior, and complete phase workflow have not
been tested as one system.

## Evaluating an untested platform

Before using an untested platform for research:

1. Verify that `hermes --version` and `python3 --version` work.
2. Confirm Research Hub and Hermes resolve the same profile collection.
3. Complete installation without skipping configuration validation.
4. Start the Web UI and confirm that all four profiles are visible.
5. Create a disposable project and run a short phase.
6. Test completion, cancellation, cleanup, progress, log access, and rerun.
7. Restart the application and confirm the project history remains intact.
8. Inspect the run record and generated artifacts before using real data or
   substantial computation.

When reporting a platform problem, include the operating system and version,
Python version, Hermes version, installation method, filesystem type, failing
command, and relevant error output.

See [Set Up Hermes Profiles](./profile-setup) for platform-specific profile
locations and [Current Limitations](./known-limitations) for other boundaries.
