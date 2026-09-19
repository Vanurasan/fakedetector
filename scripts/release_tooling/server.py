"""Owned server startup, private configuration, shutdown and reaping."""

from __future__ import annotations

import os
import signal
import socket
import subprocess
import sys
import threading
import time
from collections import deque
from pathlib import Path
from typing import Any

import yaml

from . import common, transport

_SERVER_TAIL_LINES = 200


class _ServerProcess:
    def __init__(self, process: subprocess.Popen[str], port: int) -> None:
        self.process = process
        self.port = port
        self.stdout_lines: deque[str] = deque(maxlen=_SERVER_TAIL_LINES)
        self.stderr_lines: deque[str] = deque(maxlen=_SERVER_TAIL_LINES)
        assert process.stdout is not None
        assert process.stderr is not None
        self._threads = (
            threading.Thread(
                target=self._drain,
                args=(process.stdout, self.stdout_lines),
                daemon=True,
            ),
            threading.Thread(
                target=self._drain,
                args=(process.stderr, self.stderr_lines),
                daemon=True,
            ),
        )

    def start_readers(self) -> None:
        for thread in self._threads:
            thread.start()

    @staticmethod
    def _drain(stream: Any, destination: deque[str]) -> None:
        try:
            for line in stream:
                destination.append(line.rstrip())
        finally:
            stream.close()

    def join_readers(self) -> None:
        for thread in self._threads:
            if thread.ident is not None:
                thread.join(timeout=2.0)

    def output_tail(self, secret_values: tuple[str, ...]) -> str:
        lines = [*(f"stdout: {line}" for line in self.stdout_lines)]
        lines.extend(f"stderr: {line}" for line in self.stderr_lines)
        return common._redact("\n".join(lines[-_SERVER_TAIL_LINES:]), secret_values)


def _validate_graceful_exit_code(
    *,
    returncode: int | None,
    signal_method: str,
    platform_name: str,
) -> None:
    if platform_name == "win32" and signal_method == "CTRL_BREAK_EVENT":
        accepted_codes = {3}
    elif platform_name != "win32" and signal_method == "SIGINT":
        accepted_codes = {0}
    else:
        raise common.ReleaseVerificationError(
            "shutdown",
            f"Unsupported graceful shutdown method {signal_method!r} "
            f"for platform {platform_name!r}.",
            process_returncode=returncode,
        )
    if returncode not in accepted_codes:
        raise common.ReleaseVerificationError(
            "shutdown",
            f"Unexpected graceful shutdown return code {returncode!r} "
            f"for {signal_method} on {platform_name}.",
            process_returncode=returncode,
        )


def _reserve_loopback_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


def _profile_b_ids(raw: dict[str, Any]) -> dict[str, list[str]]:
    return {
        media: list(raw["analyzers"][media]["enabled"]) for media in ("image", "audio", "video")
    }


def _prepare_work_config(
    *,
    extraction: Path,
    work: Path,
    port: int,
    secret_values: tuple[str, ...],
) -> tuple[Path, dict[str, Any]]:
    raw = yaml.safe_load((extraction / "config.example.yaml").read_text(encoding="utf-8"))
    expected_profile = {
        "image": ["image_metadata_consistency", "image_copy_move_correspondence"],
        "audio": ["audio_pcm_quality"],
        "video": ["video_sampled_frame_quality"],
    }
    if _profile_b_ids(raw) != expected_profile:
        raise common.ReleaseVerificationError(
            "work_config", "Release-kit config is not canonical Profile B."
        )
    raw["server"]["host"] = "127.0.0.1"
    raw["server"]["port"] = port
    raw["temporary_storage"]["root_path"] = str((work / "runtime" / "temp").resolve())
    raw["result"]["directory"] = str((work / "runtime" / "results").resolve())
    raw["logging"]["jsonl_path"] = str((work / "runtime" / "logs" / "application.jsonl").resolve())
    raw["limits"]["max_parallel_tasks"] = {"image": 1, "audio": 1, "video": 1}
    raw["limits"]["processing_timeout_seconds"] = 120
    raw["analyzers"]["defaults"]["timeout_seconds"] = 60
    rendered = yaml.safe_dump(raw, allow_unicode=True, sort_keys=False)
    if any(secret_value and secret_value in rendered for secret_value in secret_values):
        raise common.ReleaseVerificationError(
            "work_config", "A generated secret entered the work config."
        )
    config_path = work / "config.yaml"
    config_path.write_text(rendered, encoding="utf-8")
    return config_path, raw


