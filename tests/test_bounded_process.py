"""Tests for the private bounded subprocess safety primitive."""

from __future__ import annotations

import subprocess
import sys
import threading
from io import BytesIO
from pathlib import Path

import pytest

import fakedetector.core._bounded_process as bounded_process_module
from fakedetector.core._bounded_process import (
    ProcessInfrastructureError,
    ProcessOutputLimitError,
    ProcessTimeoutError,
    run_bounded_process,
)
from fakedetector.core._cleanup_safety import _CleanupSafetyInterruption


def python_child(source: str, *arguments: str) -> list[str]:
    return [sys.executable, "-c", source, *arguments]


def test_successful_process_discards_stdout(tmp_path: Path) -> None:
    result = run_bounded_process(
        python_child("import sys; sys.stdout.buffer.write(b'x' * 262144)"),
        cwd=tmp_path,
        timeout_seconds=2.0,
    )

    assert result.return_code == 0
    assert result.stdout is None


def test_successful_process_captures_bounded_stdout(tmp_path: Path) -> None:
    result = run_bounded_process(
        python_child("import sys; sys.stdout.buffer.write(b'captured')"),
        cwd=tmp_path,
        timeout_seconds=2.0,
        stdout_limit_bytes=16,
    )

    assert result.return_code == 0
    assert result.stdout == b"captured"


def test_successful_process_streams_to_sink_without_retaining_stdout(
    tmp_path: Path,
) -> None:
    sink = BytesIO()

    result = run_bounded_process(
        python_child("import sys; sys.stdout.buffer.write(b'x' * 4096)"),
        cwd=tmp_path,
        timeout_seconds=2.0,
        stdout_limit_bytes=4096,
        stdout_sink=sink,
    )

    assert result.return_code == 0
    assert result.stdout is None
    assert sink.getvalue() == b"x" * 4096


def test_stdout_sink_requires_an_explicit_limit(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="explicit byte limit"):
        run_bounded_process(
            python_child("pass"),
            cwd=tmp_path,
            timeout_seconds=2.0,
            stdout_sink=BytesIO(),
        )


def test_stdout_sink_limit_plus_one_stops_without_exceeding_bound(
    tmp_path: Path,
) -> None:
    sink = BytesIO()

    with pytest.raises(ProcessOutputLimitError):
        run_bounded_process(
            python_child("import sys; sys.stdout.buffer.write(b'x' * 4097)"),
            cwd=tmp_path,
            timeout_seconds=2.0,
            stdout_limit_bytes=4096,
            stdout_sink=sink,
        )

    assert len(sink.getvalue()) <= 4096


@pytest.mark.parametrize(
    ("size", "exceeds"),
    [(4096, False), (4097, True)],
    ids=["exact-limit", "limit-plus-one"],
)
def test_stdout_hard_limit(tmp_path: Path, size: int, exceeds: bool) -> None:
    def operation():
        return run_bounded_process(
            python_child(f"import sys; sys.stdout.buffer.write(b'x' * {size})"),
            cwd=tmp_path,
            timeout_seconds=2.0,
            stdout_limit_bytes=4096,
        )

    if exceeds:
        with pytest.raises(ProcessOutputLimitError):
            operation()
    else:
        assert operation().stdout == b"x" * size


def test_nonzero_exit_is_normal_factual_completion(tmp_path: Path) -> None:
    result = run_bounded_process(
        python_child("raise SystemExit(7)"),
        cwd=tmp_path,
        timeout_seconds=2.0,
    )

    assert result.return_code == 7
    assert result.stdout is None


def test_process_start_failure_is_safe_and_separate(tmp_path: Path) -> None:
    sentinel = "PRIVATE missing executable"

    with pytest.raises(ProcessInfrastructureError) as error_info:
        run_bounded_process(
            [str(tmp_path / sentinel)],
            cwd=tmp_path,
            timeout_seconds=1.0,
        )

    assert error_info.value.phase == "start"
    assert sentinel not in str(error_info.value)
    assert error_info.value.__cause__ is None


@pytest.mark.parametrize("stdout_limit_bytes", [None, 1024], ids=["discard", "capture"])
def test_timeout_stops_and_reaps_process_before_return(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    stdout_limit_bytes: int | None,
) -> None:
    real_popen = subprocess.Popen
    children: list[subprocess.Popen[bytes]] = []

    def tracking_popen(*args: object, **kwargs: object) -> subprocess.Popen[bytes]:
        child = real_popen(*args, **kwargs)
        children.append(child)
        return child

    monkeypatch.setattr(bounded_process_module.subprocess, "Popen", tracking_popen)

    with pytest.raises(ProcessTimeoutError):
        run_bounded_process(
            python_child("import time; time.sleep(10)"),
            cwd=tmp_path,
            timeout_seconds=0.05,
            stdout_limit_bytes=stdout_limit_bytes,
        )

    assert len(children) == 1
    assert children[0].poll() is not None
    assert children[0].wait(timeout=0.1) == children[0].returncode
    assert not any(thread.name == "bounded-process-stdout" for thread in threading.enumerate())


