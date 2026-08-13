"""Primary validation of one controlled Stage 3 source."""

from __future__ import annotations

import re
import warnings
from collections.abc import Callable
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO, Literal, TypeVar

from PIL import Image, UnidentifiedImageError
from pydantic import JsonValue

from fakedetector.config.models import AppConfig
from fakedetector.domain import (
    AudioTechnicalParameters,
    ErrorDetail,
    ImageTechnicalParameters,
    MediaType,
    ValidatedFileDescriptor,
    ValidationCheck,
    ValidationResult,
    VideoTechnicalParameters,
)
from fakedetector.intake.media_tools import (
    FFmpegMediaInspector,
    MediaRejectedError,
    MediaToolSystemError,
    ProbeResult,
    audio_parameters,
    video_parameters,
)
from fakedetector.intake.service import ControlledInput
from fakedetector.intake.temporary_input import IntakeSystemError, LocalTemporaryInputOwner

_HEADER_LIMIT_BYTES = 64 * 1024
_BYTES_PER_MEBIBYTE = 1024 * 1024
_EBML_HEADER_ID = 0x1A45DFA3
_EBML_DOCUMENT_TYPE_ID = 0x4282
_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_MIME_PATTERN = re.compile(r"^[!#$%&'*+.^_`|~0-9a-z-]+/[!#$%&'*+.^_`|~0-9a-z-]+$")
_PathResult = TypeVar("_PathResult")
_ErrorCategory = Literal["validation", "unsupported_media", "resource_limit"]


class ValidationSystemError(Exception):
    """Safe internal failure that Increment 3 will classify as terminal failed."""

    def __init__(self, phase: str) -> None:
        super().__init__("Primary validation failed internally.")
        self.phase = phase


@dataclass(frozen=True, slots=True)
class _DetectedFormat:
    extension: str
    detected_mime: str
    media_type: MediaType
    container: str


@dataclass(frozen=True, slots=True)
class _HeaderCandidate:
    kind: str
    document_type: str | None = None
    brands: frozenset[bytes] = frozenset()


_FORMAT_BY_EXTENSION = {
    "jpg": _DetectedFormat("jpg", "image/jpeg", MediaType.IMAGE, "jpeg"),
    "jpeg": _DetectedFormat("jpeg", "image/jpeg", MediaType.IMAGE, "jpeg"),
    "png": _DetectedFormat("png", "image/png", MediaType.IMAGE, "png"),
    "webp": _DetectedFormat("webp", "image/webp", MediaType.IMAGE, "webp"),
    "wav": _DetectedFormat("wav", "audio/wav", MediaType.AUDIO, "wav"),
    "mp3": _DetectedFormat("mp3", "audio/mpeg", MediaType.AUDIO, "mp3"),
    "flac": _DetectedFormat("flac", "audio/flac", MediaType.AUDIO, "flac"),
    "m4a": _DetectedFormat("m4a", "audio/mp4", MediaType.AUDIO, "m4a"),
    "mp4": _DetectedFormat("mp4", "video/mp4", MediaType.VIDEO, "mp4"),
    "mov": _DetectedFormat("mov", "video/quicktime", MediaType.VIDEO, "mov"),
    "avi": _DetectedFormat("avi", "video/x-msvideo", MediaType.VIDEO, "avi"),
    "mkv": _DetectedFormat("mkv", "video/x-matroska", MediaType.VIDEO, "mkv"),
}
_ALLOWED_EXTENSIONS = frozenset(_FORMAT_BY_EXTENSION)
_ALLOWED_MIME_TYPES = frozenset(item.detected_mime for item in _FORMAT_BY_EXTENSION.values())


