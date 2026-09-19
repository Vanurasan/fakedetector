"""Fresh installation and installed-wheel provenance verification."""

from __future__ import annotations

import json
import os
import textwrap
from pathlib import Path
from typing import Any

import verify_release_package as package_verifier

from . import common


def _installed_probe(
    python: Path,
    *,
    cwd: Path,
    env: dict[str, str],
    project_name: str,
) -> dict[str, Any]:
    probe = textwrap.dedent(
        f"""
        import importlib.metadata as metadata
        import importlib.resources as resources
        import json
        import os
        import platform
        import sys
        from pathlib import Path

        import fakedetector

        distribution = metadata.distribution({project_name!r})
        direct_url_text = distribution.read_text("direct_url.json")
        resource_root = resources.files("fakedetector")
        resources_found = {{
            name: resource_root.joinpath(name).is_file()
            for name in {list(package_verifier._REQUIRED_RESOURCES)!r}
        }}
        installed = {{
            item.metadata["Name"]: item.version
            for item in metadata.distributions()
            if item.metadata["Name"]
        }}
        implementation = sys.implementation.version
        marker_environment = {{
            "implementation_name": sys.implementation.name,
            "implementation_version": ".".join(str(part) for part in (
                implementation.major, implementation.minor, implementation.micro
            )),
            "os_name": os.name,
            "platform_machine": platform.machine(),
            "platform_python_implementation": platform.python_implementation(),
            "platform_release": platform.release(),
            "platform_system": platform.system(),
            "platform_version": platform.version(),
            "python_full_version": platform.python_version(),
            "python_version": ".".join(platform.python_version_tuple()[:2]),
            "sys_platform": sys.platform,
            "extra": "",
        }}
        print(json.dumps({{
            "package_version": distribution.version,
            "module_version": fakedetector.__version__,
            "module_origin": str(Path(fakedetector.__file__).resolve()),
            "direct_url": json.loads(direct_url_text) if direct_url_text else None,
            "resources": resources_found,
            "installed": installed,
            "marker_environment": marker_environment,
            "python_version": platform.python_version(),
            "sys_path": sys.path,
            "user_site_enabled": bool(__import__("site").ENABLE_USER_SITE),
        }}, sort_keys=True))
        """
    )
    completed = common._run_command(
        [str(python), "-I", "-c", probe],
        cwd=cwd,
        env=env,
        timeout=common._PHASE_TIMEOUTS["probe"],
        phase="installed_probe",
    )
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError:
        raise common.ReleaseVerificationError(
            "installed_probe", "Installed probe returned invalid JSON."
        ) from None
    if not isinstance(payload, dict):
        raise common.ReleaseVerificationError(
            "installed_probe", "Installed probe returned an invalid value."
        )
    return payload


def _create_and_verify_venv(
    *,
    repository: Path,
    output: Path,
    extraction: Path,
    wheel_filename: str,
    uv: str,
    env: dict[str, str],
    project_name: str,
    project_version: str,
) -> tuple[Path, Path, dict[str, Any]]:
    venv = output / "installed-venv"
    common._run_command(
        [uv, "venv", "--python", "3.12", "--no-project", str(venv)],
        cwd=output,
        env=env,
        timeout=common._PHASE_TIMEOUTS["venv"],
        phase="venv",
    )
    scripts = venv / ("Scripts" if os.name == "nt" else "bin")
    python = scripts / ("python.exe" if os.name == "nt" else "python")
    cli = scripts / (f"{project_name}.exe" if os.name == "nt" else project_name)
    wheel = extraction / wheel_filename
    constraints = extraction / "runtime-constraints.txt"
    common._run_command(
        [
            uv,
            "pip",
            "install",
            "--python",
            str(python),
            "--constraint",
            str(constraints),
            str(wheel),
        ],
        cwd=output,
        env=env,
        timeout=common._PHASE_TIMEOUTS["install"],
        phase="install",
    )
    common._run_command(
        [uv, "pip", "check", "--python", str(python)],
        cwd=output,
        env=env,
        timeout=common._PHASE_TIMEOUTS["probe"],
        phase="dependency_check",
    )
    probe = _installed_probe(python, cwd=output, env=env, project_name=project_name)

    if probe["package_version"] != project_version or probe["module_version"] != project_version:
        raise common.ReleaseVerificationError(
            "installed_probe", "Installed version differs from build metadata."
        )
    if not probe["python_version"].startswith("3.12."):
        raise common.ReleaseVerificationError(
            "installed_probe", "Fresh venv is not running Python 3.12."
        )
    if probe["user_site_enabled"]:
        raise common.ReleaseVerificationError(
            "installed_probe", "Fresh venv unexpectedly enables user site."
        )
    if not all(probe["resources"].values()):
        raise common.ReleaseVerificationError(
            "installed_probe", "Installed package resources are incomplete."
        )

    module_origin = Path(probe["module_origin"]).resolve()
    if venv.resolve() not in module_origin.parents or "site-packages" not in {
        part.casefold() for part in module_origin.parts
    }:
        raise common.ReleaseVerificationError(
            "installed_probe", "Package did not import from venv site-packages."
        )
    repository_resolved = repository.resolve()
    checkout_on_sys_path = any(
        candidate == repository_resolved or repository_resolved in candidate.parents
        for raw_path in probe["sys_path"]
        if raw_path
        for candidate in [Path(raw_path).resolve()]
    )
    if repository_resolved in module_origin.parents or checkout_on_sys_path:
        raise common.ReleaseVerificationError(
            "installed_probe", "Source checkout leaked into installed runtime."
        )
    direct_url = probe["direct_url"]
    if not isinstance(direct_url, dict) or direct_url.get("url") != wheel.as_uri():
        raise common.ReleaseVerificationError(
            "installed_probe", "Installed project is not bound to ZIP wheel bytes."
        )
    if direct_url.get("dir_info", {}).get("editable", False):
        raise common.ReleaseVerificationError(
            "installed_probe", "Editable installation is forbidden."
        )

    try:
        expected = package_verifier._parse_constraints(constraints, probe["marker_environment"])
        comparison = package_verifier._assert_runtime_matches_constraints(
            installed=probe["installed"],
            expected=expected,
            direct_dev_names=package_verifier._direct_dev_names(repository / "pyproject.toml"),
        )
    except package_verifier.VerificationError as error:
        raise common.ReleaseVerificationError("dependency_comparison", str(error)) from None
    help_result = common._run_command(
        [str(cli), "--help"],
        cwd=output,
        env=env,
        timeout=common._PHASE_TIMEOUTS["probe"],
        phase="cli_help",
    )
    if "usage:" not in help_result.stdout.casefold():
        raise common.ReleaseVerificationError(
            "cli_help", "Installed CLI help lacks argparse usage."
        )
    return (
        python,
        cli,
        {
            "python_version": probe["python_version"],
            "installed_origin": probe["module_origin"],
            "editable_install": False,
            "source_checkout_on_sys_path": False,
            "user_site_enabled": False,
            "installed_from_zip_wheel": True,
            "dependency_check": "passed",
            "runtime_dependency_comparison": comparison,
            "installed_resources": sorted(
                name for name, present in probe["resources"].items() if present
            ),
        },
    )
