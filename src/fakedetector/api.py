"""Asynchronous job-style HTTP API adapter."""

from __future__ import annotations

import json
from contextlib import suppress
from datetime import datetime
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, FastAPI, Request, Security
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, ConfigDict, ValidationError
from python_multipart.exceptions import MultipartParseError
from starlette.concurrency import run_in_threadpool
from starlette.datastructures import FormData, UploadFile
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.responses import Response

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
from fakedetector.auth import APIBearerAuthenticator
from fakedetector.domain import (
    AnalysisResult,
    AnalysisStatus,
    ErrorDetail,
    ProcessingStage,
    SourceChannel,
    SourceContext,
)

_BEARER_SCHEME = HTTPBearer(
    auto_error=False,
    scheme_name="BearerAuth",
    description="Статический Bearer-токен FakeDetector из переменной окружения.",
)


class AnalysisSubmissionResponse(BaseModel):
    """Factual state returned after an accepted asynchronous submission."""

    model_config = ConfigDict(extra="forbid")

    analysis_id: str
    status: AnalysisStatus
    stage: ProcessingStage
    status_url: str
    result_url: str


class AnalysisStatusResponse(BaseModel):
    """Factual live or persisted analysis status."""

    model_config = ConfigDict(extra="forbid")

    analysis_id: str
    status: AnalysisStatus
    stage: ProcessingStage
    created_at: datetime
    queued_at: datetime | None
    started_at: datetime | None
    finished_at: datetime | None
    result_available: bool
    errors: list[ErrorDetail]


class APIErrorResponse(BaseModel):
    """Canonical safe API error envelope."""

    model_config = ConfigDict(extra="forbid")

    error: ErrorDetail
    request_id: str
    analysis_id: str | None = None
    status_url: str | None = None
    result_url: str | None = None


class APIAuthenticationError(Exception):
    """Internal control signal for a safe Bearer authentication response."""

    def __init__(self, *, missing: bool) -> None:
        self.code = "authentication_required" if missing else "authentication_failed"
        super().__init__("Bearer authentication failed.")