class FileValidator:
    """Validate controlled media without taking ownership of its lifetime."""

    def __init__(
        self,
        *,
        config: AppConfig,
        temporary_input_owner: LocalTemporaryInputOwner,
        media_inspector: FFmpegMediaInspector | None = None,
    ) -> None:
        self._owner = temporary_input_owner
        self._limits = config.limits.max_file_size_mb
        self._media_inspector = media_inspector or FFmpegMediaInspector(
            timeout_seconds=min(15.0, float(config.limits.processing_timeout_seconds))
        )

    def validate(self, controlled_input: ControlledInput) -> ValidationResult:
        """Return a canonical success/rejection or raise a safe system failure."""
        self._validate_internal_invariants(controlled_input)
        checks: list[ValidationCheck] = []

        if controlled_input.input_file.size_bytes == 0:
            return _rejection(
                checks,
                "file_not_empty",
                "Файл пуст.",
                code="file_empty",
                category="validation",
            )
        checks.append(_passed("file_not_empty", "Файл содержит данные."))

        extension = _extract_extension(controlled_input.input_file.original_name)
        if extension is None:
            return _rejection(
                checks,
                "extension_present",
                "В имени файла отсутствует обязательное расширение.",
                code="missing_extension",
                category="unsupported_media",
            )
        checks.append(_passed("extension_present", "Расширение файла определено."))

        if extension not in _ALLOWED_EXTENSIONS:
            return _rejection(
                checks,
                "extension_allowed",
                "Расширение файла не поддерживается.",
                code="unsupported_extension",
                category="unsupported_media",
            )
        checks.append(_passed("extension_allowed", "Расширение файла поддерживается."))

        candidate = self._read_candidate(controlled_input)
        if candidate is None or candidate.document_type == "webm":
            return _rejection(
                checks,
                "file_signature_valid",
                "Фактический формат файла не поддерживается.",
                code="unsupported_mime_type",
                category="unsupported_media",
            )

        probe: ProbeResult | None = None
        try:
            if candidate.kind in {"wav", "mp3", "flac", "avi", "matroska", "isobmff"}:
                probe = self._with_path(controlled_input, self._media_inspector.probe)
            detected = _resolve_detected_format(candidate, probe)
        except MediaRejectedError:
            return _unreadable_rejection(checks, "file_signature_valid")
        except MediaToolSystemError as error:
            raise ValidationSystemError(error.phase) from None

        if detected is None:
            return _rejection(
                checks,
                "file_signature_valid",
                "Фактический формат файла не поддерживается.",
                code="unsupported_mime_type",
                category="unsupported_media",
            )
        checks.append(_passed("file_signature_valid", "Сигнатура и контейнер распознаны."))
        checks.append(_passed("detected_mime_allowed", "Обнаруженный MIME-тип поддерживается."))
        checks.append(_passed("media_type_supported", "Группа медиа поддерживается."))

        expected = _FORMAT_BY_EXTENSION[extension]
        if expected.detected_mime != detected.detected_mime:
            return _rejection(
                checks,
                "type_consistent",
                "Расширение файла не соответствует фактическому формату.",
                code="file_signature_mismatch",
                category="validation",
                safe_details={"detected_mime_type": detected.detected_mime},
            )
        checks.append(_passed("type_consistent", "Типы файла согласованы."))

        declared = controlled_input.input_file.declared_content_type
        normalized_declared: str | None = None
        if declared is not None:
            normalized_declared = _normalize_declared_mime(declared)
            if normalized_declared != detected.detected_mime:
                return _rejection(
                    checks,
                    "declared_mime_consistent",
                    "Заявленный MIME-тип не соответствует фактическому типу файла.",
                    code="file_signature_mismatch",
                    category="validation",
                    safe_details={"detected_mime_type": detected.detected_mime},
                )
            checks.append(
                _passed("declared_mime_consistent", "Заявленный MIME-тип согласован.")
            )

        limit_bytes = self._media_limit_bytes(detected.media_type)
        if controlled_input.input_file.size_bytes > limit_bytes:
            return _rejection(
                checks,
                "file_size_allowed",
                "Размер файла превышает допустимый предел для обнаруженного типа.",
                code="file_too_large",
                category="resource_limit",
                safe_details={
                    "max_size_bytes": limit_bytes,
                    "observed_size_bytes": controlled_input.input_file.size_bytes,
                },
            )
        checks.append(_passed("file_size_allowed", "Размер файла соответствует ограничению."))

        try:
            technical_parameters = self._safe_read(
                controlled_input,
                detected,
                probe,
            )
        except MediaRejectedError:
            return _unreadable_rejection(checks, "safe_read_completed")
        except MediaToolSystemError as error:
            raise ValidationSystemError(error.phase) from None
        except IntakeSystemError as error:
            raise ValidationSystemError(error.phase) from None

        checks.append(_passed("safe_read_completed", "Файл безопасно прочитан."))
        checks.append(
            _passed("technical_parameters_available", "Технические параметры получены.")
        )
        checks.append(_passed("sha256_available", "SHA-256 получен из controlled intake."))
        descriptor = ValidatedFileDescriptor(
            original_name=controlled_input.input_file.original_name,
            extension=extension,
            declared_mime_type=normalized_declared,
            detected_mime_type=detected.detected_mime,
            media_type=detected.media_type,
            size_bytes=controlled_input.input_file.size_bytes,
            sha256=controlled_input.sha256,
            signature_match=True,
            safe_read=True,
            technical_parameters=technical_parameters,
        )
        return ValidationResult(
            accepted=True,
            checks=checks,
            errors=[],
            validated_file=descriptor,
        )

    def _validate_internal_invariants(self, controlled_input: ControlledInput) -> None:
        if controlled_input.input_file.size_bytes < 0:
            raise ValidationSystemError("size")
        if not _SHA256_PATTERN.fullmatch(controlled_input.sha256):
            raise ValidationSystemError("sha256")
        if controlled_input.owned_source.analysis_id != controlled_input.analysis_id:
            raise ValidationSystemError("analysis_id")
        try:
            self._owner.with_local_source_path(controlled_input.owned_source, lambda _path: None)
        except IntakeSystemError as error:
            raise ValidationSystemError(error.phase) from None

    def _read_candidate(self, controlled_input: ControlledInput) -> _HeaderCandidate | None:
        try:
            with self._owner.open_for_read(controlled_input.owned_source) as source:
                header = source.read(_HEADER_LIMIT_BYTES)
        except IntakeSystemError as error:
            raise ValidationSystemError(error.phase) from None
        except OSError:
            raise ValidationSystemError("controlled_source_read") from None
        return _classify_header(header)

    def _safe_read(
        self,
        controlled_input: ControlledInput,
        detected: _DetectedFormat,
        probe: ProbeResult | None,
    ) -> ImageTechnicalParameters | AudioTechnicalParameters | VideoTechnicalParameters:
        if detected.media_type is MediaType.IMAGE:
            try:
                with self._owner.open_for_read(controlled_input.owned_source) as source:
                    return _decode_image(source, detected.container)
            except (
                UnidentifiedImageError,
                OSError,
                SyntaxError,
                ValueError,
                Image.DecompressionBombError,
                Image.DecompressionBombWarning,
            ):
                raise MediaRejectedError("image_decode") from None

        if probe is None:
            raise ValidationSystemError("missing_probe")
        if detected.media_type is MediaType.AUDIO:
            audio_probe = audio_parameters(probe)
            self._with_path(controlled_input, self._media_inspector.decode_audio)
            return AudioTechnicalParameters(
                duration_seconds=audio_probe.duration_seconds,
                sample_rate_hz=audio_probe.sample_rate_hz,
                channels=audio_probe.channels,
                codec=audio_probe.codec,
                bitrate_bps=audio_probe.bitrate_bps,
            )

        video_probe = video_parameters(probe)
        self._with_path(
            controlled_input,
            lambda path: self._media_inspector.decode_video(
                path,
                has_audio=video_probe.has_audio,
            ),
        )
        return VideoTechnicalParameters(
            duration_seconds=video_probe.duration_seconds,
            container=detected.container,
            video_codec=video_probe.video_codec,
            audio_codec=video_probe.audio_codec,
            width=video_probe.width,
            height=video_probe.height,
            fps=video_probe.fps,
            bitrate_bps=video_probe.bitrate_bps,
            has_audio=video_probe.has_audio,
        )

    def _with_path(
        self,
        controlled_input: ControlledInput,
        operation: Callable[[Path], _PathResult],
    ) -> _PathResult:
        try:
            return self._owner.with_local_source_path(controlled_input.owned_source, operation)
        except IntakeSystemError as error:
            raise ValidationSystemError(error.phase) from None

    def _media_limit_bytes(self, media_type: MediaType) -> int:
        limit_mebibytes = {
            MediaType.IMAGE: self._limits.image,
            MediaType.AUDIO: self._limits.audio,
            MediaType.VIDEO: self._limits.video,
        }[media_type]
        return limit_mebibytes * _BYTES_PER_MEBIBYTE


