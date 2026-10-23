"""M7 presentation acceptance: authoritative data, stateless locales and safe navigation."""

from __future__ import annotations

import html
from datetime import UTC, datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import get_args
from urllib.parse import parse_qs, urlsplit

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from stage8_helpers import (
    StubApplicationService,
    make_completed_result,
    make_config,
    make_error,
    make_rejected_result,
    make_status,
)
from test_analysis_assessment import _finding, _result
from test_webui import AUTH, SAME_ORIGIN, _client

from fakedetector._webui_i18n import TRANSLATIONS, error_copy, translate
from fakedetector._webui_presentation import (
    ANALYZER_METADATA,
    analyzer_metadata,
    duration,
    file_size,
    localization_text,
    measurement_labels,
    non_scoring,
    number,
    page_url,
    time_display,
    time_iso,
)
from fakedetector.analyzers._catalog import _RUNTIME_ANALYZER_DEFINITIONS
from fakedetector.api import install_api
from fakedetector.app import create_app
from fakedetector.application import (
    AnalysisNotFoundError,
    AnalysisPendingError,
    AnalysisPersistenceUnavailableError,
    AnalysisSubmission,
)
from fakedetector.auth import APIBearerAuthenticator, WebUIBasicAuthenticator
from fakedetector.config.models import RiskAssessmentConfig
from fakedetector.domain import (
    AnalysisResult,
    AnalysisStatus,
    AnalyzerStatus,
    BoundingBoxLocalization,
    CleanupStatus,
    CompletenessStatus,
    FileLocalization,
    FindingSeverity,
    FrameIntervalLocalization,
    MediaType,
    ProcessingStage,
    Recommendation,
    RiskLevel,
    TimeIntervalLocalization,
)
from fakedetector.lifecycle._assessment import AnalysisAssessmentService
from fakedetector.webui import install_webui


class _Markup(HTMLParser):
    def __init__(self, source: str) -> None:
        super().__init__()
        self.tags: dict[str, list[dict[str, str | None]]] = {}
        self.feed(source)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.tags.setdefault(tag, []).append(dict(attrs))


@pytest.mark.parametrize("locale", ["ru", "en"])
def test_page_shell_form_and_language_links(tmp_path: Path, locale: str) -> None:
    response = _client(tmp_path, StubApplicationService()).get(f"/?lang={locale}", auth=AUTH)
    markup = _Markup(response.text)
    assert markup.tags["html"] == [{"lang": locale}]
    assert len(markup.tags["h1"]) == 1
    assert markup.tags["main"][0]["id"] == "main"
    assert markup.tags["form"] == [
        {
            "id": "analysis-upload",
            "action": f"/analyses?lang={locale}",
            "method": "post",
            "enctype": "multipart/form-data",
        }
    ]
    assert len(markup.tags["input"]) == 1
    field = markup.tags["input"][0]
    assert field["type"] == "file" and field["name"] == "file"
    assert field["aria-describedby"] == "file-help formats-heading"
    assert "required" in field and "hidden" not in field.values()
    assert all("name" not in button for button in markup.tags["button"])
    assert all(not urlsplit(link["href"] or "").netloc for link in markup.tags["a"])
    assert markup.tags["link"][0]["href"] == "/static/styles.css"
    assert all("src" not in script for script in markup.tags["script"])
    assert "set-cookie" not in response.headers
    assert ("20 МиБ" if locale == "ru" else "20 MiB") in response.text


@pytest.mark.parametrize(
    "query",
    [
        "",
        "lang=",
        "lang=fr",
        "lang=EN",
        "lang=en&lang=ru",
        "lang=en&lang=en",
        "lang=%00en",
        "lang=en%0D%0A",
        "lang=%ZZ",
        "lang=%3Cscript%3E",
        "lang=" + "x" * 3000,
    ],
)
def test_invalid_or_missing_language_is_russian(tmp_path: Path, query: str) -> None:
    response = _client(tmp_path, StubApplicationService()).get(
        "/?" + query,
        auth=AUTH,
        headers={"Accept-Language": "en-US,en"},
    )
    assert response.status_code == 200
    assert '<html lang="ru">' in response.text
    assert 'action="/analyses?lang=ru"' in response.text
    assert all("lang=en&lang" not in (a["href"] or "") for a in _Markup(response.text).tags["a"])


