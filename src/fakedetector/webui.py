"""Server-rendered WebUI adapter for the shared analysis application service."""

from __future__ import annotations

from base64 import b64decode
from binascii import Error as Base64DecodeError
from contextlib import suppress
from functools import partial
from pathlib import Path
from urllib.parse import SplitResult, urlsplit

from fastapi import APIRouter, FastAPI, Request, Security
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from python_multipart.exceptions import MultipartParseError
from starlette.concurrency import run_in_threadpool
from starlette.datastructures import FormData, UploadFile
from starlette.formparsers import MultiPartException
from starlette.responses import Response

from fakedetector._http_status import intake_http_status
from fakedetector._http_upload import (
    RequestBodyDeadlineError,
    RequestBodyTooLargeError,
    multipart_body_limit_bytes,
    parse_bounded_multipart,
)
from fakedetector._webui_i18n import error_copy, translate
from fakedetector._webui_presentation import (
    Page,
    analyzer_metadata,
    duration,
    file_size,
    localization_text,
    measurement_labels,
    non_scoring,
    number,
    page_url,
    quantity,
    time_display,
    time_iso,
)
from fakedetector.application import (
    AnalysisApplicationService,
    AnalysisInternalError,
    AnalysisNotFoundError,
    AnalysisPendingError,
    AnalysisPersistenceUnavailableError,
    AnalysisStatusView,
    AnalysisStorageError,
    AnalysisSubmission,
    AnalysisSubmissionError,
)
from fakedetector.auth import WebUIBasicAuthenticator
from fakedetector.config.models import AppConfig
from fakedetector.domain import ErrorDetail, SourceChannel, SourceContext

_PACKAGE_ROOT = Path(__file__).resolve().parent


class WebUIAuthenticationError(Exception):
    """Internal control signal for an HTTP Basic challenge page."""

    def __init__(self, *, missing: bool) -> None:
        self.code = "authentication_required" if missing else "authentication_failed"
        super().__init__("HTTP Basic authentication failed.")


