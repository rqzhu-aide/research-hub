#!/usr/bin/env python3

"""Process execution, bounded output, run logs, and PID supervision."""

from __future__ import annotations

import json
import logging
import os
import signal
import stat
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence



from core import launch_common
from core import project_state
from core import launch_dispatch
from core import launch_manifest

logger = logging.getLogger("launch.process")

MAX_COMMAND_OUTPUT_BYTES = 4 * 1024 * 1024


MAX_PROCESS_CONTROL_OUTPUT_BYTES = 256 * 1024


MAX_RUN_LOG_BYTES = 64 * 1024 * 1024


PROCESS_OUTPUT_CHUNK_BYTES = 64 * 1024


PROCESS_READER_JOIN_SECONDS = 2.0


PROCESS_TREE_TERMINATION_SECONDS = 5.0


RUN_LOG_LIMIT_MARKER = (
    b"\n[Research Hub stopped this run because Hermes output exceeded the "
    b"run-log safety limit.]\n"
)


def _assign_windows_kill_job(process: subprocess.Popen[Any]) -> Any | None:
    """Place a Windows process tree in a job that dies when its handle closes."""

    if os.name != "nt":
        return None
    try:
        import ctypes
        from ctypes import wintypes

        class IO_COUNTERS(ctypes.Structure):
            _fields_ = [
                ("ReadOperationCount", ctypes.c_ulonglong),
                ("WriteOperationCount", ctypes.c_ulonglong),
                ("OtherOperationCount", ctypes.c_ulonglong),
                ("ReadTransferCount", ctypes.c_ulonglong),
                ("WriteTransferCount", ctypes.c_ulonglong),
                ("OtherTransferCount", ctypes.c_ulonglong),
            ]

        class JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):
            _fields_ = [
                ("PerProcessUserTimeLimit", ctypes.c_longlong),
                ("PerJobUserTimeLimit", ctypes.c_longlong),
                ("LimitFlags", wintypes.DWORD),
                ("MinimumWorkingSetSize", ctypes.c_size_t),
                ("MaximumWorkingSetSize", ctypes.c_size_t),
                ("ActiveProcessLimit", wintypes.DWORD),
                ("Affinity", ctypes.c_size_t),
                ("PriorityClass", wintypes.DWORD),
                ("SchedulingClass", wintypes.DWORD),
            ]

        class JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
            _fields_ = [
                ("BasicLimitInformation", JOBOBJECT_BASIC_LIMIT_INFORMATION),
                ("IoInfo", IO_COUNTERS),
                ("ProcessMemoryLimit", ctypes.c_size_t),
                ("JobMemoryLimit", ctypes.c_size_t),
                ("PeakProcessMemoryUsed", ctypes.c_size_t),
                ("PeakJobMemoryUsed", ctypes.c_size_t),
            ]

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.CreateJobObjectW.argtypes = [wintypes.LPVOID, wintypes.LPCWSTR]
        kernel32.CreateJobObjectW.restype = wintypes.HANDLE
        kernel32.SetInformationJobObject.argtypes = [
            wintypes.HANDLE,
            ctypes.c_int,
            wintypes.LPVOID,
            wintypes.DWORD,
        ]
        kernel32.SetInformationJobObject.restype = wintypes.BOOL
        kernel32.AssignProcessToJobObject.argtypes = [
            wintypes.HANDLE,
            wintypes.HANDLE,
        ]
        kernel32.AssignProcessToJobObject.restype = wintypes.BOOL
        kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel32.CloseHandle.restype = wintypes.BOOL

        job = kernel32.CreateJobObjectW(None, None)
        if not job:
            return None
        limits = JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
        limits.BasicLimitInformation.LimitFlags = 0x00002000
        if not kernel32.SetInformationJobObject(
            job, 9, ctypes.byref(limits), ctypes.sizeof(limits)
        ) or not kernel32.AssignProcessToJobObject(
            job, wintypes.HANDLE(int(process._handle))  # type: ignore[attr-defined]
        ):
            kernel32.CloseHandle(job)
            return None
        return job
    except Exception:
        return None