def install_api(
    app: FastAPI,
    *,
    service: AnalysisApplicationService,
    authenticator: APIBearerAuthenticator | None,
) -> None:
    """Install exactly the three Stage 8 MVP API routes."""

    async def require_bearer(
        request: Request,
        credentials: Annotated[
            HTTPAuthorizationCredentials | None,
            Security(_BEARER_SCHEME),
        ],
    ) -> None:
        if authenticator is None:
            return
        token = None if credentials is None else credentials.credentials
        if credentials is None:
            raise APIAuthenticationError(missing="authorization" not in request.headers)
        if credentials.scheme.lower() != "bearer" or not authenticator.verify(token):
            raise APIAuthenticationError(missing=False)

    dependencies = [Security(require_bearer)] if authenticator is not None else []
    router = APIRouter(prefix="/api/v1", tags=["analyses"], dependencies=dependencies)

    @router.post(
        "/analyses",
        status_code=202,
        response_model=AnalysisSubmissionResponse,
        responses={
            400: {"model": APIErrorResponse},
            401: {"model": APIErrorResponse},
            413: {"model": APIErrorResponse},
            415: {"model": APIErrorResponse},
            422: {"model": APIErrorResponse},
            500: {"model": APIErrorResponse},
            503: {"model": APIErrorResponse},
        },
        openapi_extra={
            "requestBody": {
                "required": True,
                "content": {
                    "multipart/form-data": {
                        "schema": {
                            "type": "object",
                            "required": ["file"],
                            "properties": {
                                "file": {"type": "string", "format": "binary"},
                                "source_context": {"type": "string"},
                            },
                        }
                    }
                },
            }
        },
    )
    async def submit_analysis(request: Request) -> Response:
        form: FormData | None = None
        try:
            try:
                form = await request.form()
            except (StarletteHTTPException, MultipartParseError):
                return _error_response(request, 400, _malformed_multipart_error())
            except Exception:
                return _error_response(request, 500, _internal_error())

            file_value = form.get("file")
            if not isinstance(file_value, UploadFile):
                return _error_response(request, 400, _file_missing_error())
            file = file_value
            source_context_value = form.get("source_context")
            if source_context_value is not None and not isinstance(
                source_context_value,
                str,
            ):
                return _error_response(request, 422, _invalid_source_error())

            try:
                upload_is_empty = _upload_is_empty(file)
            except Exception:
                return _error_response(request, 500, _internal_error())
            if upload_is_empty:
                return _error_response(request, 400, _file_empty_error())
            try:
                source = _parse_api_source_context(source_context_value)
            except json.JSONDecodeError:
                return _error_response(request, 400, _malformed_source_error())
            except (ValidationError, ValueError):
                return _error_response(request, 422, _invalid_source_error())

            try:
                submission = await run_in_threadpool(
                    service.submit,
                    file.file,
                    original_name=file.filename or "",
                    declared_content_type=file.content_type,
                    source=source,
                )
            except AnalysisPersistenceUnavailableError:
                return _error_response(request, 503, _result_write_error())
            except AnalysisSubmissionError:
                return _error_response(request, 500, _internal_error())
            except (AnalysisInternalError, AnalysisStorageError):
                return _error_response(request, 500, _internal_error())
            except Exception:
                return _error_response(request, 500, _internal_error())
            return _submission_response(request, submission)
        finally:
            if form is not None:
                with suppress(Exception):
                    await form.close()

    @router.get(
        "/analyses/{analysis_id}",
        response_model=AnalysisStatusResponse,
        responses={
            401: {"model": APIErrorResponse},
            404: {"model": APIErrorResponse},
            500: {"model": APIErrorResponse},
        },
    )
    async def get_analysis_status(request: Request, analysis_id: str) -> Response:
        try:
            status = await run_in_threadpool(service.get_status, analysis_id)
        except AnalysisNotFoundError:
            return _error_response(request, 404, _not_found_error())
        except (AnalysisStorageError, AnalysisInternalError):
            return _error_response(request, 500, _internal_error())
        except Exception:
            return _error_response(request, 500, _internal_error())
        return _status_response(status)

    @router.get(
        "/analyses/{analysis_id}/result",
        response_model=AnalysisResult,
        responses={
            202: {"model": AnalysisStatusResponse},
            401: {"model": APIErrorResponse},
            404: {"model": APIErrorResponse},
            500: {"model": APIErrorResponse},
            503: {"model": APIErrorResponse},
        },
    )
    async def get_analysis_result(request: Request, analysis_id: str) -> Response:
        try:
            result = await run_in_threadpool(service.get_result, analysis_id)
        except AnalysisPendingError as error:
            return _status_response(error.status, status_code=202)
        except AnalysisNotFoundError:
            return _error_response(request, 404, _not_found_error())
        except AnalysisPersistenceUnavailableError:
            return _error_response(request, 503, _result_write_error())
        except (AnalysisStorageError, AnalysisInternalError):
            return _error_response(request, 500, _internal_error())
        except Exception:
            return _error_response(request, 500, _internal_error())
        return JSONResponse(
            status_code=200,
            content=result.model_dump(mode="json", warnings="error"),
        )

    async def authentication_error_handler(
        request: Request,
        error: Exception,
    ) -> Response:
        code = (
            error.code
            if isinstance(error, APIAuthenticationError)
            else "authentication_failed"
        )
        return _error_response(
            request,
            401,
            ErrorDetail(
                code=code,
                category="authentication",
                message="Требуется действительный Bearer-токен.",
                retryable=False,
            ),
            headers={"WWW-Authenticate": "Bearer"},
        )

    app.add_exception_handler(APIAuthenticationError, authentication_error_handler)
    app.include_router(router)


def _parse_api_source_context(value: str | None) -> SourceContext:
    if value is None:
        return SourceContext(channel=SourceChannel.API)
    payload = json.loads(value)
    if not isinstance(payload, dict):
        raise ValueError("source context must be an object")
    source = SourceContext.model_validate(payload)
    if source.channel is not SourceChannel.API:
        raise ValueError("source context channel must be api")
    return source