def _extract_extension(original_name: str) -> str | None:
    if not original_name or original_name.endswith("."):
        return None
    final_component = original_name.replace("\\", "/").rsplit("/", maxsplit=1)[-1]
    if final_component.startswith(".") and final_component.count(".") == 1:
        return None
    if "." not in final_component:
        return None
    extension = final_component.rsplit(".", maxsplit=1)[1]
    return extension.lower() if extension else None


def _normalize_declared_mime(value: str) -> str | None:
    media_type = value.split(";", maxsplit=1)[0].strip().lower()
    return media_type if _MIME_PATTERN.fullmatch(media_type) else None


def _classify_header(header: bytes) -> _HeaderCandidate | None:
    if header.startswith(b"\xff\xd8\xff"):
        return _HeaderCandidate("jpeg")
    if header.startswith(b"\x89PNG\r\n\x1a\n"):
        return _HeaderCandidate("png")
    if len(header) >= 12 and header[:4] == b"RIFF":
        if header[8:12] == b"WEBP":
            return _HeaderCandidate("webp")
        if header[8:12] == b"WAVE":
            return _HeaderCandidate("wav")
        if header[8:12] == b"AVI ":
            return _HeaderCandidate("avi")
        return None
    if header.startswith(b"fLaC"):
        return _HeaderCandidate("flac")
    if header.startswith(b"\x1aE\xdf\xa3"):
        document_type = _ebml_document_type(header)
        if document_type in {"matroska", "webm"}:
            return _HeaderCandidate("matroska", document_type=document_type)
        return None
    if header.startswith(b"ID3") or _has_mpeg_audio_frame(header):
        return _HeaderCandidate("mp3")
    brands = _iso_bmff_brands(header)
    if brands is not None:
        return _HeaderCandidate("isobmff", brands=brands)
    return None