def test_language_survives_submission_refresh_pending_and_ready(tmp_path: Path) -> None:
    service = StubApplicationService()
    client = _client(tmp_path, service)
    response = client.post(
        "/analyses?lang=en&unexpected=https://invalid.example",
        auth=AUTH,
        headers=SAME_ORIGIN,
        files={"file": ("sample.png", b"test", "image/png")},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"] == "/analyses/analysis-001?lang=en"
    status = client.get(response.headers["location"], auth=AUTH)
    assert 'content="2;url=/analyses/analysis-001?lang=en"' in status.text
    assert "Analysis running" in status.text
    service.result_error = AnalysisPendingError(service.status)
    pending = client.get("/analyses/analysis-001/result?lang=en", auth=AUTH)
    assert pending.status_code == 202
    assert 'content="2;url=/analyses/analysis-001/result?lang=en"' in pending.text
    service.result_error = None
    service.status = make_status(result_available=True)
    ready = client.get("/analyses/analysis-001?lang=en", auth=AUTH, follow_redirects=False)
    assert ready.status_code == 303
    assert ready.headers["location"] == "/analyses/analysis-001/result?lang=en"
    assert '<html lang="en">' in client.get(ready.headers["location"], auth=AUTH).text


@pytest.mark.parametrize("path", ["/", "/analyses", "/analyses/id", "/analyses/id/result"])
def test_english_basic_challenge_on_every_html_route(tmp_path: Path, path: str) -> None:
    client = _client(tmp_path, StubApplicationService())
    response = client.request("POST" if path == "/analyses" else "GET", path + "?lang=en")
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == 'Basic realm="FakeDetector"'
    assert '<html lang="en">' in response.text
    assert "HTTP Basic sign-in is required." in response.text


@pytest.mark.parametrize(
    "query,paused",
    [
        ("lang=en", False),
        ("lang=en&refresh=off", True),
        ("lang=en&refresh=OFF", False),
        ("lang=en&refresh=", False),
        ("lang=en&refresh=off&refresh=off", False),
    ],
)
@pytest.mark.parametrize("result_route", [False, True])
def test_refresh_pause_resume_and_language_navigation(
    tmp_path: Path,
    query: str,
    paused: bool,
    result_route: bool,
) -> None:
    service = StubApplicationService()
    if result_route:
        service.result_error = AnalysisPendingError(service.status)
    path = "/analyses/analysis-001" + ("/result" if result_route else "")
    response = _client(tmp_path, service).get(path + "?" + query, auth=AUTH)
    assert response.status_code == (202 if result_route else 200)
    markup = _Markup(response.text)
    assert any(meta.get("http-equiv") == "refresh" for meta in markup.tags["meta"]) != paused
    hrefs = [a["href"] for a in markup.tags["a"]]
    assert path + "?lang=en" in hrefs
    assert path + "?lang=en&refresh=off" in hrefs
    assert path + "?lang=ru" + ("&refresh=off" if paused else "") in hrefs
    assert "/?lang=en" in hrefs
    assert "Pause refresh" in response.text if not paused else "Analysis continues" in response.text
    assert service.status.status == AnalysisStatus.RUNNING


def test_paused_ready_redirect_and_post_error_switch_are_safe(tmp_path: Path) -> None:
    service = StubApplicationService()
    service.status = make_status(result_available=True)
    client = _client(tmp_path, service)
    response = client.get(
        "/analyses/analysis-001?lang=en&refresh=off&next=//evil.example",
        auth=AUTH,
        follow_redirects=False,
    )
    assert response.headers["location"] == "/analyses/analysis-001/result?lang=en&refresh=off"
    denied = client.post("/analyses?lang=en&refresh=off", auth=AUTH)
    assert denied.status_code == 403
    assert "The upload request failed the origin check." in denied.text
    hrefs = [a["href"] for a in _Markup(denied.text).tags["a"]]
    assert set(hrefs) <= {"#main", "/?lang=en", "/?lang=ru"}
    assert "Open upload in Russian" in denied.text


@pytest.mark.parametrize(
    "code,status",
    [
        ("file_too_large", 413),
        ("unsupported_extension", 415),
        ("file_signature_mismatch", 415),
        ("unsafe_or_unreadable_file", 422),
    ],
)
def test_localized_terminal_intake_errors_keep_http_mapping(
    tmp_path: Path,
    code: str,
    status: int,
) -> None:
    service = StubApplicationService()
    result = make_rejected_result(code=code)
    service.submission = AnalysisSubmission(result.analysis_id, result.status, result.stage, result)
    response = _client(tmp_path, service).post(
        "/analyses?lang=en",
        auth=AUTH,
        headers=SAME_ORIGIN,
        files={"file": ("sample.png", b"test", "image/png")},
    )
    assert response.status_code == status
    assert '<html lang="en">' in response.text
    assert f"/analyses/{result.analysis_id}/result?lang=en" in response.text
    assert code in response.text


@pytest.mark.parametrize(
    "error,status",
    [
        (AnalysisNotFoundError(), 404),
        (AnalysisPersistenceUnavailableError(), 503),
        (RuntimeError("secret C:\\private\\runtime"), 500),
    ],
)
def test_localized_get_errors_and_language_switch(tmp_path: Path, error: Exception, status: int):
    service = StubApplicationService()
    service.result_error = error
    response = _client(tmp_path, service).get("/analyses/id/result?lang=en&next=//evil", auth=AUTH)
    assert response.status_code == status
    assert "/analyses/id/result?lang=ru" in response.text
    assert "secret" not in response.text and "C:\\private" not in response.text
    assert "next=" not in response.text


@pytest.mark.parametrize("locale", ["ru", "en"])
@pytest.mark.parametrize(
    "state,level",
    [
        ("complete", "low"),
        ("complete", "medium"),
        ("complete", "high"),
        ("partial", "low"),
        ("partial", "medium"),
        ("partial", "high"),
        ("insufficient", None),
        ("rejected", None),
        ("failed", None),
    ],
)
def test_authoritative_result_states_order_and_immutability(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    locale: str,
    state: str,
    level: str | None,
) -> None:
    service = StubApplicationService()
    if state in {"rejected", "failed"}:
        service.result = make_rejected_result(status=AnalysisStatus(state))
    else:
        completed = 2 if level == "high" else 1
        analyzers = [_result("a" + str(i)) for i in range(completed)]
        if state != "complete":
            analyzers += [_result("err", AnalyzerStatus.ERROR)]
        if state == "insufficient":
            analyzers += [_result("timeout", AnalyzerStatus.TIMEOUT)]
        findings = (
            [
                _finding(
                    "f" + str(i),
                    source_analyzer_id=a.analyzer_id,
                    severity=FindingSeverity.SIGNIFICANT,
                )
                for i, a in enumerate(analyzers[:completed])
            ]
            if level in {"medium", "high"}
            else []
        )
        completeness, risk, recommendation = AnalysisAssessmentService(
            RiskAssessmentConfig()
        ).assess(
            [a.analyzer_id for a in analyzers],
            analyzers,
            findings,
        )
        payload = make_completed_result().model_dump(mode="python")
        payload.update(
            status="completed" if state == "complete" else "partial",
            analyzers=analyzers,
            findings=findings,
            completeness=completeness,
            risk_assessment=risk,
            recommendation=recommendation,
        )
        service.result = AnalysisResult.model_validate(payload)
        assert (risk.final_level.value if risk.final_level else None) == level
    before = service.result.model_dump_json()

    def forbidden(*args, **kwargs):
        pytest.fail("Rendering must not invoke assessment")

    monkeypatch.setattr(AnalysisAssessmentService, "assess", forbidden)
    response = _client(tmp_path, service).get("/analyses/id/result?lang=" + locale, auth=AUTH)
    assert response.status_code == 200
    assert service.result.model_dump_json() == before
    assert f'data-risk="{level or "unavailable"}"' in response.text
    assert (
        "original language" in response.text
        if locale == "en"
        else "исходном языке" in response.text
    )
    order = [
        response.text.index('id="' + label + '"')
        for label in (
            "file-heading",
            "interpretation-heading",
            "recommendation-heading",
            "findings-heading",
            "analyzers-heading",
        )
    ]
    assert order == sorted(order)
    assert response.text.index('class="notice" aria-label=') < order[1]
    if level == "low":
        assert '<strong class="score">0</strong>' in response.text
    if service.result.recommendation:
        assert html.escape(service.result.recommendation.text) in response.text


@pytest.mark.parametrize("status", list(AnalyzerStatus))
def test_analyzer_statuses_unknown_versions_and_untrusted_content(tmp_path: Path, status):
    service = StubApplicationService()
    analyzer = _result("audio_aasist_l_measurement", status, version="99.0.0")
    unsafe = '<img src=x onerror="alert(1)">'
    analyzer.summary = unsafe
    analyzer.warnings = [unsafe]
    analyzer.raw_metrics = {"untrusted": unsafe}
    service.result.analyzers = [analyzer]
    service.result.file.original_name = unsafe * 30
    before = service.result.model_dump_json()
    response = _client(tmp_path, service).get("/analyses/id/result?lang=en", auth=AUTH)
    assert response.status_code == 200
    assert unsafe not in response.text
    assert "&lt;img" in response.text and r"\u003cimg" in response.text
    assert "Version metadata unavailable" in response.text
    assert "Excluded from risk scoring" not in response.text
    assert "No errors or warnings were recorded" not in response.text
    assert analyzer.analyzer_id + "@99.0.0" in response.text
    assert service.result.model_dump_json() == before


@pytest.mark.parametrize("state", ["partial", "failed"])
def test_cleanup_failures_visible_outside_details(tmp_path: Path, state: str) -> None:
    service = StubApplicationService()
    service.result.cleanup.status = CleanupStatus(state)
    service.result.cleanup.errors = [make_error("cleanup_failed", "cleanup")]
    service.result.cleanup.original_file_deleted = False
    response = _client(tmp_path, service).get("/analyses/id/result?lang=en", auth=AUTH)
    warning = (
        "Temporary data cleanup was partial."
        if state == "partial"
        else "Temporary data cleanup failed."
    )
    assert response.text.index(warning) < response.text.index('class="card technical"')
    assert "No errors or warnings were recorded" not in response.text
    assert "cleanup_failed" in response.text


@pytest.mark.parametrize("raw", [True, False])
def test_english_aasist_silence_reports_execution_without_sufficiency(tmp_path: Path, raw: bool):
    import numpy as np
    from test_audio_aasist_l import ANALYZER, _request
    from test_preprocessing import _audio_descriptor

    analyzer = ANALYZER.analyze(_request(tmp_path, np.zeros(8000, dtype="<i2")))
    completeness, risk, recommendation = AnalysisAssessmentService(
        RiskAssessmentConfig(model_id="diploma_ensemble_v1"),
    ).assess([analyzer.analyzer_id], [analyzer], [])
    service = StubApplicationService()
    payload = make_completed_result().model_dump(mode="python")
    payload.update(
        file=_audio_descriptor(duration_seconds=0.5, sample_rate_hz=16000, channels=1),
        analyzers=[
            analyzer.model_copy(update={"raw_metrics": analyzer.raw_metrics if raw else {}})
        ],
        completeness=completeness,
        risk_assessment=risk,
        recommendation=recommendation,
    )
    service.result = AnalysisResult.model_validate(payload)
    before = service.result.model_dump_json()
    response = _client(tmp_path, service).get("/analyses/id/result?lang=en", auth=AUTH)
    assert "Applicable plan completed" in response.text
    assert (
        "Low technical risk or score=0 does not establish authenticity or safety." in response.text
    )
    assert "Excluded from risk scoring" in response.text
    assert 'class="score">0</strong> / 100' in response.text
    assert "not probability" in response.text
    assert "No additional action for the checks performed" in response.text
    assert ("Measurement: insufficient evidence" in response.text) == raw
    assert ("Selected prefix is digitally silent" in response.text) == raw
    assert service.result.model_dump_json() == before


def test_translations_cover_enums_actions_and_exact_catalog() -> None:
    assert TRANSLATIONS["ru"].keys() == TRANSLATIONS["en"].keys()
    for group, enum in (
        ("analysis_status", AnalysisStatus),
        ("stage", ProcessingStage),
        ("risk", RiskLevel),
        ("severity", FindingSeverity),
        ("analyzer_status", AnalyzerStatus),
        ("completeness", CompletenessStatus),
        ("cleanup", CleanupStatus),
        ("media", MediaType),
    ):
        for member in enum:
            for locale in ("ru", "en"):
                assert TRANSLATIONS[locale][f"{group}.{member.value}"]
    for action in get_args(Recommendation.model_fields["primary_action"].annotation):
        assert TRANSLATIONS["en"]["action." + action]
    expected = {
        (d.analyzer_id, d.analyzer_version): d.maturity.value for d in _RUNTIME_ANALYZER_DEFINITIONS
    }
    assert len(expected) == 15 and expected == ANALYZER_METADATA
    for identity in expected:
        analyzer = _result(identity[0], version=identity[1])
        metadata = analyzer_metadata(analyzer)
        assert metadata is not None
        assert all(translate(locale, metadata[0]) for locale in ("ru", "en"))
        assert non_scoring(analyzer) == (identity == ("audio_aasist_l_measurement", "1.0.0"))
    unknown = _result("audio_aasist_l_measurement", version="2.0.0")
    assert analyzer_metadata(unknown) is None and not non_scoring(unknown)
    unknown.raw_metrics = {"profile": "AASIST-L-PCM16-FIRST-1", "state": "insufficient_evidence"}
    assert measurement_labels(unknown) == ()


def test_dictionary_fallback_does_not_translate_arbitrary_text(monkeypatch):
    monkeypatch.delitem(TRANSLATIONS["en"], "upload.title")
    assert translate("en", "upload.title") == "Новый анализ"
    assert translate("en", "not-a-known-key") == "Label unavailable"
    assert error_copy("en", "unknown-error") == "The request could not be completed."
    assert (
        error_copy("en", "unknown-error", action=True)
        == "Return to upload or share the code with the operator"
    )


def test_utc_size_duration_and_exact_numbers() -> None:
    timestamp = datetime(2026, 10, 24, 15, 4, 5, 123456, tzinfo=UTC)
    assert time_display("ru", timestamp) == "24.10.2026 15:04:05 UTC"
    assert time_display("en", timestamp) == "2026-10-24 15:04:05 UTC"
    assert time_iso(timestamp) == "2026-10-24T15:04:05.123456Z"
    assert time_display("en", None) == "Not recorded"
    assert file_size("en", 1048576) == "1.00 MiB (1048576 bytes)"
    assert file_size("ru", 20971520) == "20,00 МиБ (20971520 байт)"
    assert file_size("en", 0) == "0.00 MiB (0 bytes)"
    assert duration("en", 1001) == "1.001 s"
    assert duration("ru", 0) == "0 с"
    assert number(5.999999999) == "5.999999999"
    assert number(1 / 3) == str(1 / 3)
    assert number(0.0) == "0" and number(None) == ""


@pytest.mark.parametrize(
    "value,ru,en",
    [
        (FileLocalization(type="file"), "Файл целиком", "Whole file"),
        (
            TimeIntervalLocalization(type="time_interval", start_seconds=1.25, end_seconds=2.5),
            "Интервал: 1,25–2,5 с",
            "Interval: 1.25–2.5 s",
        ),
        (
            FrameIntervalLocalization(type="frame_interval", start_frame=3, end_frame=9),
            "Кадры: 3–9",
            "Frames: 3–9",
        ),
        (
            BoundingBoxLocalization(
                type="bounding_box",
                x=0.1,
                y=0.2,
                width=0.3,
                height=0.4,
                coordinate_space="normalized",
            ),
            "Нормализованная область: x=0,1, y=0,2, ширина=0,3, высота=0,4",
            "Normalized region: x=0.1, y=0.2, width=0.3, height=0.4",
        ),
    ],
)
def test_existing_localization_fields_render_as_text(tmp_path: Path, value, ru, en):
    assert localization_text("ru", value) == ru
    assert localization_text("en", value) == en
    service = StubApplicationService()
    finding = _finding("f")
    finding.localization = value
    finding.evidence_refs = ["https://untrusted.invalid/evidence"]
    service.result.findings = [finding]
    response = _client(tmp_path, service).get("/analyses/id/result?lang=en", auth=AUTH)
    assert en in response.text
    assert '<a href="https://untrusted.invalid' not in response.text
    assert "https://untrusted.invalid/evidence" in response.text


def test_url_builder_encodes_identity_and_allows_only_known_parameters() -> None:
    url = page_url("result", "not-a-locale", analysis_id="x/\r\n?next=//evil.example", paused=True)
    parsed = urlsplit(url)
    assert not parsed.scheme and not parsed.netloc
    assert parse_qs(parsed.query) == {"lang": ["ru"], "refresh": ["off"]}
    assert "%2F" in parsed.path and "%0D%0A" in parsed.path


def test_api_result_is_unchanged_by_webui_locale_or_rendering(tmp_path: Path):
    service = StubApplicationService()
    config = make_config(tmp_path)
    app = FastAPI()
    install_api(app, service=service, authenticator=APIBearerAuthenticator("test"), config=config)
    install_webui(app, service=service, authenticator=WebUIBasicAuthenticator(*AUTH), config=config)
    client = TestClient(app)
    original = client.get("/api/v1/analyses/id/result", headers={"Authorization": "Bearer test"})
    for locale in ("ru", "en", "invalid"):
        assert client.get("/analyses/id/result?lang=" + locale, auth=AUTH).status_code == 200
        response = client.get(
            "/api/v1/analyses/id/result?lang=" + locale, headers={"Authorization": "Bearer test"}
        )
        assert response.status_code == original.status_code == 200
        assert response.content == original.content
    assert service.result.model_dump(mode="json") == original.json()


def test_disabled_webui_does_not_register_localized_surface(tmp_path: Path):
    config = make_config(tmp_path, webui_enabled=False)
    client = TestClient(create_app(config))
    for path in ("/", "/analyses/id", "/analyses/id/result", "/static/styles.css"):
        assert client.get(path + "?lang=en&refresh=off").status_code == 404


@pytest.mark.parametrize("stage", list(ProcessingStage))
def test_all_processing_stages_have_activity_and_manual_navigation(tmp_path: Path, stage):
    service = StubApplicationService()
    service.status = make_status(stage=stage)
    response = _client(tmp_path, service).get("/analyses/id?lang=en", auth=AUTH)
    assert response.status_code == 200
    assert "Label unavailable" not in response.text
    assert "Refresh status" in response.text and "New analysis" in response.text
    assert stage.value in response.text
    assert "progressbar" not in response.text


@pytest.mark.parametrize("version", ["0.1.0", "historical"])
@pytest.mark.parametrize("model", ["diploma_ensemble_v1", "score_model_v1", "unknown"])
def test_scale_requires_exact_model_and_risk_is_never_recomputed(tmp_path: Path, model, version):
    service = StubApplicationService()
    risk = service.result.risk_assessment
    risk.model_id, risk.model_version = model, version
    # Deliberately differing stored facts verify that presentation cannot replace final_level.
    risk.final_level = RiskLevel.HIGH
    risk.score = 0
    before = service.result.model_dump_json()
    response = _client(tmp_path, service).get("/analyses/id/result?lang=en", auth=AUTH)
    assert 'data-risk="high"' in response.text and 'class="score">0</strong>' in response.text
    assert (" / 100" in response.text) == (model == "diploma_ensemble_v1" and version == "0.1.0")
    assert "High technical risk" in response.text
    assert service.result.model_dump_json() == before


@pytest.mark.parametrize(
    "action", get_args(Recommendation.model_fields["primary_action"].annotation)
)
def test_recommendation_labels_present_actual_actions_without_rewriting_text(
    tmp_path: Path, action
):
    service = StubApplicationService()
    recommendation = service.result.recommendation
    recommendation.primary_action = action
    recommendation.additional_actions = ["request_better_quality_source", "verify_source"]
    recommendation.text = "Оригинальная рекомендация без перевода."
    before = service.result.model_dump_json()
    response = _client(tmp_path, service).get("/analyses/id/result?lang=en", auth=AUTH)
    assert recommendation.text in response.text
    assert translate("en", "action." + action) in response.text
    assert response.text.index("Request a better-quality source") < response.text.index(
        "Verify the source</li>"
    )
    assert service.result.model_dump_json() == before


def test_missing_original_name_and_empty_metrics_are_honest(tmp_path: Path):
    service = StubApplicationService()
    service.result.file.original_name = ""
    service.result.analyzers = [_result("analyzer")]
    response = _client(tmp_path, service).get("/analyses/id/result?lang=en", auth=AUTH)
    assert "Filename was not recorded" in response.text
    assert "Structured measurements were not recorded" in response.text
    assert "File information was not recorded" not in response.text