def _upload_is_empty(upload: UploadFile) -> bool:
    if upload.size is not None:
        return upload.size == 0
    position = upload.file.tell()
    try:
        return not upload.file.read(1)
    finally:
        upload.file.seek(position)


def _submission_response(request: Request, submission: AnalysisSubmission) -> Response:
    status_url, result_url = _analysis_urls(submission.analysis_id)
    if submission.terminal_result is None:
        response = AnalysisSubmissionResponse(
            analysis_id=submission.analysis_id,
            status=submission.status,
            stage=submission.stage,
            status_url=status_url,
            result_url=result_url,
        )
        return JSONResponse(status_code=202, content=response.model_dump(mode="json"))

    result = submission.terminal_result
    error = result.errors[0] if result.errors else _internal_error()
    status_code = stage3_http_status(result.status, error.code)
    return _error_response(
        request,
        status_code,
        error,
        analysis_id=result.analysis_id,
        status_url=status_url,
        result_url=result_url,
    )


def _status_response(status: AnalysisStatusView, *, status_code: int = 200) -> Response:
    response = AnalysisStatusResponse(
        analysis_id=status.analysis_id,
        status=status.status,
        stage=status.stage,
        created_at=status.created_at,
        queued_at=status.queued_at,
        started_at=status.started_at,
        finished_at=status.finished_at,
        result_available=status.result_available,
        errors=[error.model_copy(deep=True) for error in status.errors],
    )
    return JSONResponse(status_code=status_code, content=response.model_dump(mode="json"))


def _error_response(
    _request: Request,
    status_code: int,
    error: ErrorDetail,
    *,
    analysis_id: str | None = None,
    status_url: str | None = None,
    result_url: str | None = None,
    headers: dict[str, str] | None = None,
) -> Response:
    response = APIErrorResponse(
        error=error,
        request_id=f"req_{uuid4().hex}",
        analysis_id=analysis_id,
        status_url=status_url,
        result_url=result_url,
    )
    return JSONResponse(
        status_code=status_code,
        content=response.model_dump(mode="json", exclude_none=True),
        headers=headers,
    )


def _analysis_urls(analysis_id: str) -> tuple[str, str]:
    status_url = f"/api/v1/analyses/{analysis_id}"
    return status_url, f"{status_url}/result"


def stage3_http_status(status: AnalysisStatus, error_code: str) -> int:
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


def _file_missing_error() -> ErrorDetail:
    return ErrorDetail(
        code="file_missing",
        category="validation",
        message="Файл не передан.",
        retryable=False,
        field="file",
    )


def _malformed_multipart_error() -> ErrorDetail:
    return ErrorDetail(
        code="invalid_multipart",
        category="validation",
        message="Тело multipart/form-data не удалось безопасно разобрать.",
        retryable=False,
    )


def _file_empty_error() -> ErrorDetail:
    return ErrorDetail(
        code="file_empty",
        category="validation",
        message="Передан пустой файл.",
        retryable=False,
        field="file",
    )


def _malformed_source_error() -> ErrorDetail:
    return ErrorDetail(
        code="invalid_source_context_json",
        category="validation",
        message="Поле source_context должно содержать корректный JSON-объект.",
        retryable=False,
        field="source_context",
    )


def _invalid_source_error() -> ErrorDetail:
    return ErrorDetail(
        code="invalid_source_context",
        category="validation",
        message="Поле source_context не соответствует контракту API.",
        retryable=False,
        field="source_context",
    )


def _not_found_error() -> ErrorDetail:
    return ErrorDetail(
        code="result_not_found",
        category="storage",
        message="Анализ не найден.",
        retryable=False,
    )


def _result_write_error() -> ErrorDetail:
    return ErrorDetail(
        code="result_write_failed",
        category="storage",
        message="Итоговый результат анализа недоступен из-за ошибки сохранения.",
        retryable=True,
    )


def _internal_error() -> ErrorDetail:
    return ErrorDetail(
        code="internal_error",
        category="internal",
        message="Внутренняя ошибка не позволила выполнить запрос.",
        retryable=True,
    )