def test_output_producer_does_not_deadlock(tmp_path: Path) -> None:
    size = 512 * 1024

    result = run_bounded_process(
        python_child(f"import sys; sys.stdout.buffer.write(b'x' * {size})"),
        cwd=tmp_path,
        timeout_seconds=2.0,
        stdout_limit_bytes=size,
    )

    assert result.return_code == 0
    assert result.stdout is not None
    assert len(result.stdout) == size


def test_output_limit_stops_and_reaps_process(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    real_popen = subprocess.Popen
    children: list[subprocess.Popen[bytes]] = []

    def tracking_popen(*args: object, **kwargs: object) -> subprocess.Popen[bytes]:
        child = real_popen(*args, **kwargs)
        children.append(child)
        return child

    monkeypatch.setattr(bounded_process_module.subprocess, "Popen", tracking_popen)

    with pytest.raises(ProcessOutputLimitError):
        run_bounded_process(
            python_child(
                "import sys, time; "
                "sys.stdout.buffer.write(b'x' * 65536); sys.stdout.buffer.flush(); "
                "time.sleep(10)"
            ),
            cwd=tmp_path,
            timeout_seconds=2.0,
            stdout_limit_bytes=1024,
        )

    assert len(children) == 1
    assert children[0].poll() is not None
    assert children[0].wait(timeout=0.1) == children[0].returncode


def test_shell_metacharacters_remain_one_literal_argv_value(tmp_path: Path) -> None:
    literal = "spaces & semicolon; pipe| dollar$(ignored) \"double\" 'single'"

    result = run_bounded_process(
        python_child(
            "import sys; sys.stdout.buffer.write(sys.argv[1].encode('utf-8'))",
            literal,
        ),
        cwd=tmp_path,
        timeout_seconds=2.0,
        stdout_limit_bytes=1024,
    )

    assert result.stdout == literal.encode()


def test_explicit_trusted_cwd_is_applied(tmp_path: Path) -> None:
    working_directory = tmp_path / "trusted working directory"
    working_directory.mkdir()

    result = run_bounded_process(
        python_child("import os, sys; sys.stdout.buffer.write(os.getcwd().encode())"),
        cwd=working_directory,
        timeout_seconds=2.0,
        stdout_limit_bytes=1024,
    )

    assert result.stdout is not None
    assert Path(result.stdout.decode()).samefile(working_directory)


@pytest.mark.parametrize(
    ("stdout_limit_bytes", "expected_stdout"),
    [(None, subprocess.DEVNULL), (0, subprocess.PIPE)],
    ids=["discard", "capture"],
)
def test_process_start_uses_safe_fixed_boundary(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    stdout_limit_bytes: int | None,
    expected_stdout: int,
) -> None:
    real_popen = subprocess.Popen
    observed: dict[str, object] = {}

    def tracking_popen(*args: object, **kwargs: object) -> subprocess.Popen[bytes]:
        observed.update(kwargs)
        return real_popen(*args, **kwargs)

    monkeypatch.setattr(bounded_process_module.subprocess, "Popen", tracking_popen)

    run_bounded_process(
        python_child("pass"),
        cwd=tmp_path,
        timeout_seconds=2.0,
        stdout_limit_bytes=stdout_limit_bytes,
    )

    assert observed == {
        "shell": False,
        "stdin": subprocess.DEVNULL,
        "stdout": expected_stdout,
        "stderr": subprocess.DEVNULL,
        "cwd": tmp_path,
    }


class _FailingStdout:
    def __init__(self, *, fail_close: bool = False) -> None:
        self._fail_close = fail_close

    def read(self, _size: int) -> bytes:
        if self._fail_close:
            return b""
        raise OSError("PRIVATE stdout detail")

    def close(self) -> None:
        if self._fail_close:
            raise OSError("PRIVATE close detail")


class _RetainedStdout:
    def __init__(self) -> None:
        self.closed = False

    def read(self, _size: int) -> None:
        return None

    def close(self) -> None:
        self.closed = True


class _OversizedStdout:
    def read(self, _size: int) -> bytes:
        return b"xx"

    def close(self) -> None:
        pass


class _FailingSink:
    def write(self, _data: bytes) -> int:
        raise RuntimeError("PRIVATE sink detail")


class _FakeProcess:
    def __init__(self, *, stdout: object | None = None) -> None:
        self.stdout = stdout
        self.killed = False
        self.terminated = False
        self.wait_calls = 0

    def wait(self, timeout: float | None = None) -> int:
        self.wait_calls += 1
        return 0

    def kill(self) -> None:
        self.killed = True

    def terminate(self) -> None:
        self.terminated = True

    def poll(self) -> int | None:
        return 0


class _WaitFailureProcess(_FakeProcess):
    def wait(self, timeout: float | None = None) -> int:
        self.wait_calls += 1
        if self.wait_calls == 1:
            raise OSError("PRIVATE wait detail")
        return 0


class _NeverReapedProcess(_FakeProcess):
    def __init__(self, *, stdout: object | None = None) -> None:
        super().__init__(stdout=stdout)
        self.reaped = False

    def wait(self, timeout: float | None = None) -> int:
        self.wait_calls += 1
        if self.reaped:
            return 0
        raise subprocess.TimeoutExpired("PRIVATE command", timeout)

    def poll(self) -> int | None:
        return 0 if self.reaped else None


@pytest.mark.parametrize(
    ("stdout", "phase"),
    [
        (_FailingStdout(), "stdout_read"),
        (_FailingStdout(fail_close=True), "stdout_close"),
    ],
)
def test_stdout_infrastructure_failure_is_safe(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    stdout: _FailingStdout,
    phase: str,
) -> None:
    process = _FakeProcess(stdout=stdout)
    monkeypatch.setattr(
        bounded_process_module.subprocess,
        "Popen",
        lambda *args, **kwargs: process,
    )
    monkeypatch.setattr(
        bounded_process_module,
        "_make_stdout_nonblocking",
        lambda _stdout: None,
    )

    with pytest.raises(ProcessInfrastructureError) as error_info:
        run_bounded_process(
            python_child("pass"),
            cwd=tmp_path,
            timeout_seconds=1.0,
            stdout_limit_bytes=1,
        )

    assert error_info.value.phase == phase
    assert "PRIVATE" not in str(error_info.value)
    if phase == "stdout_read":
        assert process.terminated
    assert process.wait_calls == 1


def test_retained_stdout_writer_returns_bounded_without_live_reader(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stdout = _RetainedStdout()
    process = _FakeProcess(stdout=stdout)
    monotonic_value = 0.0

    def advancing_monotonic() -> float:
        nonlocal monotonic_value
        monotonic_value += 0.1
        return monotonic_value

    monkeypatch.setattr(
        bounded_process_module.subprocess,
        "Popen",
        lambda *args, **kwargs: process,
    )
    monkeypatch.setattr(
        bounded_process_module,
        "_make_stdout_nonblocking",
        lambda _stdout: None,
    )
    monkeypatch.setattr(bounded_process_module, "_monotonic", advancing_monotonic)
    monkeypatch.setattr(bounded_process_module, "_sleep", lambda _seconds: None)

    with pytest.raises(ProcessInfrastructureError) as error_info:
        run_bounded_process(
            python_child("pass"),
            cwd=tmp_path,
            timeout_seconds=1.0,
            stdout_limit_bytes=1,
        )

    assert error_info.value.phase == "stdout_read"
    assert process.terminated
    assert process.wait_calls == 1
    assert stdout.closed
    assert not any(thread.name == "bounded-process-stdout" for thread in threading.enumerate())


@pytest.mark.parametrize(
    "stdout",
    [
        _FailingStdout(),
        _FailingStdout(fail_close=True),
        _OversizedStdout(),
    ],
    ids=["stdout-read", "stdout-close", "output-limit"],
)
def test_unreapable_capture_process_has_termination_precedence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    stdout: object,
) -> None:
    process = _NeverReapedProcess(stdout=stdout)
    monkeypatch.setattr(
        bounded_process_module.subprocess,
        "Popen",
        lambda *args, **kwargs: process,
    )
    monkeypatch.setattr(
        bounded_process_module,
        "_make_stdout_nonblocking",
        lambda _stdout: None,
    )

    with pytest.raises(ProcessInfrastructureError) as error_info:
        run_bounded_process(
            python_child("pass"),
            cwd=tmp_path,
            timeout_seconds=0.01,
            stdout_limit_bytes=1,
        )

    assert error_info.value.phase == "termination"
    assert error_info.value._cleanup_safety_barrier is not None
    assert process.terminated
    assert process.killed
    assert process.wait_calls == 2


def test_sink_write_failure_stops_and_reaps_before_safe_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    process = _FakeProcess(stdout=_OversizedStdout())
    monkeypatch.setattr(
        bounded_process_module.subprocess,
        "Popen",
        lambda *args, **kwargs: process,
    )
    monkeypatch.setattr(
        bounded_process_module,
        "_make_stdout_nonblocking",
        lambda _stdout: None,
    )

    with pytest.raises(ProcessInfrastructureError) as error_info:
        run_bounded_process(
            python_child("pass"),
            cwd=tmp_path,
            timeout_seconds=1.0,
            stdout_limit_bytes=2,
            stdout_sink=_FailingSink(),
        )

    assert error_info.value.phase == "stdout_write"
    assert "PRIVATE" not in str(error_info.value)
    assert process.terminated
    assert process.wait_calls == 1


def test_unreapable_sink_output_limit_has_termination_precedence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    process = _NeverReapedProcess(stdout=_OversizedStdout())
    monkeypatch.setattr(
        bounded_process_module.subprocess,
        "Popen",
        lambda *args, **kwargs: process,
    )
    monkeypatch.setattr(
        bounded_process_module,
        "_make_stdout_nonblocking",
        lambda _stdout: None,
    )

    with pytest.raises(ProcessInfrastructureError) as error_info:
        run_bounded_process(
            python_child("pass"),
            cwd=tmp_path,
            timeout_seconds=1.0,
            stdout_limit_bytes=1,
            stdout_sink=BytesIO(),
        )

    assert error_info.value.phase == "termination"
    assert error_info.value._cleanup_safety_barrier is not None
    assert process.terminated
    assert process.killed
    assert process.wait_calls == 2


def test_wait_failure_stops_and_reaps_before_safe_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    process = _WaitFailureProcess()
    monkeypatch.setattr(
        bounded_process_module.subprocess,
        "Popen",
        lambda *args, **kwargs: process,
    )

    with pytest.raises(ProcessInfrastructureError) as error_info:
        run_bounded_process(
            python_child("pass"),
            cwd=tmp_path,
            timeout_seconds=1.0,
        )

    assert error_info.value.phase == "wait"
    assert "PRIVATE" not in str(error_info.value)
    assert process.terminated
    assert process.wait_calls == 2


def test_unconfirmed_termination_is_infrastructure_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    process = _NeverReapedProcess()
    monkeypatch.setattr(
        bounded_process_module.subprocess,
        "Popen",
        lambda *args, **kwargs: process,
    )

    with pytest.raises(ProcessInfrastructureError) as error_info:
        run_bounded_process(
            python_child("pass"),
            cwd=tmp_path,
            timeout_seconds=0.01,
        )

    assert error_info.value.phase == "termination"
    barrier = error_info.value._cleanup_safety_barrier
    assert barrier is not None
    assert process.terminated
    assert process.killed
    assert process.wait_calls == 3
    assert barrier.try_confirm_safe() is False
    assert process.wait_calls == 5
    process.reaped = True
    assert barrier.try_confirm_safe() is True
    assert barrier.try_confirm_safe() is True
    assert process.wait_calls == 6


@pytest.mark.parametrize("phase", ["wait", "poll", "read", "sink", "deadline", "result"])
def test_real_process_interruption_reaps_and_closes_stdout_before_propagation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    real_subprocesses,
    process_interruption: BaseException,
    phase: str,
) -> None:
    injected = False

    def interrupt(*_args, **_kwargs):
        nonlocal injected
        assert len(real_subprocesses) == 1
        child = real_subprocesses[0]
        assert (child.poll() is not None) == (phase == "result")
        injected = True
        raise process_interruption

    if phase == "wait":
        wait_without_capture = bounded_process_module._wait_without_capture

        def interrupt_wait(process, **kwargs):
            wait = process.wait

            def wait_once(*args, **options):
                monkeypatch.setattr(process, "wait", wait)
                interrupt(*args, **options)

            monkeypatch.setattr(process, "wait", wait_once)
            return wait_without_capture(process, **kwargs)

        monkeypatch.setattr(bounded_process_module, "_wait_without_capture", interrupt_wait)
    elif phase == "poll":
        monkeypatch.setattr(bounded_process_module, "_poll_process", interrupt)
    elif phase == "read":
        monkeypatch.setattr(bounded_process_module, "_read_stdout_chunk", interrupt)
    elif phase == "deadline":
        monkeypatch.setattr(bounded_process_module, "_monotonic", interrupt)
    elif phase == "result":
        monkeypatch.setattr(bounded_process_module._BoundedStdoutTarget, "result", interrupt)

    sink = BytesIO()
    if phase == "sink":
        monkeypatch.setattr(sink, "write", interrupt)
    source = "import sys, time; sys.stdout.buffer.write(b'x'); sys.stdout.buffer.flush()"
    if phase != "result":
        source += "; time.sleep(30)"

    with pytest.raises(type(process_interruption)) as raised:
        run_bounded_process(
            python_child(source),
            cwd=tmp_path,
            timeout_seconds=5.0,
            stdout_limit_bytes=None if phase == "wait" else 1024,
            stdout_sink=sink if phase == "sink" else None,
        )

    assert raised.value is process_interruption
    assert injected
    child = real_subprocesses[0]
    assert child.returncode is not None
    assert child.wait(timeout=0.0) == child.returncode
    assert child.stdout is None or child.stdout.closed
    assert not sink.closed


