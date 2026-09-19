"""Shared HTTP status policy for terminal file intake outcomes."""

from fakedetector.domain import AnalysisStatus


def intake_http_status(status: AnalysisStatus, error_code: str) -> int:
    if status is AnalysisStatus.FAILED:
        return 500
    if error_code == "file_too_large":
        return 413
    if error_code in {
        "missing_extension",
        "unsupported_extension",
        "unsupported_mime_type",
        "unsupported_media_type",
        "file_signature_mismatch",
    }:
        return 415
    return 422
