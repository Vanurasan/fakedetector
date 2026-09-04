"""Private bounded subprocess execution for trusted application-built argv."""

from __future__ import annotations

import os
import subprocess
from collections.abc import Sequence
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from time import monotonic as _monotonic
from time import sleep as _sleep
from typing import IO, Literal

from fakedetector.core._cleanup_safety import _CleanupSafetyBarrier

_READ_CHUNK_BYTES = 64 * 1024
_POLL_INTERVAL_SECONDS = 0.005
_STDOUT_EOF_WAIT_SECONDS = 0.25
_TERMINATE_WAIT_SECONDS = 1.0
_KILL_WAIT_SECONDS = 1.0

ProcessInfrastructurePhase = Literal[
    "start",
    "stdout_read",
    "stdout_close",
    "wait",
    "termination",
]


class ProcessInfrastructureError(Exception):
    """Report one safe process infrastructure failure without leaking details."""

    def __init__(
        self,
        phase: ProcessInfrastructurePhase,
        *,
        _cleanup_safety_barrier: _CleanupSafetyBarrier | None = None,
    ) -> None:
        if (phase == "termination") != (_cleanup_safety_barrier is not None):
            raise ValueError("termination safety barrier does not match process phase")
        super().__init__("Subprocess infrastructure failed.")
        self.phase = phase
        self._cleanup_safety_barrier = _cleanup_safety_barrier


class ProcessTimeoutError(Exception):
    """Report a deadline only after the child has been stopped and reaped."""

    def __init__(self) -> None:
        super().__init__("Subprocess timed out.")


class ProcessOutputLimitError(Exception):
    """Report bounded stdout overflow only after the child has been reaped."""

    def __init__(self) -> None:
        super().__init__("Subprocess stdout exceeded its limit.")


@dataclass(frozen=True, slots=True)
class ProcessResult:
    """Factual normal child completion, including a possible non-zero exit."""

    return_code: int
    stdout: bytes | None


class _ProcessTerminationBarrier:
    """Retain one unresolved child and retry terminate/kill/reap boundedly."""

    def __init__(self, process: subprocess.Popen[bytes]) -> None:
        self._process: subprocess.Popen[bytes] | None = process
        self._confirmed = False
        self._lock = Lock()

    def try_confirm_safe(self) -> bool:
        """Retry the fixed escalation and forget the handle only after reap."""
        with self._lock:
            if self._confirmed:
                return True
            process = self._process
            if process is None:
                return False

            with suppress(OSError):
                process.terminate()
            if self._wait(process, _TERMINATE_WAIT_SECONDS):
                return self._mark_confirmed()

            with suppress(OSError):
                process.kill()
            if self._wait(process, _KILL_WAIT_SECONDS):
                return self._mark_confirmed()
            return False

    @staticmethod
    def _wait(process: subprocess.Popen[bytes], timeout: float) -> bool:
        try:
            process.wait(timeout=timeout)
        except (OSError, subprocess.TimeoutExpired):
            return False
        return True

    def _mark_confirmed(self) -> bool:
        self._confirmed = True
        self._process = None
        return True


def run_bounded_process(
    arguments: Sequence[str],
    *,
    cwd: Path,
    timeout_seconds: float,
    stdout_limit_bytes: int | None = None,
) -> ProcessResult:
    """Run trusted argv with discarded output or a hard-bounded stdout capture."""
    argv = _validated_argv(arguments)
    if timeout_seconds <= 0:
        raise ValueError("timeout_seconds must be greater than zero")
    if stdout_limit_bytes is not None and stdout_limit_bytes < 0:
        raise ValueError("stdout_limit_bytes must not be negative")

    process = _start_process(
        argv,
        cwd=cwd,
        capture_stdout=stdout_limit_bytes is not None,
    )
    if stdout_limit_bytes is None:
        return _wait_without_capture(process, timeout_seconds=timeout_seconds)
    return _wait_with_bounded_capture(
        process,
        timeout_seconds=timeout_seconds,
        stdout_limit_bytes=stdout_limit_bytes,
    )


def _validated_argv(arguments: Sequence[str]) -> tuple[str, ...]:
    if isinstance(arguments, (str, bytes)):
        raise TypeError("arguments must be a sequence of argv elements")
    argv = tuple(arguments)
    if not argv:
        raise ValueError("arguments must not be empty")
    if any(not isinstance(argument, str) for argument in argv):
        raise TypeError("every argv element must be a string")
    return argv


def _start_process(
    arguments: tuple[str, ...],
    *,
    cwd: Path,
    capture_stdout: bool,
) -> subprocess.Popen[bytes]:
    try:
        return subprocess.Popen(
            arguments,
            shell=False,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE if capture_stdout else subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            cwd=cwd,
        )
    except OSError:
        raise ProcessInfrastructureError("start") from None


def _wait_without_capture(
    process: subprocess.Popen[bytes],
    *,
    timeout_seconds: float,
) -> ProcessResult:
    return_code = _wait_for_execution(process, timeout_seconds=timeout_seconds)
    return ProcessResult(return_code=return_code, stdout=None)


