"""Coordinate installed-artifact release verification."""

from __future__ import annotations

import argparse
import json
import platform
import secrets
import shutil
import sys
import tomllib
from pathlib import Path
from typing import Any

from release_tooling import (
    build,
    common,
    demo,
    environment,
    kit,
    probes,
    reporting,
    server,
    transport,
)


def _announce(phase: str) -> None:
    print(f"[release] {phase}", file=sys.stderr, flush=True)


def run_release_gate(
    *,
    output_directory: Path | None = None,
    development: bool = False,
) -> dict[str, Any]:
    """Run the complete installed-artifact release gate and return its report."""
    repository = Path(__file__).resolve().parents[1]
    output = common._prepare_output_directory(output_directory, repository)
    report = reporting._initial_report(output=output, development=development)
    secret_values: tuple[str, ...] = ()
    active_server: server._ServerProcess | None = None

    try:
        _announce("source preflight")
        env = common._sanitized_environment()
        git = shutil.which("git", path=env.get("PATH"))
        uv = shutil.which("uv", path=env.get("PATH"))
        if git is None or uv is None:
            raise common.ReleaseVerificationError("source", "git and uv are required.")
        source_sha = common._run_command(
            [git, "rev-parse", "HEAD"],
            cwd=repository,
            env=env,
            timeout=10.0,
            phase="source",
        ).stdout.strip()
        source_status = common._run_command(
            [git, "status", "--short", "--untracked-files=all"],
            cwd=repository,
            env=env,
            timeout=10.0,
            phase="source",
        ).stdout.splitlines()
        report["source_sha"] = source_sha
        report["source_status_at_start"] = source_status
        certification = build._certification_state(
            development=development,
            source_status=source_status,
        )
        report.update(certification)

        machine = platform.machine()
        windows_version = sys.getwindowsversion() if sys.platform == "win32" else None
        windows_major = windows_version.major if windows_version is not None else None
        windows_build = windows_version.build if windows_version is not None else None
        windows_product_type = windows_version.product_type if windows_version is not None else None
        build._validate_supported_host(
            platform_name=sys.platform,
            machine=machine,
            python_version=sys.version_info[:2],
            windows_major=windows_major,
            windows_build=windows_build,
            windows_product_type=windows_product_type,
        )
        report["host_platform"] = {
            "system": platform.system(),
            "release": platform.release(),
            "machine": machine,
            "windows_major": windows_major,
            "windows_build": windows_build,
            "windows_product_type": windows_product_type,
            "python_version": platform.python_version(),
        }

        pyproject = tomllib.loads((repository / "pyproject.toml").read_text(encoding="utf-8"))
        project_name, project_version = build._project_identity(pyproject)
        report["project_name"] = project_name
        report["package_version"] = project_version
        uv_version = common._run_command(
            [uv, "--version"],
            cwd=output,
            env=env,
            timeout=10.0,
            phase="prerequisites",
        ).stdout.strip()
        ffmpeg_version = build._probe_external_tool("ffmpeg", cwd=output, env=env)
        ffprobe_version = build._probe_external_tool("ffprobe", cwd=output, env=env)
        report["ffmpeg"] = {"version": ffmpeg_version, "external_prerequisite": True}
        report["ffprobe"] = {"version": ffprobe_version, "external_prerequisite": True}

        _announce("build sdist, wheel, and runtime constraints")
        build_inputs = build._build_release_inputs(
            repository=repository,
            output=output,
            project_name=project_name,
            uv=uv,
            env=env,
        )
        wheel = build_inputs["wheel"]
        constraints = build_inputs["constraints"]
        report["build"] = {
            "status": "passed",
            "method": "uv build --sdist, then uv build --wheel from the sdist",
            "sdist_filename": build_inputs["sdist"].name,
            "wheel_filename": wheel.name,
            "wheel_sha256": common._sha256_file(wheel),
            "constraints_generation_command": build_inputs["constraints_command"],
            "constraints_sha256": common._sha256_file(constraints),
            "uv_version": uv_version,
            "backend": pyproject["build-system"]["build-backend"],
            "backend_requirements": pyproject["build-system"]["requires"],
        }

        _announce("assemble release kit, manifest, and ZIP")
        verification_python_version = platform.python_version()
        kit_directory, manifest, manifest_sha256, file_hashes = kit._assemble_release_kit(
            repository=repository,
            output=output,
            project_name=project_name,
            wheel=wheel,
            constraints=constraints,
            manifest_arguments={
                "product_name": project_name,
                "package_version": project_version,
                "source_head_sha": source_sha,
                "source_tree_clean_at_build_start": certification["source_tree_clean"],
                "certification_mode": certification["certification_mode"],
                "python_version": verification_python_version,
                "uv_version": uv_version,
                "build_backend": pyproject["build-system"]["build-backend"],
                "build_requirements": pyproject["build-system"]["requires"],
                "ffmpeg_version": ffmpeg_version,
                "ffprobe_version": ffprobe_version,
            },
        )
        expected_kit_names = kit._expected_kit_names(wheel.name)
        zip_path = output / f"{project_name}-{project_version}-windows-x64.zip"
        kit._create_zip(kit_directory, zip_path, expected_kit_names)
        extraction, zip_verification = kit._verify_zip(
            zip_path=zip_path,
            output=output,
            expected_names=expected_kit_names,
            manifest=manifest,
            manifest_sha256=manifest_sha256,
        )
        report["release_kit"] = {
            "status": "passed",
            "directory_name": kit_directory.name,
            "inventory": sorted(expected_kit_names),
            "covered_file_hashes": file_hashes,
            "manifest": kit._MANIFEST_NAME,
            "manifest_sha256": manifest_sha256,
            "manifest_self_hash_strategy": "reported outside manifest",
            "zip_filename": zip_path.name,
            "zip_sha256": common._sha256_file(zip_path),
            "zip_verified": zip_verification,
        }

        _announce("create fresh venv and install ZIP wheel")
        python, cli, environment_evidence = environment._create_and_verify_venv(
            repository=repository,
            output=output,
            extraction=extraction,
            wheel_filename=wheel.name,
            uv=uv,
            env=env,
            project_name=project_name,
            project_version=project_version,
        )
        report["environment"] = {
            **environment_evidence,
            "fresh_venv_class": "external release-gate output outside repository",
            "pythonhome_sanitized": True,
            "pythonpath_sanitized": True,
            "virtual_env_sanitized": True,
            "cli_help": "passed",
        }

        _announce("run release-kit demo generator")
        work = output / "gate-work"
        work.mkdir()
        media, demo_evidence = demo._generate_demo_media(
            python=python,
            extraction=extraction,
            work=work,
            env=env,
        )
        report["demo"] = demo_evidence

        api_token = secrets.token_urlsafe(32)
        webui_username = f"gate-{secrets.token_hex(6)}"
        webui_password = secrets.token_urlsafe(24)
        basic_credentials, basic_header, bearer_header, secret_values = (
            common._auth_headers_and_redaction_values(
                api_token=api_token,
                webui_username=webui_username,
                webui_password=webui_password,
            )
        )
        child_env = env.copy()
        child_env["MEDIA_ANALYZER_API_TOKEN"] = api_token
        child_env["MEDIA_ANALYZER_WEBUI_CREDENTIALS"] = basic_credentials
        initial_port = server._reserve_loopback_port()
        config_path, config_raw = server._prepare_work_config(
            extraction=extraction,
            work=work,
            port=initial_port,
            secret_values=secret_values,
        )
        report["work_config"] = {
            "status": "passed",
            "source": "verified ZIP config.example.yaml copy",
            "profile_b": server._profile_b_ids(config_raw),
            "private_runtime_root": str((work / "runtime").resolve()),
            "secrets_in_config": False,
            "bounded_processing_seconds": 120,
            "bounded_analyzer_seconds": 60,
        }
        report["auth_secrets"] = {
            "status": "passed",
            "generation": "Python secrets module",
            "transport": "child process environment only",
            "persisted": False,
            "reported": False,
        }

        _announce("start installed CLI process 1 and exercise real HTTP")
        active_server, startup_1 = server._start_server_with_bind_retry(
            cli=cli,
            config_path=config_path,
            config_raw=config_raw,
            work=work,
            env=child_env,
            secret_values=secret_values,
        )
        port = active_server.port
        base_url = f"http://127.0.0.1:{port}"
        startup_1["command_pattern"] = (
            f"<fresh-venv>\\Scripts\\{project_name}.exe --config <private-gate-work>\\config.yaml"
        )
        api_auth_evidence = probes._exercise_api_auth(base_url, bearer_header)

        all_results: dict[str, dict[str, Any]] = {}
        persistence_evidence: list[dict[str, Any]] = []
        web_result, web_analysis, web_persistence, webui_evidence = probes._exercise_webui(
            base_url=base_url,
            image_path=media[".png"],
            basic_header=basic_header,
            bearer_header=bearer_header,
            config_raw=config_raw,
            expected_application_version=project_version,
        )
        web_analysis_id = web_result["analysis_id"]
        all_results[web_analysis_id] = web_result
        persistence_evidence.append(web_persistence)

        api_evidence: dict[str, Any] = {}
        for media_name, suffix in (("image", ".png"), ("audio", ".wav"), ("video", ".mp4")):
            result, evidence, persistence = probes._submit_api_analysis(
                base_url=base_url,
                path=media[suffix],
                bearer_header=bearer_header,
                config_raw=config_raw,
                expected_application_version=project_version,
            )
            all_results[result["analysis_id"]] = result
            persistence_evidence.append(persistence)
            api_evidence[media_name] = evidence

        if not demo._verify_no_demo_copies_outside_demo(work):
            raise common.ReleaseVerificationError(
                "cleanup", "Demo media escaped the gate-owned demo directory."
            )
        report["server_1"] = {
            "startup": startup_1,
            "health": startup_1["health"],
            "webui_auth_and_upload": webui_evidence,
            "webui_analysis": web_analysis,
            "api_auth": api_auth_evidence,
            "api_image": api_evidence["image"],
            "api_audio": api_evidence["audio"],
            "api_video": api_evidence["video"],
            "persistence": persistence_evidence,
            "cleanup": {
                "status": "passed",
                "analysis_count": len(persistence_evidence),
                "workspaces_absent": True,
                "quarantine_residue_absent": True,
                "demo_media_confined": True,
            },
        }

        _announce("gracefully stop installed CLI process 1")
        shutdown_1 = server._graceful_shutdown(active_server, secret_values=secret_values)
        report["server_1"]["shutdown"] = shutdown_1
        active_server = None

        _announce("restart installed CLI and retrieve persisted results")
        active_server, startup_2 = server._start_server_same_config(
            cli=cli,
            config_path=config_path,
            work=work,
            env=child_env,
            port=port,
            secret_values=secret_values,
        )
        restarted_url = f"http://127.0.0.1:{port}"
        restart_retrieval = probes._retrieve_after_restart(
            base_url=restarted_url,
            results=all_results,
            bearer_header=bearer_header,
        )
        _web_headers, web_restart_body = transport._require_http(
            "GET",
            f"{restarted_url}/analyses/{web_analysis_id}/result",
            expected_status=200,
            phase="webui_restart",
            headers={"Authorization": basic_header},
        )
        if web_analysis_id.encode("utf-8") not in web_restart_body:
            raise common.ReleaseVerificationError(
                "webui_restart",
                "Restarted WebUI did not render the prior result.",
                analysis_id=web_analysis_id,
            )
        report["server_2"] = {
            "startup": startup_2,
            "restart_retrieval": restart_retrieval,
            "webui_restart": {
                "status": "passed",
                "analysis_id": web_analysis_id,
                "http_status": 200,
            },
        }

        _announce("gracefully stop installed CLI process 2")
        shutdown_2 = server._graceful_shutdown(active_server, secret_values=secret_values)
        report["server_2"]["shutdown"] = shutdown_2
        active_server = None
        report["process_cleanup"] = {
            "listener_closed": shutdown_1["listener_closed"] and shutdown_2["listener_closed"],
            "processes_reaped": shutdown_1["process_reaped"] and shutdown_2["process_reaped"],
            "owned_server_process_count": 2,
            "broad_system_cleanup_used": False,
        }

        _announce("final source and release-kit integrity checks")
        final_source_sha = common._run_command(
            [git, "rev-parse", "HEAD"],
            cwd=repository,
            env=env,
            timeout=10.0,
            phase="source",
        ).stdout.strip()
        report["source_sha_at_end"] = final_source_sha
        report["source_sha_stable"] = final_source_sha == source_sha
        build._require_stable_source_sha(initial_sha=source_sha, final_sha=final_source_sha)
        final_source_status = common._run_command(
            [git, "status", "--short", "--untracked-files=all"],
            cwd=repository,
            env=env,
            timeout=10.0,
            phase="source",
        ).stdout.splitlines()
        report["source_status_at_end"] = final_source_status
        if not development and final_source_status:
            raise common.ReleaseVerificationError(
                "source", "Source tree became dirty during strict gate."
            )
        if final_source_status != source_status:
            raise common.ReleaseVerificationError(
                "source", "Release gate changed repository status."
            )
        for name, expected_hash in file_hashes.items():
            if common._sha256_file(kit_directory / name) != expected_hash:
                raise common.ReleaseVerificationError(
                    "release_kit", f"Release-kit input changed: {name}."
                )
        if common._sha256_file(kit_directory / kit._MANIFEST_NAME) != manifest_sha256:
            raise common.ReleaseVerificationError(
                "release_kit", "Release manifest changed after assembly."
            )

        report["certified"] = bool(not development and not final_source_status)
        report["source_tree_clean"] = not final_source_status
        report["overall_status"] = "development_pass" if development else "passed"
        reporting._write_report(report, output=output, secret_values=secret_values)
        return report
    except BaseException as caught:
        # Reap the owned server even when the operator interrupts the gate.
        error = (
            caught
            if isinstance(caught, common.ReleaseVerificationError)
            else common.ReleaseVerificationError(
                "internal",
                f"Unexpected release-gate failure: {type(caught).__name__}.",
            )
        )
        if active_server is not None:
            emergency_tail = active_server.output_tail(secret_values)
            server._emergency_stop(active_server)
            if error.server_output_tail is None:
                error.server_output_tail = emergency_tail
        report["certified"] = False
        report["overall_status"] = "failed"
        report["failure"] = {
            "phase": error.phase,
            "message": common._redact(str(error), secret_values),
            "analysis_id": error.analysis_id,
            "process_returncode": error.process_returncode,
            "server_output_tail": common._redact(error.server_output_tail or "", secret_values),
        }
        reporting._write_report(report, output=output, secret_values=secret_values)
        if not isinstance(caught, Exception):
            raise
        return report


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Assemble and exercise the complete product release handoff."
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        help="empty directory outside the repository; defaults to an OS temp directory",
    )
    parser.add_argument(
        "--development",
        action="store_true",
        help="allow a dirty source tree but produce non-certifying evidence",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        report = run_release_gate(
            output_directory=args.output_dir,
            development=args.development,
        )
    except common.ReleaseVerificationError as error:
        print(f"Release verification failed in {error.phase}: {error}", file=sys.stderr)
        return 1
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report["overall_status"] in {"passed", "development_pass"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