@pytest.mark.parametrize("stdout_limit_bytes", [None, 1024], ids=["discard", "capture"])
def test_real_process_interrupted_escalation_retains_recoverable_barrier(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    real_subprocesses,
    process_interruption: BaseException,
    stdout_limit_bytes: int | None,
) -> None:
    terminate = bounded_process_module._ProcessTerminationBarrier.try_confirm_safe
    injected = False

    def interrupted_termination(barrier):
        nonlocal injected
        process = real_subprocesses[0]
        if not injected:
            injected = True
            real_terminate = process.terminate

            def terminate_once():
                monkeypatch.setattr(process, "terminate", real_terminate)
                assert process.poll() is None
                raise process_interruption

            monkeypatch.setattr(process, "terminate", terminate_once)
        return terminate(barrier)

    monkeypatch.setattr(
        bounded_process_module._ProcessTerminationBarrier,
        "try_confirm_safe",
        interrupted_termination,
    )

    with pytest.raises(_CleanupSafetyInterruption) as raised:
        run_bounded_process(
            python_child("import time; time.sleep(30)"),
            cwd=tmp_path,
            timeout_seconds=0.05,
            stdout_limit_bytes=stdout_limit_bytes,
        )

    assert raised.value.interruption is process_interruption
    barrier = raised.value._cleanup_safety_barrier
    child = real_subprocesses[0]
    assert child.poll() is None
    assert child.stdout is None or child.stdout.closed
    assert barrier.try_confirm_safe() is True
    assert barrier.try_confirm_safe() is True
    assert child.wait(timeout=0.0) == child.returncode