def _wait_with_bounded_capture(
    process: subprocess.Popen[bytes],
    *,
    timeout_seconds: float,
    stdout_limit_bytes: int,
) -> ProcessResult:
    stdout_pipe = process.stdout
    assert stdout_pipe is not None
    execution_error: (
        ProcessInfrastructureError | ProcessTimeoutError | ProcessOutputLimitError | None
    ) = None
    return_code: int | None = None
    output = bytearray()
    try:
        _make_stdout_nonblocking(stdout_pipe)
        return_code = _capture_until_complete(
            process,
            stdout_pipe,
            output=output,
            stdout_limit_bytes=stdout_limit_bytes,
            timeout_seconds=timeout_seconds,
        )
    except (
        ProcessInfrastructureError,
        ProcessTimeoutError,
        ProcessOutputLimitError,
    ) as error:
        execution_error = _stop_after_capture_failure(process, error)

    close_failed = False
    try:
        stdout_pipe.close()
    except OSError:
        close_failed = True

    if (
        isinstance(execution_error, ProcessInfrastructureError)
        and execution_error.phase == "termination"
    ):
        raise execution_error
    if (
        isinstance(execution_error, ProcessInfrastructureError)
        and execution_error.phase == "stdout_read"
    ):
        raise execution_error
    if close_failed:
        raise ProcessInfrastructureError("stdout_close") from None
    if execution_error is not None:
        raise execution_error
    assert return_code is not None
    return ProcessResult(return_code=return_code, stdout=bytes(output))


def _make_stdout_nonblocking(stdout_pipe: IO[bytes]) -> None:
    try:
        os.set_blocking(stdout_pipe.fileno(), False)
    except OSError:
        raise ProcessInfrastructureError("stdout_read") from None


def _capture_until_complete(
    process: subprocess.Popen[bytes],
    stdout_pipe: IO[bytes],
    *,
    output: bytearray,
    stdout_limit_bytes: int,
    timeout_seconds: float,
) -> int:
    execution_deadline = _monotonic() + timeout_seconds
    stdout_deadline: float | None = None
    stdout_eof = False

    while True:
        if not stdout_eof:
            stdout_eof = _read_available_stdout(
                stdout_pipe,
                output=output,
                stdout_limit_bytes=stdout_limit_bytes,
            )

        return_code = _poll_process(process)
        now = _monotonic()
        if return_code is not None:
            if stdout_eof:
                return _confirm_reaped(process)
            if stdout_deadline is None:
                stdout_deadline = now + _STDOUT_EOF_WAIT_SECONDS
            elif now >= stdout_deadline:
                raise ProcessInfrastructureError("stdout_read") from None
        elif now >= execution_deadline:
            raise ProcessTimeoutError() from None

        active_deadline = stdout_deadline or execution_deadline
        _sleep(min(_POLL_INTERVAL_SECONDS, max(0.0, active_deadline - now)))


def _read_available_stdout(
    stdout_pipe: IO[bytes],
    *,
    output: bytearray,
    stdout_limit_bytes: int,
) -> bool:
    read_size = min(
        _READ_CHUNK_BYTES,
        stdout_limit_bytes + 1 - len(output),
    )
    try:
        chunk = _read_stdout_chunk(stdout_pipe, read_size)
    except BlockingIOError:
        return False
    except OSError:
        raise ProcessInfrastructureError("stdout_read") from None
    if chunk is None:
        return False
    if not chunk:
        return True
    output.extend(chunk)
    if len(output) > stdout_limit_bytes:
        raise ProcessOutputLimitError() from None
    return False


def _read_stdout_chunk(stdout_pipe: IO[bytes], read_size: int) -> bytes | None:
    return stdout_pipe.read(read_size)


def _poll_process(process: subprocess.Popen[bytes]) -> int | None:
    try:
        return process.poll()
    except OSError:
        raise ProcessInfrastructureError("wait") from None


def _confirm_reaped(process: subprocess.Popen[bytes]) -> int:
    try:
        return process.wait(timeout=0)
    except (OSError, subprocess.TimeoutExpired):
        raise ProcessInfrastructureError("wait") from None


def _stop_after_capture_failure(
    process: subprocess.Popen[bytes],
    error: ProcessInfrastructureError | ProcessTimeoutError | ProcessOutputLimitError,
) -> ProcessInfrastructureError | ProcessTimeoutError | ProcessOutputLimitError:
    try:
        _terminate_and_reap(process)
    except ProcessInfrastructureError as termination_error:
        return termination_error
    return error


def _wait_for_execution(
    process: subprocess.Popen[bytes],
    *,
    timeout_seconds: float,
) -> int:
    try:
        return process.wait(timeout=timeout_seconds)
    except subprocess.TimeoutExpired:
        _terminate_and_reap(process)
        raise ProcessTimeoutError() from None
    except OSError:
        _terminate_and_reap(process)
        raise ProcessInfrastructureError("wait") from None


def _terminate_and_reap(process: subprocess.Popen[bytes]) -> None:
    barrier = _ProcessTerminationBarrier(process)
    if barrier.try_confirm_safe():
        return
    raise ProcessInfrastructureError(
        "termination",
        _cleanup_safety_barrier=barrier,
    ) from None
