"""Shared intake HTTP policy and adapter import boundary regressions."""

from __future__ import annotations

import subprocess
import sys

import pytest

from fakedetector._http_status import intake_http_status
from fakedetector.domain import AnalysisStatus


@pytest.mark.parametrize("first_adapter", ["webui", "api"])
def test_http_adapters_import_independently_and_share_policy(first_adapter: str) -> None:
    script = f"""
import importlib
import sys

first = importlib.import_module('fakedetector.{first_adapter}')
other_name = 'api' if '{first_adapter}' == 'webui' else 'webui'
assert 'fakedetector.' + other_name not in sys.modules
other = importlib.import_module('fakedetector.' + other_name)
policy = importlib.import_module('fakedetector._http_status')
assert first.intake_http_status is other.intake_http_status is policy.intake_http_status
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize(
    "code",
    ["file_too_large", "unsupported_extension", "unsafe_or_unreadable_file", "internal_error"],
)
def test_failed_intake_takes_precedence_over_rejection_code(code: str) -> None:
    assert intake_http_status(AnalysisStatus.FAILED, code) == 500
