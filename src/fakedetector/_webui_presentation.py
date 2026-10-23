"""Private, read-only WebUI formatting and versioned display metadata."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from urllib.parse import quote, urlencode

from fakedetector._webui_i18n import translate
from fakedetector.domain import AnalyzerResult, Localization

Page = Literal["upload", "submit", "status", "result"]

# Display metadata only. Tests compare these exact identities with the closed catalog.
ANALYZER_METADATA: dict[tuple[str, str], str] = {
    ("image_metadata_consistency", "1.0.0"): "CORE",
    ("audio_pcm_quality", "1.0.0"): "CORE",
    ("video_sampled_frame_quality", "1.0.0"): "CORE",
    ("image_copy_move_correspondence", "1.0.0"): "CORE",
    ("image_jpeg_double_quantization", "1.0.0"): "CORE",
    ("audio_aasist_l_measurement", "1.0.0"): "EXPERIMENTAL",
    ("audio_repeated_segment_correspondence", "1.0.0"): "EXPERIMENTAL",
    ("video_repeated_content_correspondence", "1.0.0"): "EXPERIMENTAL_WEAK",
    ("video_visual_discontinuity", "1.0.0"): "EXPERIMENTAL_WEAK",
    ("video_timing_anomaly", "1.0.0"): "EXPERIMENTAL_WEAK",
    ("image_noise_residual_consistency", "1.0.0"): "EXPERIMENTAL_WEAK",
    ("image_resampling_consistency", "1.0.0"): "EXPERIMENTAL_WEAK",
    ("audio_temporal_discontinuity", "1.0.0"): "EXPERIMENTAL",
    ("audio_spectral_consistency", "1.0.0"): "EXPERIMENTAL",
    ("audio_background_noise_consistency", "1.0.0"): "EXPERIMENTAL_WEAK",
}
_AASIST = ("audio_aasist_l_measurement", "1.0.0")


def page_url(
    page: Page,
    locale: str,
    *,
    analysis_id: str = "",
    paused: bool = False,
) -> str:
    """Construct only known local routes and allowlisted presentation parameters."""
    paths = {"upload": "/", "submit": "/analyses"}
    if page in {"status", "result"}:
        path = "/analyses/" + quote(analysis_id, safe="")
        if page == "result":
            path += "/result"
    else:
        path = paths[page]
    query = {"lang": locale if locale in {"ru", "en"} else "ru"}
    if paused and page in {"status", "result"}:
        query["refresh"] = "off"
    return path + "?" + urlencode(query)


def number(value: int | float | None) -> str:
    """Keep score/coverage values exact, including zero, in either language."""
    if value is None:
        return ""
    return str(value).removesuffix(".0")


def quantity(locale: str, value: int | float | None) -> str:
    """Format a measured quantity without changing its value."""
    if value is None:
        return translate(locale, "common.unknown")
    rendered = number(value)
    return rendered.replace(".", ",") if locale == "ru" else rendered


def time_display(locale: str, value: datetime | None) -> str:
    """Display domain UTC timestamps deterministically, never using host timezone."""
    if value is None:
        return translate(locale, "common.unknown")
    date = value.strftime("%d.%m.%Y" if locale == "ru" else "%Y-%m-%d")
    return f"{date} {value:%H:%M:%S} UTC"


def time_iso(value: datetime) -> str:
    """Preserve the canonical aware UTC value, including fractional seconds."""
    return value.isoformat().replace("+00:00", "Z")


def file_size(locale: str, value: int) -> str:
    """Round only the human size; always include the exact byte count."""
    display = f"{value / 1_048_576:.2f}"
    if locale == "ru":
        display = display.replace(".", ",")
    return (
        f"{display} {translate(locale, 'format.mib')} ({value} {translate(locale, 'format.bytes')})"
    )


def duration(locale: str, milliseconds: int | None) -> str:
    """Show a persisted duration in seconds with exact millisecond precision."""
    if milliseconds is None:
        return translate(locale, "common.unknown")
    whole, fraction = divmod(milliseconds, 1000)
    value = f"{whole}.{fraction:03}".rstrip("0").rstrip(".")
    if locale == "ru":
        value = value.replace(".", ",")
    return f"{value} {translate(locale, 'format.seconds')}"


def localization_text(locale: str, value: Localization | None) -> str:
    """Describe stored localization fields without inferring media evidence."""
    if value is None:
        return translate(locale, "common.unknown")
    if value.type == "file":
        return translate(locale, "localization.file")
    if value.type == "bounding_box":
        return translate(
            locale,
            "localization.box",
            x=quantity(locale, value.x),
            y=quantity(locale, value.y),
            width=quantity(locale, value.width),
            height=quantity(locale, value.height),
        )
    if value.type == "time_interval":
        return translate(
            locale,
            "localization.time",
            start=quantity(locale, value.start_seconds),
            end=quantity(locale, value.end_seconds),
        )
    return translate(
        locale,
        "localization.frames",
        start=value.start_frame,
        end=value.end_frame,
    )


def analyzer_metadata(analyzer: AnalyzerResult) -> tuple[str, str] | None:
    """Return name key and maturity only for an exact known ID/version pair."""
    maturity = ANALYZER_METADATA.get((analyzer.analyzer_id, analyzer.analyzer_version))
    if maturity is None:
        return None
    return f"analyzer.{analyzer.analyzer_id}.name", f"maturity.{maturity}"


def non_scoring(analyzer: AnalyzerResult) -> bool:
    """The accepted AASIST-L identity alone carries this presentation label."""
    return (analyzer.analyzer_id, analyzer.analyzer_version) == _AASIST


def measurement_labels(analyzer: AnalyzerResult) -> tuple[str, ...]:
    """Display an explicit known raw state; do not derive sufficiency from prose."""
    metrics = analyzer.raw_metrics
    if not (
        non_scoring(analyzer)
        and analyzer.status.value == "completed"
        and analyzer.applicable
        and metrics.get("profile") == "AASIST-L-PCM16-FIRST-1"
        and metrics.get("state") == "insufficient_evidence"
    ):
        return ()
    labels: tuple[str, ...] = ("measurement.insufficient",)
    reason = metrics.get("insufficiency_reason")
    if reason in ("digital_silence", "too_short"):
        labels += (f"measurement.{reason}",)
    return labels