def install_webui(
    app: FastAPI,
    *,
    service: AnalysisApplicationService,
    authenticator: WebUIBasicAuthenticator | None,
    config: AppConfig,
) -> None:
    """Install authenticated HTML routes and package-relative static resources."""
    templates = Jinja2Templates(
        directory=str(_PACKAGE_ROOT / "templates"),
        context_processors=[_page_context],
    )
    app.mount("/static", StaticFiles(directory=_PACKAGE_ROOT / "static"), name="static")

    async def require_basic(
        request: Request,
    ) -> None:
        if authenticator is None:
            return
        authorization = request.headers.get("authorization")
        if authorization is None:
            raise WebUIAuthenticationError(missing=True)
        username, password = _strict_basic_credentials(authorization)
        if not authenticator.verify(username, password):
            raise WebUIAuthenticationError(missing=False)

    dependencies = [Security(require_basic)] if authenticator is not None else []
    router = APIRouter(dependencies=dependencies)
    upload_context = _upload_context(config)
    body_limit_bytes = multipart_body_limit_bytes(config)
    request_timeout_seconds = config.server.request_timeout_seconds

    @router.get("/", include_in_schema=False)
    async def upload_page(request: Request) -> Response:
        return templates.TemplateResponse(
            request=request,
            name="upload.html",
            context=upload_context,
        )

    @router.post("/analyses", include_in_schema=False)
    async def submit_analysis(request: Request) -> Response:
        if not is_same_origin(request):
            return _error_page(
                templates,
                request,
                status_code=403,
                error=ErrorDetail(
                    code="same_origin_required",
                    category="authorization",
                    message="Отправка разрешена только со страницы FakeDetector.",
                    retryable=False,
                ),
            )
        form: FormData | None = None
        try:
            try:
                form = await parse_bounded_multipart(
                    request,
                    body_limit_bytes=body_limit_bytes,
                    timeout_seconds=request_timeout_seconds,
                    max_files=2,
                    max_fields=1,
                )
            except RequestBodyTooLargeError:
                return _error_page(
                    templates,
                    request,
                    status_code=413,
                    error=ErrorDetail(
                        code="file_too_large",
                        category="resource_limit",
                        message="Размер тела запроса превышает допустимый предел.",
                        retryable=False,
                        field="file",
                        safe_details={"max_size_bytes": body_limit_bytes},
                    ),
                )
            except RequestBodyDeadlineError:
                return _malformed_form_page(templates, request)
            except (MultiPartException, MultipartParseError):
                return _malformed_form_page(templates, request)
            except Exception:
                return _internal_error_page(templates, request)

            items = form.multi_items()
            if any(name != "file" for name, _value in items):
                return _invalid_form_structure_page(templates, request)
            file_values = [value for name, value in items if name == "file"]
            if not file_values:
                return _error_page(
                    templates,
                    request,
                    status_code=400,
                    error=ErrorDetail(
                        code="file_missing",
                        category="validation",
                        message="Файл не передан.",
                        retryable=False,
                        field="file",
                    ),
                )
            if len(file_values) != 1 or not isinstance(file_values[0], UploadFile):
                return _invalid_form_structure_page(templates, request)
            file = file_values[0]
            try:
                upload_is_empty = file.size == 0
            except Exception:
                return _internal_error_page(templates, request)
            if upload_is_empty:
                return _error_page(
                    templates,
                    request,
                    status_code=400,
                    error=ErrorDetail(
                        code="file_empty",
                        category="validation",
                        message="Передан пустой файл.",
                        retryable=False,
                        field="file",
                    ),
                )
            try:
                submission = await run_in_threadpool(
                    service.submit,
                    file.file,
                    original_name=file.filename or "",
                    declared_content_type=file.content_type,
                    source=SourceContext(channel=SourceChannel.WEBUI),
                )
            except AnalysisPersistenceUnavailableError:
                return _persistence_error_page(templates, request)
            except (AnalysisSubmissionError, AnalysisInternalError, AnalysisStorageError):
                return _internal_error_page(templates, request)
            except Exception:
                return _internal_error_page(templates, request)
            return _submission_response(templates, request, submission)
        finally:
            if form is not None:
                with suppress(Exception):
                    await form.close()

    @router.get("/analyses/{analysis_id}", include_in_schema=False)
    async def analysis_status(request: Request, analysis_id: str) -> Response:
        try:
            status = await run_in_threadpool(service.get_status, analysis_id)
        except AnalysisNotFoundError:
            return _not_found_page(templates, request)
        except (AnalysisStorageError, AnalysisInternalError):
            return _internal_error_page(templates, request)
        except Exception:
            return _internal_error_page(templates, request)
        if status.persistence_failed:
            return _persistence_error_page(templates, request)
        if status.result_available:
            return RedirectResponse(
                url=page_url(
                    "result",
                    _request_locale(request),
                    analysis_id=status.analysis_id,
                    paused=_refresh_paused(request),
                ),
                status_code=303,
            )
        return _status_page(
            templates,
            request,
            status,
            status_code=200,
            refresh_page="status",
        )

    @router.get("/analyses/{analysis_id}/result", include_in_schema=False)
    async def analysis_result(request: Request, analysis_id: str) -> Response:
        try:
            result = await run_in_threadpool(service.get_result, analysis_id)
        except AnalysisPendingError as error:
            return _status_page(
                templates,
                request,
                error.status,
                status_code=202,
                refresh_page="result",
            )
        except AnalysisNotFoundError:
            return _not_found_page(templates, request)
        except AnalysisPersistenceUnavailableError:
            return _persistence_error_page(templates, request)
        except (AnalysisStorageError, AnalysisInternalError):
            return _internal_error_page(templates, request)
        except Exception:
            return _internal_error_page(templates, request)
        return templates.TemplateResponse(
            request=request,
            name="result.html",
            context={"result": result},
        )

    async def authentication_error_handler(
        request: Request,
        error: Exception,
    ) -> Response:
        code = (
            error.code
            if isinstance(error, WebUIAuthenticationError)
            else "authentication_failed"
        )
        return templates.TemplateResponse(
            request=request,
            name="error.html",
            context={
                "status_code": 401,
                "error": ErrorDetail(
                    code=code,
                    category="authentication",
                    message="Требуются действительные учётные данные HTTP Basic.",
                    retryable=False,
                ),
                "analysis_id": None,
                "status_url": None,
                "result_url": None,
            },
            status_code=401,
            headers={"WWW-Authenticate": 'Basic realm="FakeDetector"'},
        )

    app.add_exception_handler(WebUIAuthenticationError, authentication_error_handler)
    app.include_router(router)