def _ebml_document_type(header: bytes) -> str | None:
    """Read only the structural DocType from one complete bounded EBML header."""
    header_id = _read_ebml_vint(header, 0, max_length=4, preserve_marker=True)
    if header_id is None or header_id[0] != _EBML_HEADER_ID:
        return None
    header_size = _read_ebml_vint(header, header_id[1], max_length=8, preserve_marker=False)
    if header_size is None:
        return None

    offset = header_id[1] + header_size[1]
    header_end = offset + header_size[0]
    if header_end > len(header):
        return None

    document_type: bytes | None = None
    while offset < header_end:
        element_id = _read_ebml_vint(header, offset, max_length=4, preserve_marker=True)
        if element_id is None:
            return None
        size_offset = offset + element_id[1]
        element_size = _read_ebml_vint(
            header,
            size_offset,
            max_length=8,
            preserve_marker=False,
        )
        if element_size is None:
            return None
        value_start = size_offset + element_size[1]
        value_end = value_start + element_size[0]
        if value_end > header_end:
            return None
        if element_id[0] == _EBML_DOCUMENT_TYPE_ID:
            if document_type is not None:
                return None
            document_type = header[value_start:value_end]
        offset = value_end

    if document_type is None:
        return None
    return {b"matroska": "matroska", b"webm": "webm"}.get(document_type)


def _read_ebml_vint(
    data: bytes,
    offset: int,
    *,
    max_length: int,
    preserve_marker: bool,
) -> tuple[int, int] | None:
    """Read one bounded EBML variable integer without interpreting other elements."""
    if offset >= len(data):
        return None
    first = data[offset]
    marker = 0x80
    length = 1
    while marker and not first & marker:
        marker >>= 1
        length += 1
    if marker == 0 or length > max_length or offset + length > len(data):
        return None

    if preserve_marker:
        return int.from_bytes(data[offset : offset + length], "big"), length

    value = first & (marker - 1)
    for byte in data[offset + 1 : offset + length]:
        value = (value << 8) | byte
    if value == (1 << (7 * length)) - 1:
        return None
    return value, length


def _has_mpeg_audio_frame(header: bytes) -> bool:
    for index in range(max(0, len(header) - 4)):
        first, second = header[index], header[index + 1]
        if first == 0xFF and second & 0xE6 == 0xE2:
            return True
    return False