def _terminate_windows_job(job: Any) -> None:
    import ctypes
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.TerminateJobObject.argtypes = [wintypes.HANDLE, wintypes.UINT]
    kernel32.TerminateJobObject.restype = wintypes.BOOL
    kernel32.TerminateJobObject(job, 1)


def _close_windows_job(job: Any) -> None:
    import ctypes
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL
    kernel32.CloseHandle(job)


def _terminate_windows_process_tree(pid: int) -> None:
    """Best-effort fallback when a Windows kill-on-close job is unavailable."""

    killer: subprocess.Popen[Any] | None = None
    try:
        killer = subprocess.Popen(
            ["taskkill", "/PID", str(pid), "/T", "/F"],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        try:
            killer.wait(timeout=PROCESS_TREE_TERMINATION_SECONDS)
        except subprocess.TimeoutExpired:
            killer.kill()
            killer.wait(timeout=PROCESS_TREE_TERMINATION_SECONDS)
    except (OSError, subprocess.SubprocessError):
        if killer is not None and killer.poll() is None:
            try:
                killer.kill()
            except OSError:
                pass


def _run_process_with_bounded_output(
    arguments: Sequence[str],
    *,
    timeout: int,
    max_output_bytes: int,
    merge_stderr: bool = False,
    output_writer: Callable[[bytes], None] | None = None,
    environment: Mapping[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run a process while draining at most one combined output byte budget."""

    if max_output_bytes < 1:
        raise launch_common._ProcessOutputLimitExceeded(
            "No output budget remains for the external command"
        )
    command = [str(argument) for argument in arguments]
    popen_options: dict[str, Any] = {}
    if os.name == "nt":
        popen_options["creationflags"] = getattr(
            subprocess, "CREATE_NEW_PROCESS_GROUP", 0
        )
    else:
        popen_options["start_new_session"] = True
    try:
        process = subprocess.Popen(
            command,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT if merge_stderr else subprocess.PIPE,
            env=(dict(environment) if environment is not None else None),
            **popen_options,
        )
    except OSError as exc:
        raise launch_common.LaunchError(f"Could not run {' '.join(command[:3])}: {exc}") from exc

    windows_job = _assign_windows_kill_job(process)
    buffers = {"stdout": bytearray(), "stderr": bytearray()}
    state_lock = threading.Lock()
    tree_lock = threading.Lock()
    overflow = threading.Event()
    termination_requested = threading.Event()
    reader_failures: list[BaseException] = []
    tree_terminated = False
    total = 0

    def stop_process() -> None:
        nonlocal tree_terminated
        termination_requested.set()
        with tree_lock:
            if tree_terminated:
                return
            tree_terminated = True
            if os.name == "nt":
                if windows_job is not None:
                    try:
                        _terminate_windows_job(windows_job)
                    except OSError:
                        _terminate_windows_process_tree(process.pid)
                else:
                    _terminate_windows_process_tree(process.pid)
            else:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                except OSError:
                    if process.poll() is None:
                        try:
                            process.kill()
                        except OSError:
                            pass
            if process.poll() is None:
                try:
                    process.kill()
                except OSError:
                    pass

    def release_process_tree() -> None:
        nonlocal tree_terminated, windows_job
        if os.name != "nt":
            return
        with tree_lock:
            if windows_job is not None:
                try:
                    _close_windows_job(windows_job)
                finally:
                    windows_job = None
                    tree_terminated = True

    def join_readers(timeout: float) -> list[threading.Thread]:
        deadline = time.monotonic() + timeout
        for reader in readers:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            reader.join(remaining)
        return [reader for reader in readers if reader.is_alive()]

    def wait_after_stop() -> int | None:
        try:
            return process.wait(timeout=PROCESS_TREE_TERMINATION_SECONDS)
        except subprocess.TimeoutExpired:
            try:
                process.kill()
            except OSError:
                pass
            try:
                return process.wait(timeout=PROCESS_TREE_TERMINATION_SECONDS)
            except subprocess.TimeoutExpired:
                return None

    def consume(name: str, stream: Any) -> None:
        nonlocal total
        try:
            while True:
                chunk = stream.read(PROCESS_OUTPUT_CHUNK_BYTES)
                if not chunk:
                    break
                with state_lock:
                    remaining = max_output_bytes - total
                    accepted = chunk[: max(0, remaining)]
                    total += len(accepted)
                    if len(accepted) != len(chunk):
                        overflow.set()
                if accepted:
                    if output_writer is None:
                        buffers[name].extend(accepted)
                    else:
                        output_writer(accepted)
                if overflow.is_set():
                    stop_process()
        except BaseException as exc:
            if not termination_requested.is_set():
                with state_lock:
                    reader_failures.append(exc)
            stop_process()
        finally:
            try:
                stream.close()
            except OSError:
                pass

    readers: list[threading.Thread] = []
    if process.stdout is not None:
        readers.append(
            threading.Thread(
                target=consume,
                args=("stdout", process.stdout),
                daemon=True,
            )
        )
    if not merge_stderr and process.stderr is not None:
        readers.append(
            threading.Thread(
                target=consume,
                args=("stderr", process.stderr),
                daemon=True,
            )
        )
    for reader in readers:
        reader.start()

    timed_out = False
    wait_failed = False
    try:
        return_code = process.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        timed_out = True
        stop_process()
        stopped_code = wait_after_stop()
        wait_failed = stopped_code is None
        return_code = stopped_code if stopped_code is not None else -1
    finally:
        release_process_tree()

    lingering_readers = join_readers(PROCESS_READER_JOIN_SECONDS)
    if lingering_readers:
        stop_process()
        lingering_readers = join_readers(PROCESS_READER_JOIN_SECONDS)

    stdout = bytes(buffers["stdout"]).decode("utf-8", errors="replace")
    stderr = bytes(buffers["stderr"]).decode("utf-8", errors="replace")
    if wait_failed:
        raise launch_common.LaunchError(
            f"Could not terminate the process tree for {' '.join(command[:3])}"
        )
    if lingering_readers:
        raise launch_common.LaunchError(
            f"Process-tree output did not close after termination: "
            f"{' '.join(command[:3])}"
        )
    if reader_failures:
        raise launch_common.LaunchError(
            f"Could not record output from {' '.join(command[:3])}: "
            f"{reader_failures[0]}"
        ) from reader_failures[0]
    if timed_out:
        raise subprocess.TimeoutExpired(
            command, timeout, output=stdout, stderr=stderr
        )
    if overflow.is_set():
        raise launch_common._ProcessOutputLimitExceeded(
            f"External command output exceeded the {max_output_bytes:,}-byte safety limit: "
            f"{' '.join(command[:3])}"
        )
    return subprocess.CompletedProcess(command, return_code, stdout, stderr)


def _run_command(
    arguments: Sequence[str],
    *,
    timeout: int = 20,
    environment: Mapping[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    try:
        return _run_process_with_bounded_output(
            arguments,
            timeout=timeout,
            max_output_bytes=MAX_COMMAND_OUTPUT_BYTES,
            environment=environment,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise launch_common.LaunchError(f"Could not run {' '.join(arguments[:3])}: {exc}") from exc


def _hermes_environment(
    hermes_root: str | os.PathLike[str] | None,
    *,
    base: Mapping[str, str] | None = None,
) -> dict[str, str] | None:
    """Copy an environment and bind Hermes to one resolved profile root."""

    if hermes_root is None:
        return dict(base) if base is not None else None
    environment = dict(os.environ if base is None else base)
    for key in list(environment):
        if key.casefold() in {
            "hermes_home",
            "research_hub_hermes_root",
        }:
            environment.pop(key)
    root = str(Path(hermes_root))
    environment["HERMES_HOME"] = root
    environment["RESEARCH_HUB_HERMES_ROOT"] = root
    return environment


def _open_new_run_log(log_path: Path) -> Any:
    """Create a new regular run log without following or reusing a path."""

    flags = (
        os.O_WRONLY
        | os.O_CREAT
        | os.O_EXCL
        | os.O_APPEND
        | getattr(os, "O_BINARY", 0)
    )
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(log_path, flags, 0o600)
    except FileExistsError as exc:
        raise launch_common.LaunchError(
            f"Run log destination already exists; refusing to reuse it: {log_path}"
        ) from exc
    except OSError as exc:
        raise launch_common.LaunchError(f"Run log could not be created safely: {log_path}") from exc
    try:
        opened_metadata = os.fstat(descriptor)
        path_metadata = log_path.lstat()
        if (
            launch_common._metadata_is_link_or_reparse(path_metadata)
            or not stat.S_ISREG(opened_metadata.st_mode)
            or not os.path.samestat(opened_metadata, path_metadata)
        ):
            raise launch_common.LaunchError(
                f"Run log must be one newly created regular file: {log_path}"
            )
        if os.name != "nt":
            os.fchmod(descriptor, 0o600)
        handle = os.fdopen(
            descriptor,
            "a",
            encoding="utf-8",
            newline="\n",
            buffering=1,
        )
    except Exception:
        os.close(descriptor)
        raise
    return handle


def _write_worker_output(payload: bytes, *, descriptor: int | None = None) -> None:
    """Forward bounded Hermes output to the worker's inherited run log."""

    inherited = _worker_log_descriptor()
    if descriptor is not None and inherited != descriptor:
        raise launch_common.LaunchError("The inherited run-log descriptor changed during execution")
    binary = getattr(sys.stdout, "buffer", None)
    if binary is not None:
        binary.write(payload)
        binary.flush()
        return
    sys.stdout.write(payload.decode("utf-8", errors="replace"))
    sys.stdout.flush()


def _worker_log_descriptor() -> int:
    """Return the exact inherited descriptor used for persistent worker output."""

    try:
        descriptor = int(sys.stdout.fileno())
    except (AttributeError, OSError, TypeError, ValueError) as exc:
        raise launch_common.LaunchError("The worker has no usable inherited run-log descriptor") from exc
    if descriptor < 0:
        raise launch_common.LaunchError("The worker has no usable inherited run-log descriptor")
    return descriptor


def _run_log_descriptor_metadata(descriptor: int) -> os.stat_result:
    """Inspect a bound run-log descriptor without reopening its pathname."""

    try:
        metadata = os.fstat(descriptor)
    except (OSError, ValueError) as exc:
        raise launch_common.LaunchError("The inherited run-log descriptor is unavailable") from exc
    if not stat.S_ISREG(metadata.st_mode):
        raise launch_common.LaunchError("The inherited run-log descriptor is not a regular file")
    return metadata


def _verified_run_log_descriptor(
    log_path: Path,
    descriptor: int,
    *,
    expected: os.stat_result | None = None,
) -> os.stat_result:
    """Require the named log path to identify the inherited regular file."""

    descriptor_metadata = _run_log_descriptor_metadata(descriptor)
    if expected is not None and not os.path.samestat(descriptor_metadata, expected):
        raise launch_common.LaunchError("The inherited run-log descriptor changed during execution")
    try:
        path_metadata = log_path.lstat()
    except (OSError, ValueError) as exc:
        raise launch_common.LaunchError(
            f"Run log no longer identifies the inherited worker output: {log_path}"
        ) from exc
    if (
        not stat.S_ISREG(descriptor_metadata.st_mode)
        or launch_common._metadata_is_link_or_reparse(path_metadata)
        or not os.path.samestat(descriptor_metadata, path_metadata)
    ):
        raise launch_common.LaunchError(
            f"Run log no longer identifies the inherited worker output: {log_path}"
        )
    return descriptor_metadata


def _flush_worker_log_streams() -> None:
    """Flush Python's wrappers before measuring or truncating their shared file."""

    for stream in (sys.stdout, sys.stderr):
        try:
            stream.flush()
        except (AttributeError, OSError, ValueError) as exc:
            raise launch_common.LaunchError("The inherited run-log stream could not be flushed") from exc


def _run_logged_command(
    arguments: Sequence[str],
    *,
    timeout: int,
    project_dir: Path,
    phase_slug: str,
    run_id: str,
    environment: Mapping[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run Hermes while keeping the persistent run log within its byte cap."""

    log_path = launch_common.run_log_path(project_dir, phase_slug, run_id)
    descriptor = _worker_log_descriptor()
    _flush_worker_log_streams()
    bound_metadata = _verified_run_log_descriptor(log_path, descriptor)
    try:
        remaining = MAX_RUN_LOG_BYTES - bound_metadata.st_size
        if remaining <= len(RUN_LOG_LIMIT_MARKER):
            marker = RUN_LOG_LIMIT_MARKER[: max(0, remaining)]
            if marker:
                _write_worker_output(marker, descriptor=descriptor)
            raise launch_common._ProcessOutputLimitExceeded(
                f"Run log reached the {MAX_RUN_LOG_BYTES:,}-byte safety limit"
            )
        output_budget = remaining - len(RUN_LOG_LIMIT_MARKER)
        try:
            return _run_process_with_bounded_output(
                arguments,
                timeout=timeout,
                max_output_bytes=output_budget,
                merge_stderr=True,
                output_writer=lambda payload: _write_worker_output(
                    payload, descriptor=descriptor
                ),
                environment=environment,
            )
        except launch_common._ProcessOutputLimitExceeded as exc:
            _write_worker_output(RUN_LOG_LIMIT_MARKER, descriptor=descriptor)
            raise launch_common._ProcessOutputLimitExceeded(
                f"Hermes output exceeded the {MAX_RUN_LOG_BYTES:,}-byte run-log safety limit"
            ) from exc
    finally:
        _flush_worker_log_streams()
        _verified_run_log_descriptor(
            log_path, descriptor, expected=bound_metadata
        )


def _truncate_run_log(
    log_path: Path,
    *,
    descriptor: int | None = None,
    expected: os.stat_result | None = None,
) -> None:
    """Enforce the persistent cap after all worker cleanup messages are written."""

    inherited = _worker_log_descriptor() if descriptor is None else int(descriptor)
    _flush_worker_log_streams()
    opened_metadata = _run_log_descriptor_metadata(inherited)
    if expected is not None and not os.path.samestat(opened_metadata, expected):
        raise launch_common.LaunchError("The inherited run-log descriptor changed during execution")
    try:
        if opened_metadata.st_size > MAX_RUN_LOG_BYTES:
            marker = RUN_LOG_LIMIT_MARKER[:MAX_RUN_LOG_BYTES]
            retained = MAX_RUN_LOG_BYTES - len(marker)
            os.ftruncate(inherited, retained)
            os.lseek(inherited, retained, os.SEEK_SET)
            os.write(inherited, marker)
            os.fsync(inherited)
    except OSError as exc:
        raise launch_common.LaunchError(f"Run log could not be capped safely: {log_path}") from exc
    _verified_run_log_descriptor(log_path, inherited, expected=opened_metadata)


def _process_identity(pid: int | None) -> str | None:
    """Return a process birth identity so a recycled PID is never trusted."""

    if not pid:
        return None
    if os.name == "nt":
        try:
            import ctypes
            from ctypes import wintypes

            class FILETIME(ctypes.Structure):
                _fields_ = [("low", wintypes.DWORD), ("high", wintypes.DWORD)]

            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
            kernel32.OpenProcess.restype = wintypes.HANDLE
            kernel32.GetProcessTimes.argtypes = [
                wintypes.HANDLE,
                ctypes.POINTER(FILETIME),
                ctypes.POINTER(FILETIME),
                ctypes.POINTER(FILETIME),
                ctypes.POINTER(FILETIME),
            ]
            kernel32.GetProcessTimes.restype = wintypes.BOOL
            kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
            kernel32.CloseHandle.restype = wintypes.BOOL
            handle = kernel32.OpenProcess(0x1000, False, int(pid))
            if not handle:
                return None
            try:
                creation, exit_time, kernel, user = FILETIME(), FILETIME(), FILETIME(), FILETIME()
                if not kernel32.GetProcessTimes(
                    handle,
                    ctypes.byref(creation),
                    ctypes.byref(exit_time),
                    ctypes.byref(kernel),
                    ctypes.byref(user),
                ):
                    return None
                ticks = (int(creation.high) << 32) | int(creation.low)
                return f"windows:{ticks}"
            finally:
                kernel32.CloseHandle(handle)
        except Exception:
            return None
    proc = Path("/proc") / str(pid)
    try:
        stat = (proc / "stat").read_text(encoding="utf-8")
        remainder = stat.rsplit(")", 1)[1].split()
        start_ticks = remainder[19]
        executable = os.readlink(proc / "exe")
        return f"proc:{start_ticks}:{executable}"
    except (OSError, IndexError, ValueError):
        pass
    try:
        shown = _run_process_with_bounded_output(
            ["ps", "-p", str(pid), "-o", "lstart=,comm="],
            timeout=2,
            max_output_bytes=MAX_PROCESS_CONTROL_OUTPUT_BYTES,
        )
    except (launch_common.LaunchError, subprocess.SubprocessError):
        return None
    value = shown.stdout.strip()
    return f"ps:{value}" if shown.returncode == 0 and value else None


def _pid_is_alive(pid: int | None, expected_identity: str | None = None) -> bool:
    """Conservatively report whether the recorded process may still be alive.

    Failure to read a live PID's birth identity is uncertainty, not evidence
    that the recorded worker has stopped.  Callers that need to distinguish an
    exact match from uncertainty use :func:`_pid_identity_status`.
    """

    if not pid:
        return False
    try:
        os.kill(int(pid), 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except (OSError, ValueError):
        return False
    if expected_identity:
        observed_identity = _process_identity(pid)
        if observed_identity is not None and observed_identity != expected_identity:
            return False
    return True


def _pid_identity_status(pid: int | None, expected_identity: str | None) -> str:
    """Return absent, matching, mismatched, or unverifiable for one PID."""

    if not _pid_is_alive(pid):
        return "absent"
    if not expected_identity:
        return "unverifiable"
    observed_identity = _process_identity(pid)
    if observed_identity is None:
        return "unverifiable"
    return "matching" if observed_identity == expected_identity else "mismatched"


def _terminate_pid_tree(pid: int, expected_identity: str | None = None) -> None:
    if expected_identity and _process_identity(pid) != expected_identity:
        raise launch_common.LaunchError(f"Refusing to stop recycled or unverified process PID {pid}")
    if os.name == "nt":
        try:
            result = _run_process_with_bounded_output(
                ["taskkill", "/PID", str(pid), "/T", "/F"],
                timeout=15,
                max_output_bytes=MAX_PROCESS_CONTROL_OUTPUT_BYTES,
            )
        except (launch_common.LaunchError, subprocess.SubprocessError) as exc:
            raise launch_common.LaunchError(f"Could not stop process {pid}: {exc}") from exc
        if result.returncode not in {0, 128}:
            detail = (result.stderr or result.stdout).strip()
            raise launch_common.LaunchError(f"Could not stop process {pid}: {detail}")
        return
    try:
        os.killpg(os.getpgid(pid), signal.SIGTERM)
    except ProcessLookupError:
        return
    except OSError as exc:
        raise launch_common.LaunchError(f"Could not stop process {pid}: {exc}") from exc


def _task_list(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        for key in ("tasks", "items", "data"):
            nested = payload.get(key)
            if isinstance(nested, list):
                return [item for item in nested if isinstance(item, dict)]
    return []


def _board_slugs(payload: Any) -> set[str]:
    if isinstance(payload, dict):
        payload = payload.get("boards", payload.get("items", []))
    if not isinstance(payload, list):
        return set()
    return {
        str(board.get("slug"))
        for board in payload
        if isinstance(board, dict) and board.get("slug")
    }


def _stop_external_tasks(
    project_dir: Path,
    phase_slug: str,
    run_id: str,
    manifest: Mapping[str, Any] | None = None,
) -> list[str]:
    """Archive every run-scoped Hermes task and stop its current worker."""

    warnings: list[str] = []
    try:
        manifest = dict(manifest or launch_manifest._read_manifest(project_dir, phase_slug, run_id))
    except Exception as exc:
        return [f"Could not load run manifest for task cleanup: {exc}"]
    task_ids: set[str] = set()
    try:
        run = project_state.get_run(project_dir, phase_slug, run_id)
        for round_state in run.get("rounds", []):
            task_ids.update(
                str(task["task_id"])
                for task in round_state.get("tasks", [])
                if task.get("task_id")
            )
    except Exception as exc:
        warnings.append(f"Could not read recorded task IDs: {exc}")

    try:
        listed = _run_command(
            [
                str(manifest["hermes_executable"]),
                "kanban",
                "--board",
                str(manifest["board_slug"]),
                "list",
                "--json",
            ],
            environment=_hermes_environment(launch_manifest._manifest_hermes_root(manifest)),
        )
    except Exception as exc:
        warnings.append(f"Could not list run-scoped Hermes tasks: {exc}")
        listed = None
    if listed is not None and listed.returncode == 0:
        try:
            short_id = run_id.split("-", 1)[0]
            for item in _task_list(json.loads(listed.stdout or "[]")):
                if f"[{short_id}]" in str(item.get("title", "")) and item.get("id"):
                    task_ids.add(str(item["id"]))
        except (TypeError, ValueError) as exc:
            warnings.append(f"Could not parse board task list: {exc}")
    elif listed is not None:
        warnings.append(
            "Could not list run-scoped Hermes tasks: "
            + (listed.stderr or listed.stdout).strip()
        )

    for task_id in sorted(task_ids):
        warning = _archive_external_task(manifest, task_id)
        if warning:
            warnings.append(warning)
    for warning in warnings:
        logger.warning("Task cleanup pending: %s", warning)
    return warnings


def _archive_external_task(
    manifest: Mapping[str, Any], task_id: str
) -> str | None:
    """Stop and archive one exact Hermes task, returning an uncertainty warning."""

    status = ""
    try:
        status = str(launch_dispatch._show_task(manifest, task_id).get("status", ""))
    except Exception:
        # Still attempt the exact archive. Its return code is the cleanup proof.
        pass
    if status in {"done", "archived"}:
        return None
    if status not in {"blocked", ""}:
        try:
            _run_command(
                [
                    str(manifest["hermes_executable"]),
                    "kanban",
                    "--board",
                    str(manifest["board_slug"]),
                    "block",
                    task_id,
                    "Research Hub stopped this user-controlled run.",
                ],
                environment=_hermes_environment(launch_manifest._manifest_hermes_root(manifest)),
            )
        except Exception:
            pass
    try:
        archived = _run_command(
            [
                str(manifest["hermes_executable"]),
                "kanban",
                "--board",
                str(manifest["board_slug"]),
                "archive",
                task_id,
            ],
            environment=_hermes_environment(launch_manifest._manifest_hermes_root(manifest)),
        )
    except Exception as exc:
        return f"Could not archive Hermes task {task_id}: {exc}"
    if archived.returncode != 0:
        detail = (archived.stderr or archived.stdout).strip()
        return f"Could not archive Hermes task {task_id}: {detail or 'unknown error'}"
    return None