def is_same_origin(request: Request) -> bool:
    """Require one valid same-origin Origin, or Referer when Origin is absent."""
    origins = request.headers.getlist("origin")
    if origins:
        return len(origins) == 1 and _matches_request_origin(
            origins[0],
            request,
            origin_header=True,
        )
    referers = request.headers.getlist("referer")
    return len(referers) == 1 and _matches_request_origin(
        referers[0],
        request,
        origin_header=False,
    )


def _matches_request_origin(value: str, request: Request, *, origin_header: bool) -> bool:
    if not value or value == "null" or _contains_ascii_control_character(value):
        return False
    try:
        supplied = urlsplit(value)
        expected = urlsplit(str(request.url))
        supplied_origin = _normalized_origin(supplied)
        expected_origin = _normalized_origin(expected)
        if origin_header and (supplied.path or supplied.query or supplied.fragment):
            return False
    except (TypeError, ValueError):
        return False
    return supplied_origin == expected_origin


def _strict_basic_credentials(authorization: str) -> tuple[str, str]:
    scheme, separator, encoded = authorization.partition(" ")
    if scheme.lower() != "basic" or not separator or not encoded:
        raise WebUIAuthenticationError(missing=False)
    try:
        decoded = b64decode(encoded, validate=True).decode("ascii")
    except (Base64DecodeError, UnicodeDecodeError, ValueError):
        raise WebUIAuthenticationError(missing=False) from None
    username, separator, password = decoded.partition(":")
    if not separator:
        raise WebUIAuthenticationError(missing=False)
    return username, password


def _contains_ascii_control_character(value: str) -> bool:
    return any(ord(character) <= 0x1F or ord(character) == 0x7F for character in value)


def _normalized_origin(parts: SplitResult) -> tuple[str, str, int] | None:
    scheme = parts.scheme.lower()
    if scheme not in {"http", "https"} or not parts.netloc:
        return None
    if parts.username is not None or parts.password is not None or parts.hostname is None:
        return None
    port = parts.port
    if port is None:
        port = 443 if scheme == "https" else 80
    return scheme, parts.hostname.lower(), port


def _upload_context(config: AppConfig) -> dict[str, object]:
    return {
        "formats": {
            "image": tuple(config.allowed_formats.image.extensions),
            "audio": tuple(config.allowed_formats.audio.extensions),
            "video": tuple(config.allowed_formats.video.extensions),
        },
        "limits": {
            "image": config.limits.max_file_size_mb.image,
            "audio": config.limits.max_file_size_mb.audio,
            "video": config.limits.max_file_size_mb.video,
        },
    }


def _submission_response(
    templates: Jinja2Templates,
    request: Request,
    submission: AnalysisSubmission,
) -> Response:
    if submission.terminal_result is None:
        return RedirectResponse(
            url=page_url(
                "status",
                _request_locale(request),
                analysis_id=submission.analysis_id,
                paused=_refresh_paused(request),
            ),
            status_code=303,
        )
    result = submission.terminal_result
    error = (
        result.errors[0]
        if result.errors
        else ErrorDetail(
            code="internal_error",
            category="internal",
            message="Анализ завершился внутренней ошибкой.",
            retryable=True,
        )
    )
    return _error_page(
        templates,
        request,
        status_code=intake_http_status(result.status, error.code),
        error=error,
        analysis_id=result.analysis_id,
        status_url=page_url("status", _request_locale(request), analysis_id=result.analysis_id),
        result_url=page_url("result", _request_locale(request), analysis_id=result.analysis_id),
    )


def _status_page(
    templates: Jinja2Templates,
    request: Request,
    status: AnalysisStatusView,
    *,
    status_code: int,
    refresh_page: Page,
) -> Response:
    return templates.TemplateResponse(
        request=request,
        name="status.html",
        context={
            "status": status,
            "refresh_url": page_url(
                refresh_page,
                _request_locale(request),
                analysis_id=status.analysis_id,
                paused=_refresh_paused(request),
            ),
            "pause_url": page_url(
                refresh_page,
                _request_locale(request),
                analysis_id=status.analysis_id,
                paused=True,
            ),
            "resume_url": page_url(
                refresh_page,
                _request_locale(request),
                analysis_id=status.analysis_id,
            ),
        },
        status_code=status_code,
    )