def _rewrite_config_port(config_path: Path, raw: dict[str, Any], port: int) -> None:
    raw["server"]["port"] = port
    config_path.write_text(
        yaml.safe_dump(raw, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )


def _spawn_server(
    *,
    cli: Path,
    config_path: Path,
    work: Path,
    env: dict[str, str],
    port: int,
) -> _ServerProcess:
    creationflags = subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
    try:
        process = subprocess.Popen(
            [str(cli), "--config", str(config_path)],
            cwd=work,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
            creationflags=creationflags,
            start_new_session=os.name != "nt",
        )
    except OSError:
        raise common.ReleaseVerificationError(
            "startup", "Installed CLI process could not be started."
        ) from None
    # Own the raw child until wrapper construction and reader startup both succeed.
    server: _ServerProcess | None = None
    try:
        server = _ServerProcess(process, port)
        server.start_readers()
    except BaseException:
        try:
            _stop_process(process)
        finally:
            if server is not None:
                server.join_readers()
            for stream in (process.stdout, process.stderr):
                if stream is not None:
                    stream.close()
        raise
    return server


def _wait_for_health(
    server: _ServerProcess,
    *,
    secret_values: tuple[str, ...],
) -> dict[str, Any]:
    deadline = time.monotonic() + common._PHASE_TIMEOUTS["startup"]
    url = f"http://127.0.0.1:{server.port}/health"
    last_transport_error: str | None = None
    while time.monotonic() < deadline:
        returncode = server.process.poll()
        if returncode is not None:
            server.join_readers()
            raise common.ReleaseVerificationError(
                "startup",
                "Installed CLI exited before health readiness.",
                process_returncode=returncode,
                server_output_tail=server.output_tail(secret_values),
            )
        try:
            status, _headers, body = transport._http_exchange("GET", url, timeout=0.5)
        except OSError as error:
            last_transport_error = type(error).__name__
            time.sleep(0.05)
            continue
        if status != 200 or transport._json_object(body, phase="health") != {"status": "ok"}:
            raise common.ReleaseVerificationError(
                "health", "Health endpoint returned an invalid response."
            )
        if server.process.poll() is not None:
            raise common.ReleaseVerificationError(
                "health", "Installed CLI exited during health readiness."
            )
        return {"status": "passed", "http_status": 200, "payload": {"status": "ok"}}
    raise common.ReleaseVerificationError(
        "startup",
        f"Health readiness exceeded deadline; last transport error={last_transport_error}.",
        process_returncode=server.process.poll(),
        server_output_tail=server.output_tail(secret_values),
    )


def _is_bind_failure(output: str) -> bool:
    normalized = output.casefold()
    return any(
        marker in normalized
        for marker in (
            "address already in use",
            "only one usage of each socket address",
            "winerror 10048",
            "errno 10048",
            "eaddrinuse",
        )
    )


def _stop_process(process: subprocess.Popen[str]) -> None:
    if process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=5.0)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5.0)


def _emergency_stop(server: _ServerProcess) -> None:
    _stop_process(server.process)
    server.join_readers()