def _iso_bmff_brands(header: bytes) -> frozenset[bytes] | None:
    offset = 0
    while offset + 8 <= len(header):
        size = int.from_bytes(header[offset : offset + 4], "big")
        box_type = header[offset + 4 : offset + 8]
        header_size = 8
        if size == 1:
            if offset + 16 > len(header):
                return None
            size = int.from_bytes(header[offset + 8 : offset + 16], "big")
            header_size = 16
        if size < header_size:
            return None
        if box_type == b"ftyp":
            end = offset + size
            if end > len(header) or size < header_size + 8:
                return None
            payload = header[offset + header_size : end]
            compatible = {
                payload[index : index + 4]
                for index in range(8, len(payload) - 3, 4)
            }
            return frozenset({payload[:4], *compatible})
        offset += size
    return None


def _resolve_detected_format(
    candidate: _HeaderCandidate,
    probe: ProbeResult | None,
) -> _DetectedFormat | None:
    direct = {
        "jpeg": _FORMAT_BY_EXTENSION["jpg"],
        "png": _FORMAT_BY_EXTENSION["png"],
        "webp": _FORMAT_BY_EXTENSION["webp"],
    }
    if candidate.kind in direct:
        return direct[candidate.kind]
    if probe is None:
        return None
    if candidate.kind == "wav" and "wav" in probe.format_names:
        return _FORMAT_BY_EXTENSION["wav"]
    if candidate.kind == "mp3" and "mp3" in probe.format_names:
        return _FORMAT_BY_EXTENSION["mp3"]
    if candidate.kind == "flac" and "flac" in probe.format_names:
        return _FORMAT_BY_EXTENSION["flac"]
    if candidate.kind == "avi" and "avi" in probe.format_names:
        return _FORMAT_BY_EXTENSION["avi"]
    if candidate.kind == "matroska" and probe.video_streams:
        return _FORMAT_BY_EXTENSION["mkv"]
    if candidate.kind != "isobmff" or not {"mov", "mp4", "m4a"} & probe.format_names:
        return None
    if b"qt  " in candidate.brands and probe.video_streams:
        return _FORMAT_BY_EXTENSION["mov"]
    if probe.video_streams:
        return _FORMAT_BY_EXTENSION["mp4"]
    if probe.audio_streams:
        return _FORMAT_BY_EXTENSION["m4a"]
    return None


def _decode_image(source: BinaryIO, expected_container: str) -> ImageTechnicalParameters:
    expected_format = {"jpeg": "JPEG", "png": "PNG", "webp": "WEBP"}[expected_container]
    with warnings.catch_warnings():
        warnings.simplefilter("error", Image.DecompressionBombWarning)
        with Image.open(source, formats=[expected_format]) as image:
            if image.format != expected_format:
                raise UnidentifiedImageError("unexpected image format")
            width, height = image.size
            color_mode = image.mode
            frame_count = getattr(image, "n_frames", None)
            has_metadata = bool(image.info)
            with suppress(AttributeError, OSError, ValueError):
                has_metadata = has_metadata or bool(image.getexif())
            frames = frame_count if frame_count is not None else 1
            for frame_index in range(frames):
                image.seek(frame_index)
                image.load()
            return ImageTechnicalParameters(
                width=width,
                height=height,
                format=expected_format,
                color_mode=color_mode,
                frame_count=frame_count,
                has_metadata=has_metadata,
            )


def _passed(code: str, message: str) -> ValidationCheck:
    return ValidationCheck(code=code, passed=True, message=message)


def _rejection(
    checks: list[ValidationCheck],
    check_code: str,
    message: str,
    *,
    code: str,
    category: _ErrorCategory,
    safe_details: dict[str, JsonValue] | None = None,
) -> ValidationResult:
    return ValidationResult(
        accepted=False,
        checks=[*checks, ValidationCheck(code=check_code, passed=False, message=message)],
        errors=[
            ErrorDetail(
                code=code,
                category=category,
                message=message,
                retryable=False,
                field="file",
                safe_details=safe_details or {},
            )
        ],
        validated_file=None,
    )


def _unreadable_rejection(checks: list[ValidationCheck], check_code: str) -> ValidationResult:
    return _rejection(
        checks,
        check_code,
        "Файл не удалось безопасно прочитать.",
        code="unsafe_or_unreadable_file",
        category="validation",
    )
