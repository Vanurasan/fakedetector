"""Regression protection for private release verification trust boundaries."""

from __future__ import annotations

import ast
import importlib
import json
import os
import subprocess
from io import StringIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, call

import pytest

_SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"


@pytest.fixture
def tools(monkeypatch: pytest.MonkeyPatch) -> SimpleNamespace:
    monkeypatch.syspath_prepend(str(_SCRIPTS))
    modules = {
        name: importlib.import_module(f"release_tooling.{name}")
        for name in ("common", "build", "kit", "environment", "server", "transport", "reporting")
    }
    return SimpleNamespace(**modules, verifier=importlib.import_module("verify_release"))


def test_private_module_dependencies_are_acyclic_and_do_not_import_orchestrator() -> None:
    package = _SCRIPTS / "release_tooling"
    graph: dict[str, set[str]] = {}
    for path in package.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        dependencies: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                assert all(alias.name != "verify_release" for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                assert node.module != "verify_release"
                if node.level == 1:
                    dependencies.update(alias.name for alias in node.names)
        graph[path.stem] = dependencies

    def visit(name: str, ancestors: frozenset[str]) -> None:
        assert name not in ancestors, f"Release tooling import cycle at {name}"
        for dependency in graph[name]:
            visit(dependency, ancestors | {name})

    for name in graph:
        visit(name, frozenset())


def test_subprocess_environment_removes_contamination(
    tools: SimpleNamespace,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for name in ("FAKEDETECTOR_SERVER__PORT", "PYTHONHOME", "PYTHONPATH", "VIRTUAL_ENV"):
        monkeypatch.setenv(name, "contaminated")
    monkeypatch.setenv("PIP_CONFIG_FILE", "unsafe.ini")
    environment = tools.common._sanitized_environment()
    assert not any(name.upper().startswith("FAKEDETECTOR_") for name in environment)
    assert not {"PYTHONHOME", "PYTHONPATH", "VIRTUAL_ENV"} & environment.keys()
    assert environment["PYTHONNOUSERSITE"] == "1"
    assert environment["PYTHONDONTWRITEBYTECODE"] == "1"
    assert environment["PIP_CONFIG_FILE"] == os.devnull


@pytest.mark.parametrize("status", [["?? untracked.txt"], [" M README.md"]])
def test_strict_dirty_source_writes_non_certifying_failure_report(
    tools: SimpleNamespace,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    status: list[str],
) -> None:
    monkeypatch.setattr(tools.verifier.shutil, "which", lambda name, **kwargs: name)
    monkeypatch.setattr(
        tools.common,
        "_run_command",
        lambda args, **kwargs: SimpleNamespace(
            stdout="\n".join(status) if "status" in args else "a" * 40
        ),
    )
    report = tools.verifier.run_release_gate(output_directory=tmp_path)
    assert report["overall_status"] == "failed"
    assert report["certified"] is False
    assert report["failure"]["phase"] == "source"
    assert report["source_status_at_start"] == status
    assert json.loads((tmp_path / "verification-report.json").read_text()) == report


def test_report_serialization_redacts_nested_failure_evidence(
    tools: SimpleNamespace,
    tmp_path: Path,
) -> None:
    _, basic, bearer, secrets = tools.common._auth_headers_and_redaction_values(
        api_token="test-api-secret",
        webui_username="test-user",
        webui_password="test-password",
    )
    report = tools.reporting._initial_report(output=tmp_path, development=True)
    report.update(overall_status="failed", failure={"message": bearer, "server_output_tail": basic})
    tools.reporting._write_report(report, output=tmp_path, secret_values=secrets)
    rendered = (tmp_path / "verification-report.json").read_text()
    assert all(secret not in rendered for secret in secrets)
    assert json.loads(rendered)["certified"] is False
    assert "<redacted>" in rendered


@pytest.mark.parametrize("failure", [RuntimeError, KeyboardInterrupt, SystemExit, BaseException])
@pytest.mark.parametrize("restart", [False, True])
def test_startup_failure_reaps_owned_process_before_handoff(
    tools: SimpleNamespace,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    failure: type[BaseException],
    restart: bool,
) -> None:
    owned = Mock()
    owned.process.poll.return_value = None
    monkeypatch.setattr(tools.server, "_spawn_server", lambda **kwargs: owned)
    monkeypatch.setattr(tools.server, "_reserve_loopback_port", lambda: 12345)
    monkeypatch.setattr(tools.server, "_rewrite_config_port", lambda *args: None)

    def interrupt(*args: object, **kwargs: object) -> None:
        raise failure("test interruption")

    monkeypatch.setattr(tools.server, "_wait_for_health", interrupt)
    arguments = {
        "cli": tmp_path / "cli",
        "config_path": tmp_path / "config.yaml",
        "work": tmp_path,
        "env": {},
        "secret_values": (),
    }
    if restart:
        start = tools.server._start_server_same_config
        arguments["port"] = 12345
    else:
        start = tools.server._start_server_with_bind_retry
        arguments["config_raw"] = {}
    with pytest.raises(failure):
        start(**arguments)
    owned.process.terminate.assert_called_once_with()
    owned.process.wait.assert_called_once_with(timeout=5.0)
    owned.join_readers.assert_called_once_with()


def test_emergency_stop_escalates_only_owned_process(tools: SimpleNamespace) -> None:
    owned = Mock()
    owned.process.poll.return_value = None
    owned.process.wait.side_effect = [subprocess.TimeoutExpired("owned", 5), 0]
    tools.server._emergency_stop(owned)
    owned.process.terminate.assert_called_once_with()
    owned.process.kill.assert_called_once_with()
    assert owned.process.wait.call_count == 2
    owned.join_readers.assert_called_once_with()


@pytest.mark.parametrize("failure", [RuntimeError, KeyboardInterrupt, SystemExit, BaseException])
@pytest.mark.parametrize("reader_number", [1, 2])
@pytest.mark.parametrize("escalate", [False, True])
def test_reader_start_failure_reaps_raw_process(
    tools: SimpleNamespace,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    failure: type[BaseException],
    reader_number: int,
    escalate: bool,
) -> None:
    process = Mock(stdout=StringIO("output\n"), stderr=StringIO("error\n"))
    process.poll.return_value = None
    if escalate:
        process.wait.side_effect = [subprocess.TimeoutExpired("owned", 5), 0]
    monkeypatch.setattr(tools.server.subprocess, "Popen", lambda *a, **kw: process)
    thread_type = tools.server.threading.Thread
    real_start, real_join = thread_type.start, thread_type.join
    attempted = []
    joined = []
    injected = failure("reader start failed")

    def start(thread):
        attempted.append(thread)
        if len(attempted) == reader_number:
            raise injected
        real_start(thread)

    def join(thread, *, timeout):
        assert timeout == 2.0
        assert process.wait.called
        joined.append(thread)
        real_join(thread, timeout=timeout)

    monkeypatch.setattr(thread_type, "start", start)
    monkeypatch.setattr(thread_type, "join", join)
    with pytest.raises(failure) as caught:
        tools.server._spawn_server(
            cli=tmp_path / "cli", config_path=tmp_path / "config.yaml",
            work=tmp_path, env={}, port=12345,
        )

    assert caught.value is injected
    process.terminate.assert_called_once_with()
    assert process.wait.call_args_list == [call(timeout=5.0)] * (2 if escalate else 1)
    assert process.kill.call_count == int(escalate)
    assert joined == attempted[:-1]
    assert all(thread.ident is not None and not thread.is_alive() for thread in joined)
    assert attempted[-1].ident is None
    assert process.stdout.closed and process.stderr.closed


@pytest.mark.parametrize("failure", [RuntimeError, KeyboardInterrupt, SystemExit, BaseException])
def test_reader_construction_failure_reaps_raw_process(
    tools: SimpleNamespace,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    failure: type[BaseException],
) -> None:
    process = Mock(stdout=StringIO(), stderr=StringIO())
    process.poll.return_value = None
    monkeypatch.setattr(tools.server.subprocess, "Popen", lambda *a, **kw: process)
    injected = failure("reader construction failed")
    monkeypatch.setattr(tools.server.threading, "Thread", Mock(side_effect=injected))
    with pytest.raises(failure) as caught:
        tools.server._spawn_server(
            cli=tmp_path / "cli", config_path=tmp_path / "config.yaml",
            work=tmp_path, env={}, port=12345,
        )
    assert caught.value is injected
    process.terminate.assert_called_once_with()
    process.wait.assert_called_once_with(timeout=5.0)
    process.kill.assert_not_called()
    assert process.stdout.closed and process.stderr.closed


def test_spawn_hands_off_without_premature_or_double_cleanup(
    tools: SimpleNamespace,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    process = Mock(stdout=StringIO("output\n"), stderr=StringIO("error\n"))
    process.poll.return_value = None
    monkeypatch.setattr(tools.server.subprocess, "Popen", lambda *a, **kw: process)
    server = tools.server._spawn_server(
        cli=tmp_path / "cli", config_path=tmp_path / "config.yaml",
        work=tmp_path, env={}, port=12345,
    )
    assert server.process is process
    assert server.port == 12345
    process.terminate.assert_not_called()
    process.wait.assert_not_called()
    process.kill.assert_not_called()
    server.join_readers()
    assert list(server.stdout_lines) == ["output"]
    assert list(server.stderr_lines) == ["error"]
    tools.server._emergency_stop(server)
    process.terminate.assert_called_once_with()
    process.wait.assert_called_once_with(timeout=5.0)


@pytest.mark.parametrize(
    "defect", [None, "origin", "sys_path", "wheel", "editable", "version", "resources", "user_site"]
)
def test_installed_provenance_uses_exact_extracted_wheel_and_external_environment(
    tools: SimpleNamespace,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    defect: str | None,
) -> None:
    repository = tmp_path / "checkout"
    repository.mkdir()
    (repository / "pyproject.toml").write_text("[dependency-groups]\ndev = []\n")
    output = tmp_path / "output"
    output.mkdir()
    extraction = output / "extraction"
    extraction.mkdir()
    (extraction / "runtime-constraints.txt").write_text("sample==1.2.3\n")
    wheel = extraction / "fakedetector-0.1.0-py3-none-any.whl"
    origin = output / "installed-venv" / "Lib" / "site-packages" / "fakedetector" / "__init__.py"
    probe = {
        "package_version": "0.1.0",
        "module_version": "0.1.0",
        "python_version": "3.12.10",
        "user_site_enabled": False,
        "resources": {"templates/result.html": True},
        "module_origin": str(origin),
        "sys_path": [str(origin.parent.parent)],
        "direct_url": {"url": wheel.as_uri()},
        "marker_environment": {},
        "installed": {"fakedetector": "0.1.0", "sample": "1.2.3"},
    }
    if defect == "origin":
        probe["module_origin"] = str(repository / "src" / "fakedetector" / "__init__.py")
    elif defect == "sys_path":
        probe["sys_path"] = [str(repository)]
    elif defect == "wheel":
        probe["direct_url"] = {"url": (output / wheel.name).as_uri()}
    elif defect == "editable":
        probe["direct_url"]["dir_info"] = {"editable": True}
    elif defect == "version":
        probe["package_version"] = "9.9.9"
    elif defect == "resources":
        probe["resources"] = {"templates/result.html": False}
    elif defect == "user_site":
        probe["user_site_enabled"] = True
    commands: list[list[str]] = []

    def run(args: list[str], **kwargs: object) -> SimpleNamespace:
        commands.append(args)
        assert kwargs["cwd"] == output
        return SimpleNamespace(stdout="usage: fakedetector")

    monkeypatch.setattr(tools.common, "_run_command", run)
    monkeypatch.setattr(tools.environment, "_installed_probe", lambda *args, **kwargs: probe)
    arguments = {
        "repository": repository,
        "output": output,
        "extraction": extraction,
        "wheel_filename": wheel.name,
        "uv": "uv",
        "env": {},
        "project_name": "fakedetector",
        "project_version": "0.1.0",
    }
    if defect is not None:
        with pytest.raises(tools.common.ReleaseVerificationError):
            tools.environment._create_and_verify_venv(**arguments)
    else:
        _, cli, evidence = tools.environment._create_and_verify_venv(**arguments)
        assert evidence["installed_from_zip_wheel"] is True
        assert evidence["source_checkout_on_sys_path"] is False
        assert commands[-1] == [str(cli), "--help"]
    assert commands[0][:5] == ["uv", "venv", "--python", "3.12", "--no-project"]
    assert commands[1][-3:] == [
        "--constraint",
        str(extraction / "runtime-constraints.txt"),
        str(wheel),
    ]


def test_zip_hash_mismatch_is_rejected_before_file_is_written(
    tools: SimpleNamespace,
    tmp_path: Path,
) -> None:
    import zipfile

    archive_path = tmp_path / "kit.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("wheel.whl", b"tampered")
    with pytest.raises(tools.common.ReleaseVerificationError, match="hash mismatch"):
        tools.kit._verify_zip(
            zip_path=archive_path,
            output=tmp_path,
            expected_names={"wheel.whl"},
            manifest={"covered_files": [{"path": "wheel.whl", "sha256": "0" * 64}]},
            manifest_sha256="0" * 64,
        )
    assert not (tmp_path / "verified-zip-extraction" / "wheel.whl").exists()
