"""Shared failures, commands, isolation, hashing and credential redaction."""

from __future__ import annotations

import base64
import hashlib
import os
import subprocess
import tempfile
from pathlib import Path

_TOOL_VERSION = "1.0.0"


_PHASE_TIMEOUTS = {
    "build": 300.0,
    "constraints": 120.0,
    "venv": 120.0,
    "install": 300.0,
    "probe": 60.0,
    "demo": 60.0,
    "startup": 30.0,
    "analysis": 120.0,
    "shutdown": 30.0,
}


class ReleaseVerificationError(RuntimeError):
    """Safe release-gate failure with a stable phase."""

    def __init__(
        self,
        phase: str,
        message: str,
        *,
        analysis_id: str | None = None,
        process_returncode: int | None = None,
        server_output_tail: str | None = None,
    ) -> None:
        super().__init__(message)
        self.phase = phase
        self.analysis_id = analysis_id
        self.process_returncode = process_returncode
        self.server_output_tail = server_output_tail


def _redact(value: str, secret_values: tuple[str, ...]) -> str:
    redacted = value
    for secret_value in sorted(secret_values, key=len, reverse=True):
        if secret_value:
            redacted = redacted.replace(secret_value, "<redacted>")
    return redacted


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _run_command(
    args: list[str],
    *,
    cwd: Path,
    env: dict[str, str],
    timeout: float,
    phase: str,
) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            args,
            cwd=cwd,
            env=env,
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        raise ReleaseVerificationError(
            phase, f"Command exceeded its {timeout:g}s deadline."
        ) from None
    except subprocess.CalledProcessError as error:
        output = "\n".join(part for part in (error.stdout, error.stderr) if part)
        safe_tail = output[-4000:]
        raise ReleaseVerificationError(
            phase,
            f"Command failed with return code {error.returncode}: {safe_tail}",
            process_returncode=error.returncode,
        ) from None
    except OSError:
        raise ReleaseVerificationError(phase, "Command could not be started.") from None


def _sanitized_environment() -> dict[str, str]:
    environment = {
        key: value
        for key, value in os.environ.items()
        if not key.upper().startswith("FAKEDETECTOR_")
    }
    for name in ("PYTHONHOME", "PYTHONPATH", "VIRTUAL_ENV"):
        environment.pop(name, None)
    environment["PYTHONNOUSERSITE"] = "1"
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    environment["PIP_CONFIG_FILE"] = os.devnull
    return environment


def _prepare_output_directory(requested: Path | None, repository: Path) -> Path:
    if requested is None:
        output = Path(tempfile.mkdtemp(prefix="fakedetector-release-")).resolve()
    else:
        output = requested.expanduser().resolve()
        output.mkdir(parents=True, exist_ok=True)
        if any(output.iterdir()):
            raise ReleaseVerificationError("output", "Requested output directory must be empty.")
    if output == repository or repository in output.parents:
        raise ReleaseVerificationError("output", "Release output must be outside the repository.")
    return output


def _basic_header(username: str, password: str) -> str:
    encoded = base64.b64encode(f"{username}:{password}".encode()).decode("ascii")
    return f"Basic {encoded}"


def _auth_headers_and_redaction_values(
    *,
    api_token: str,
    webui_username: str,
    webui_password: str,
) -> tuple[str, str, str, tuple[str, ...]]:
    basic_credentials = f"{webui_username}:{webui_password}"
    basic_header = _basic_header(webui_username, webui_password)
    basic_payload = basic_header.removeprefix("Basic ")
    bearer_header = f"Bearer {api_token}"
    secret_values = (
        api_token,
        webui_username,
        webui_password,
        basic_credentials,
        basic_payload,
        basic_header,
        bearer_header,
    )
    return basic_credentials, basic_header, bearer_header, secret_values