def _not_found_page(templates: Jinja2Templates, request: Request) -> Response:
    return _error_page(
        templates,
        request,
        status_code=404,
        error=ErrorDetail(
            code="result_not_found",
            category="storage",
            message="Анализ не найден.",
            retryable=False,
        ),
    )


def _persistence_error_page(templates: Jinja2Templates, request: Request) -> Response:
    return _error_page(
        templates,
        request,
        status_code=503,
        error=ErrorDetail(
            code="result_write_failed",
            category="storage",
            message="Итоговый результат анализа недоступен из-за ошибки сохранения.",
            retryable=True,
        ),
    )


def _malformed_form_page(templates: Jinja2Templates, request: Request) -> Response:
    return _error_page(
        templates,
        request,
        status_code=400,
        error=ErrorDetail(
            code="invalid_multipart",
            category="validation",
            message="Форму загрузки не удалось безопасно разобрать.",
            retryable=False,
        ),
    )


def _invalid_form_structure_page(
    templates: Jinja2Templates,
    request: Request,
) -> Response:
    return _error_page(
        templates,
        request,
        status_code=400,
        error=ErrorDetail(
            code="invalid_multipart",
            category="validation",
            message="Структура формы загрузки не соответствует контракту WebUI.",
            retryable=False,
        ),
    )


def _internal_error_page(templates: Jinja2Templates, request: Request) -> Response:
    return _error_page(
        templates,
        request,
        status_code=500,
        error=ErrorDetail(
            code="internal_error",
            category="internal",
            message="Внутренняя ошибка не позволила выполнить запрос.",
            retryable=True,
        ),
    )


def _error_page(
    templates: Jinja2Templates,
    request: Request,
    *,
    status_code: int,
    error: ErrorDetail,
    analysis_id: str | None = None,
    status_url: str | None = None,
    result_url: str | None = None,
) -> Response:
    return templates.TemplateResponse(
        request=request,
        name="error.html",
        context={
            "status_code": status_code,
            "error": error,
            "analysis_id": analysis_id,
            "status_url": status_url,
            "result_url": result_url,
        },
        status_code=status_code,
    )


def _request_locale(request: Request) -> str:
    values = request.query_params.getlist("lang")
    return values[0] if len(values) == 1 and values[0] in {"ru", "en"} else "ru"


def _refresh_paused(request: Request) -> bool:
    return request.query_params.getlist("refresh") == ["off"]


def _page_context(request: Request) -> dict[str, object]:
    """Supply presentation helpers to every HTML response, including guard failures."""
    locale = _request_locale(request)
    paused = _refresh_paused(request)
    routes: dict[str, Page] = {
        "analysis_status": "status",
        "analysis_result": "result",
    }
    route_name = getattr(request.scope.get("route"), "name", "")
    current_page = routes.get(route_name, "upload") if request.method == "GET" else "upload"
    analysis_id = str(request.path_params.get("analysis_id", ""))
    language_links = tuple(
        (
            language,
            translate(locale, "error.post_language_" + language)
            if request.method == "POST"
            else label,
            page_url(current_page, language, analysis_id=analysis_id, paused=paused),
        )
        for language, label in (("ru", "Русский"), ("en", "English"))
    )
    return {
        "locale": locale,
        "t": partial(translate, locale),
        "error_copy": partial(error_copy, locale),
        "url": partial(page_url, locale=locale, analysis_id=analysis_id, paused=paused),
        "language_links": language_links,
        "refresh_paused": paused,
        "number": number,
        "quantity": partial(quantity, locale),
        "time_display": partial(time_display, locale),
        "time_iso": time_iso,
        "file_size": partial(file_size, locale),
        "duration": partial(duration, locale),
        "localization_text": partial(localization_text, locale),
        "analyzer_metadata": analyzer_metadata,
        "non_scoring": non_scoring,
        "measurement_labels": measurement_labels,
    }