def _start_server_with_bind_retry(
    *,
    cli: Path,
    config_path: Path,
    config_raw: dict[str, Any],
    work: Path,
    env: dict[str, str],
    secret_values: tuple[str, ...],
    attempts: int = 3,
) -> tuple[_ServerProcess, dict[str, Any]]:
    for attempt in range(1, attempts + 1):
        port = _reserve_loopback_port()
        _rewrite_config_port(config_path, config_raw, port)
        server = _spawn_server(
            cli=cli,
            config_path=config_path,
            work=work,
            env=env,
            port=port,
        )
        try:
            health = _wait_for_health(server, secret_values=secret_values)
        except common.ReleaseVerificationError as error:
            tail = server.output_tail(secret_values)
            returncode = server.process.poll()
            if returncode is not None:
                server.join_readers()
            else:
                _emergency_stop(server)
            if attempt < attempts and returncode is not None and _is_bind_failure(tail):
                continue
            if error.server_output_tail is None:
                error.server_output_tail = tail
            raise
        except BaseException:
            _emergency_stop(server)
            raise
        return server, {
            "status": "passed",
            "attempts": attempt,
            "dynamic_loopback_port": port,
            "health": health,
        }
    raise common.ReleaseVerificationError("startup", "Bounded bind retry was exhausted.")


def _start_server_same_config(
    *,
    cli: Path,
    config_path: Path,
    work: Path,
    env: dict[str, str],
    port: int,
    secret_values: tuple[str, ...],
) -> tuple[_ServerProcess, dict[str, Any]]:
    server = _spawn_server(
        cli=cli,
        config_path=config_path,
        work=work,
        env=env,
        port=port,
    )
    try:
        health = _wait_for_health(server, secret_values=secret_values)
    except BaseException:
        _emergency_stop(server)
        raise
    return server, {
        "status": "passed",
        "attempts": 1,
        "loopback_port": port,
        "health": health,
    }


def _listener_closed(port: int, *, timeout: float = 5.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.25):
                time.sleep(0.05)
        except OSError:
            return True
    return False


def _graceful_shutdown(
    server: _ServerProcess,
    *,
    secret_values: tuple[str, ...],
) -> dict[str, Any]:
    process = server.process
    if process.poll() is not None:
        server.join_readers()
        raise common.ReleaseVerificationError(
            "shutdown",
            "Server exited before graceful shutdown was initiated.",
            process_returncode=process.returncode,
            server_output_tail=server.output_tail(secret_values),
        )
    try:
        if os.name == "nt":
            os.kill(process.pid, signal.CTRL_BREAK_EVENT)
            signal_method = "CTRL_BREAK_EVENT"
        else:
            process.send_signal(signal.SIGINT)
            signal_method = "SIGINT"
        process.wait(timeout=common._PHASE_TIMEOUTS["shutdown"])
    except (OSError, subprocess.TimeoutExpired):
        _emergency_stop(server)
        raise common.ReleaseVerificationError(
            "shutdown",
            "Graceful shutdown did not complete before the deadline.",
            process_returncode=process.poll(),
            server_output_tail=server.output_tail(secret_values),
        ) from None
    server.join_readers()
    output = server.output_tail(secret_values)
    normalized = output.casefold()
    marker_evidence = {
        "shutdown_started": "shutting down" in normalized,
        "lifespan_shutdown_completed": "application shutdown complete" in normalized,
        "server_finished": "finished server process" in normalized,
    }
    listener_closed = _listener_closed(server.port)
    if not all(marker_evidence.values()) or not listener_closed or process.poll() is None:
        raise common.ReleaseVerificationError(
            "shutdown",
            "Signal-aware graceful shutdown evidence is incomplete.",
            process_returncode=process.poll(),
            server_output_tail=output,
        )
    _validate_graceful_exit_code(
        returncode=process.returncode,
        signal_method=signal_method,
        platform_name=sys.platform,
    )
    return {
        "status": "passed",
        "signal": signal_method,
        "returncode": process.returncode,
        "markers": marker_evidence,
        "listener_closed": listener_closed,
        "process_reaped": True,
    }