@pytest.mark.parametrize("failure", ["output_limit", "stdout_read", "termination"])
def test_stdout_close_interruption_preserves_pending_termination_safety(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    real_subprocesses,
    process_interruption: BaseException,
    failure: str,
) -> None:
    with pytest.MonkeyPatch.context() as stop_patch:

        def fail_read(stdout, _size):
            child = real_subprocesses[0]
            assert child.poll() is None
            close = stdout.close

            def interrupted_close():
                monkeypatch.setattr(stdout, "close", close)
                close()
                raise process_interruption

            monkeypatch.setattr(stdout, "close", interrupted_close)
            if failure == "termination":
                stop_patch.setattr(child, "terminate", lambda: None)
                stop_patch.setattr(child, "kill", lambda: None)

                def unconfirmed_wait(timeout):
                    raise subprocess.TimeoutExpired("probe", timeout)

                stop_patch.setattr(child, "wait", unconfirmed_wait)
            if failure == "stdout_read":
                raise ProcessInfrastructureError("stdout_read")
            raise ProcessOutputLimitError

        monkeypatch.setattr(bounded_process_module, "_read_stdout_chunk", fail_read)
        expected_error = (
            _CleanupSafetyInterruption if failure == "termination" else type(process_interruption)
        )
        with pytest.raises(expected_error) as raised:
            run_bounded_process(
                python_child("import time; time.sleep(30)"),
                cwd=tmp_path,
                timeout_seconds=5.0,
                stdout_limit_bytes=1,
            )
        child = real_subprocesses[0]
        assert child.stdout.closed
        if failure == "termination":
            assert raised.value.interruption is process_interruption
            assert child.poll() is None
            stop_patch.undo()
            assert raised.value._cleanup_safety_barrier.try_confirm_safe() is True
        else:
            assert raised.value is process_interruption
        assert child.returncode is not None
        assert child.wait(timeout=0.0) == child.returncode
