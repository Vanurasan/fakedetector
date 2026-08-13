"""Behavior tests for controlled Stage 3 primary validation."""

from __future__ import annotations

from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image

from fakedetector.config.models import AppConfig
from fakedetector.domain import (
    AudioTechnicalParameters,
    ImageTechnicalParameters,
    InputFileDescriptor,
    MediaType,
    SourceChannel,
    SourceContext,
    VideoTechnicalParameters,
)
from fakedetector.intake import (
    ControlledInput,
    FileValidator,
    LocalTemporaryInputOwner,
    ValidationSystemError,
)
from fakedetector.intake.media_tools import MediaToolSystemError
from fakedetector.intake.validation import _classify_header

_RECEIVED_AT = datetime(2026, 8, 13, tzinfo=UTC)
_MATRIX = [
    ("jpg", "image/jpeg", MediaType.IMAGE, ImageTechnicalParameters),
    ("jpeg", "image/jpeg", MediaType.IMAGE, ImageTechnicalParameters),
    ("png", "image/png", MediaType.IMAGE, ImageTechnicalParameters),
    ("webp", "image/webp", MediaType.IMAGE, ImageTechnicalParameters),
    ("wav", "audio/wav", MediaType.AUDIO, AudioTechnicalParameters),
    ("mp3", "audio/mpeg", MediaType.AUDIO, AudioTechnicalParameters),
    ("flac", "audio/flac", MediaType.AUDIO, AudioTechnicalParameters),
    ("m4a", "audio/mp4", MediaType.AUDIO, AudioTechnicalParameters),
    ("mp4", "video/mp4", MediaType.VIDEO, VideoTechnicalParameters),
    ("mov", "video/quicktime", MediaType.VIDEO, VideoTechnicalParameters),
    ("avi", "video/x-msvideo", MediaType.VIDEO, VideoTechnicalParameters),
    ("mkv", "video/x-matroska", MediaType.VIDEO, VideoTechnicalParameters),
]


def make_config(
    root: Path,
    *,
    image_limit: int = 20,
    audio_limit: int = 50,
    video_limit: int = 200,
) -> AppConfig:
    return AppConfig.model_validate(
        {
            "schema_version": "1.0",
            "server": {},
            "access_channels": {},
            "limits": {
                "max_file_size_mb": {
                    "image": image_limit,
                    "audio": audio_limit,
                    "video": video_limit,
                }
            },
            "allowed_formats": {},
            "validation": {},
            "temporary_storage": {"root_path": str(root)},
            "preprocessing": {},
            "analyzers": {},
            "risk_assessment": {},
            "result": {},
            "error_handling": {},
            "logging": {},
            "external_systems": {},
        }
    )


def controlled_source(
    owner: LocalTemporaryInputOwner,
    payload: bytes,
    *,
    analysis_id: str = "validation-test",
    original_name: str = "sample.png",
    declared_content_type: str | None = None,
    hard_limit_bytes: int | None = None,
) -> ControlledInput:
    owned_source = owner.create(analysis_id)
    measurements = owner.ingest(
        owned_source,
        BytesIO(payload),
        hard_limit_bytes if hard_limit_bytes is not None else len(payload) + 1,
    )
    return ControlledInput(
        analysis_id=analysis_id,
        registered_at=_RECEIVED_AT,
        source=SourceContext(channel=SourceChannel.API),
        input_file=InputFileDescriptor(
            original_name=original_name,
            declared_content_type=declared_content_type,
            size_bytes=measurements.size_bytes,
            received_at=_RECEIVED_AT,
        ),
        sha256=measurements.sha256,
        owned_source=owned_source,
    )


@pytest.mark.parametrize(
    ("extension", "mime_type", "media_type", "parameters_type"),
    _MATRIX,
)
def test_accepts_complete_canonical_matrix_with_required_parameters(
    tmp_path: Path,
    media_files: dict[str, Path],
    extension: str,
    mime_type: str,
    media_type: MediaType,
    parameters_type: type,
) -> None:
    owner = LocalTemporaryInputOwner(tmp_path / extension)
    controlled = controlled_source(
        owner,
        media_files[extension].read_bytes(),
        analysis_id=f"valid-{extension}",
        original_name=f"archive.tar.{extension.upper()}",
        declared_content_type=mime_type,
    )

    result = FileValidator(
        config=make_config(tmp_path / extension),
        temporary_input_owner=owner,
    ).validate(controlled)

    assert result.accepted
    assert result.errors == []
    descriptor = result.validated_file
    assert descriptor is not None
    assert descriptor.extension == extension
    assert descriptor.detected_mime_type == mime_type
    assert descriptor.declared_mime_type == mime_type
    assert descriptor.media_type is media_type
    assert descriptor.signature_match is True
    assert descriptor.safe_read is True
    assert isinstance(descriptor.technical_parameters, parameters_type)
    assert descriptor.sha256 == controlled.sha256
    assert descriptor.size_bytes == controlled.input_file.size_bytes
    assert not controlled.owned_source.is_released
    assert all(check.passed for check in result.checks)
    with owner.open_for_read(controlled.owned_source) as source:
        assert source.read(1)
    owner.cleanup(controlled.owned_source)


def test_required_technical_parameters_are_meaningful(
    tmp_path: Path,
    media_files: dict[str, Path],
) -> None:
    observed: dict[str, object] = {}
    for index, extension in enumerate(("png", "wav", "mp4")):
        owner = LocalTemporaryInputOwner(tmp_path / extension)
        controlled = controlled_source(
            owner,
            media_files[extension].read_bytes(),
            analysis_id=f"parameters-{index}",
            original_name=f"sample.{extension}",
        )
        result = FileValidator(
            config=make_config(tmp_path / extension),
            temporary_input_owner=owner,
        ).validate(controlled)
        assert result.validated_file is not None
        observed[extension] = result.validated_file.technical_parameters
        owner.cleanup(controlled.owned_source)

    image = observed["png"]
    assert isinstance(image, ImageTechnicalParameters)
    assert (image.width, image.height, image.format, image.color_mode) == (16, 12, "PNG", "RGB")
    assert image.frame_count == 1

    audio = observed["wav"]
    assert isinstance(audio, AudioTechnicalParameters)
    assert audio.duration_seconds > 0
    assert audio.sample_rate_hz == 8000
    assert audio.channels == 1
    assert audio.codec == "pcm_s16le"

    video = observed["mp4"]
    assert isinstance(video, VideoTechnicalParameters)
    assert video.duration_seconds > 0
    assert video.container == "mp4"
    assert video.video_codec == "mpeg4"
    assert (video.width, video.height) == (32, 24)
    assert video.fps == pytest.approx(10.0)
    assert video.has_audio is False
    assert video.audio_codec is None


@pytest.mark.parametrize("extension", ["png", "webp"])
def test_animated_images_are_fully_decoded_and_report_frame_count(
    tmp_path: Path,
    media_files: dict[str, Path],
    extension: str,
) -> None:
    owner = LocalTemporaryInputOwner(tmp_path / extension)
    controlled = controlled_source(
        owner,
        media_files[f"animated.{extension}"].read_bytes(),
        original_name=f"animated.{extension}",
    )

    result = FileValidator(
        config=make_config(tmp_path / extension),
        temporary_input_owner=owner,
    ).validate(controlled)

    assert result.validated_file is not None
    parameters = result.validated_file.technical_parameters
    assert isinstance(parameters, ImageTechnicalParameters)
    assert parameters.frame_count == 2
    owner.cleanup(controlled.owned_source)


def test_pillow_safety_rejection_is_normative_and_not_system_failure(
    tmp_path: Path,
    media_files: dict[str, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    owner = LocalTemporaryInputOwner(tmp_path / "temp")
    controlled = controlled_source(
        owner,
        media_files["png"].read_bytes(),
        original_name="sample.png",
    )

    def reject_open(*args: object, **kwargs: object) -> None:
        raise Image.DecompressionBombError("PRIVATE IMAGE DETAIL")

    monkeypatch.setattr(Image, "open", reject_open)

    result = FileValidator(
        config=make_config(tmp_path / "temp"),
        temporary_input_owner=owner,
    ).validate(controlled)

    assert result.errors[0].code == "unsafe_or_unreadable_file"
    assert "PRIVATE" not in result.errors[0].message
    owner.cleanup(controlled.owned_source)


@pytest.mark.parametrize("original_name", ["file", "file.", ".mp4"])
def test_missing_extension_rejects_without_opening_media(
    tmp_path: Path,
    original_name: str,
) -> None:
    owner = LocalTemporaryInputOwner(tmp_path / "temp")
    controlled = controlled_source(owner, b"not-media", original_name=original_name)

    result = FileValidator(
        config=make_config(tmp_path / "temp"),
        temporary_input_owner=owner,
    ).validate(controlled)

    assert not result.accepted
    assert result.errors[0].code == "missing_extension"
    assert [check.code for check in result.checks] == ["file_not_empty", "extension_present"]
    assert not controlled.owned_source.is_released
    owner.cleanup(controlled.owned_source)


def test_empty_source_is_normative_rejection_and_remains_owned(tmp_path: Path) -> None:
    owner = LocalTemporaryInputOwner(tmp_path / "temp")
    controlled = controlled_source(owner, b"", original_name="empty.png")

    result = FileValidator(
        config=make_config(tmp_path / "temp"),
        temporary_input_owner=owner,
    ).validate(controlled)

    assert not result.accepted
    assert result.validated_file is None
    assert result.errors[0].code == "file_empty"
    assert [check.code for check in result.checks] == ["file_not_empty"]
    assert not controlled.owned_source.is_released
    with owner.open_for_read(controlled.owned_source) as source:
        assert source.read() == b""
    owner.cleanup(controlled.owned_source)


def test_unsupported_extension_fails_before_signature_detection(tmp_path: Path) -> None:
    owner = LocalTemporaryInputOwner(tmp_path / "temp")
    controlled = controlled_source(owner, b"PK\x03\x04", original_name="archive.zip")

    result = FileValidator(
        config=make_config(tmp_path / "temp"),
        temporary_input_owner=owner,
    ).validate(controlled)

    assert result.errors[0].code == "unsupported_extension"
    assert [check.code for check in result.checks][-1] == "extension_allowed"
    owner.cleanup(controlled.owned_source)


def test_webm_renamed_as_mkv_is_unsupported_actual_container(
    tmp_path: Path,
    media_files: dict[str, Path],
) -> None:
    owner = LocalTemporaryInputOwner(tmp_path / "temp")
    controlled = controlled_source(
        owner,
        media_files["webm"].read_bytes(),
        original_name="renamed.mkv",
    )

    result = FileValidator(
        config=make_config(tmp_path / "temp"),
        temporary_input_owner=owner,
    ).validate(controlled)

    assert not result.accepted
    assert result.errors[0].code == "unsupported_mime_type"
    assert result.checks[-1].code == "file_signature_valid"
    owner.cleanup(controlled.owned_source)


def test_matroska_with_unrelated_webm_title_is_accepted_structurally(
    tmp_path: Path,
    media_files: dict[str, Path],
) -> None:
    owner = LocalTemporaryInputOwner(tmp_path / "temp")
    controlled = controlled_source(
        owner,
        media_files["mkv"].read_bytes(),
        original_name="metadata-contamination.mkv",
    )

    result = FileValidator(
        config=make_config(tmp_path / "temp"),
        temporary_input_owner=owner,
    ).validate(controlled)

    assert result.accepted
    assert result.errors == []
    assert result.validated_file is not None
    assert result.validated_file.detected_mime_type == "video/x-matroska"
    assert result.validated_file.media_type is MediaType.VIDEO
    owner.cleanup(controlled.owned_source)


def test_ebml_doctype_ignores_values_of_other_structural_elements() -> None:
    unrelated_element = b"\x42\x87\x86webm\xff\xe2"
    document_type_element = b"\x42\x82\x88matroska"
    payload = unrelated_element + document_type_element
    header = b"\x1aE\xdf\xa3" + bytes([0x80 | len(payload)]) + payload

    candidate = _classify_header(header)

    assert candidate is not None
    assert candidate.document_type == "matroska"


@pytest.mark.parametrize(
    "header",
    [
        b"\x1aE\xdf\xa3",
        b"\x1aE\xdf\xa3\x00",
        b"\x1aE\xdf\xa3\xff",
        b"\x1aE\xdf\xa3\x90\x42\x82\x88matroska",
        b"\x1aE\xdf\xa3\x81\x00",
        b"\x1aE\xdf\xa3\x82\x42\x82",
        b"\x1aE\xdf\xa3\x83\x42\x82\x00",
        b"\x1aE\xdf\xa3\x84\x42\x82\x85x",
        b"\x1aE\xdf\xa3\x83\x42\x86\x80",
        b"\x1aE\xdf\xa3\x88\x42\x82\x85other",
    ],
    ids=[
        "truncated-header-size",
        "malformed-header-size-vint",
        "unknown-header-size",
        "header-boundary-beyond-buffer",
        "malformed-element-id-vint",
        "truncated-element-size",
        "malformed-element-size-vint",
        "element-boundary-beyond-header",
        "missing-doctype",
        "unsupported-doctype",
    ],
)
def test_malformed_or_unsupported_bounded_ebml_header_is_not_classified(header: bytes) -> None:
    assert _classify_header(header) is None


def test_renamed_media_rejects_matrix_mismatch_before_decode(
    tmp_path: Path,
    media_files: dict[str, Path],
) -> None:
    owner = LocalTemporaryInputOwner(tmp_path / "temp")
    controlled = controlled_source(
        owner,
        media_files["png"].read_bytes(),
        original_name="renamed.jpg",
    )

    result = FileValidator(
        config=make_config(tmp_path / "temp"),
        temporary_input_owner=owner,
    ).validate(controlled)

    assert result.errors[0].code == "file_signature_mismatch"
    assert result.errors[0].safe_details == {"detected_mime_type": "image/png"}
    assert result.checks[-1].code == "type_consistent"
    assert not result.checks[-1].passed
    assert "safe_read_completed" not in {check.code for check in result.checks}
    owner.cleanup(controlled.owned_source)


@pytest.mark.parametrize(
    ("declared", "accepted"),
    [
        (None, True),
        (" image/png ; charset=binary ", True),
        ("IMAGE/PNG", True),
        ("image/jpeg", False),
        ("image/x-png", False),
        ("not-a-mime", False),
    ],
)
def test_declared_mime_is_optional_normalized_and_never_source_of_truth(
    tmp_path: Path,
    media_files: dict[str, Path],
    declared: str | None,
    accepted: bool,
) -> None:
    owner = LocalTemporaryInputOwner(tmp_path / str(abs(hash(declared))))
    controlled = controlled_source(
        owner,
        media_files["png"].read_bytes(),
        original_name="sample.png",
        declared_content_type=declared,
    )

    result = FileValidator(
        config=make_config(tmp_path / str(abs(hash(declared)))),
        temporary_input_owner=owner,
    ).validate(controlled)

    assert result.accepted is accepted
    check_codes = [check.code for check in result.checks]
    if declared is None:
        assert "declared_mime_consistent" not in check_codes
    elif accepted:
        assert result.validated_file is not None
        assert result.validated_file.declared_mime_type == "image/png"
    else:
        assert result.errors[0].code == "file_signature_mismatch"
        assert result.checks[-1].code == "declared_mime_consistent"
    owner.cleanup(controlled.owned_source)


def test_exact_image_limit_rejects_after_detection_without_decode(
    tmp_path: Path,
    media_files: dict[str, Path],
) -> None:
    owner = LocalTemporaryInputOwner(tmp_path / "temp")
    payload = media_files["png"].read_bytes() + b"x" * (1024 * 1024)
    controlled = controlled_source(
        owner,
        payload,
        original_name="large.png",
        hard_limit_bytes=2 * 1024 * 1024,
    )

    result = FileValidator(
        config=make_config(tmp_path / "temp", image_limit=1, video_limit=2),
        temporary_input_owner=owner,
    ).validate(controlled)

    assert result.errors[0].code == "file_too_large"
    assert result.errors[0].safe_details == {
        "max_size_bytes": 1024 * 1024,
        "observed_size_bytes": len(payload),
    }
    assert result.checks[-1].code == "file_size_allowed"
    assert "safe_read_completed" not in {check.code for check in result.checks}
    owner.cleanup(controlled.owned_source)


@pytest.mark.parametrize(("extension", "keep_bytes"), [("png", 40), ("wav", 20), ("avi", 20)])
def test_corrupt_media_is_normative_unreadable_rejection(
    tmp_path: Path,
    media_files: dict[str, Path],
    extension: str,
    keep_bytes: int,
) -> None:
    owner = LocalTemporaryInputOwner(tmp_path / extension)
    controlled = controlled_source(
        owner,
        media_files[extension].read_bytes()[:keep_bytes],
        original_name=f"corrupt.{extension}",
    )

    result = FileValidator(
        config=make_config(tmp_path / extension),
        temporary_input_owner=owner,
    ).validate(controlled)

    assert not result.accepted
    assert result.errors[0].code == "unsafe_or_unreadable_file"
    assert not controlled.owned_source.is_released
    owner.cleanup(controlled.owned_source)


def test_sha_is_reused_and_source_is_read_only_for_detection_and_decode(
    tmp_path: Path,
    media_files: dict[str, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    owner = LocalTemporaryInputOwner(tmp_path / "temp")
    controlled = controlled_source(
        owner,
        media_files["png"].read_bytes(),
        original_name="sample.png",
    )
    open_calls = 0
    real_open = owner.open_for_read

    def tracking_open(owned_source):
        nonlocal open_calls
        open_calls += 1
        return real_open(owned_source)

    monkeypatch.setattr(owner, "open_for_read", tracking_open)

    result = FileValidator(
        config=make_config(tmp_path / "temp"),
        temporary_input_owner=owner,
    ).validate(controlled)

    assert result.validated_file is not None
    assert result.validated_file.sha256 == controlled.sha256
    assert open_calls == 2
    owner.cleanup(controlled.owned_source)


@pytest.mark.parametrize("failure", ["foreign", "released", "analysis_id", "sha256", "size"])
def test_internal_controlled_input_invariants_are_system_failures(
    tmp_path: Path,
    media_files: dict[str, Path],
    failure: str,
) -> None:
    owner = LocalTemporaryInputOwner(tmp_path / "owner")
    controlled = controlled_source(
        owner,
        media_files["png"].read_bytes(),
        original_name="sample.png",
    )
    validator_owner = owner
    if failure == "foreign":
        validator_owner = LocalTemporaryInputOwner(tmp_path / "foreign")
    elif failure == "released":
        owner.cleanup(controlled.owned_source)
    elif failure == "analysis_id":
        controlled = ControlledInput(
            analysis_id="different-id",
            registered_at=controlled.registered_at,
            source=controlled.source,
            input_file=controlled.input_file,
            sha256=controlled.sha256,
            owned_source=controlled.owned_source,
        )
    elif failure == "sha256":
        controlled = ControlledInput(
            analysis_id=controlled.analysis_id,
            registered_at=controlled.registered_at,
            source=controlled.source,
            input_file=controlled.input_file,
            sha256="INVALID",
            owned_source=controlled.owned_source,
        )
    elif failure == "size":
        controlled = ControlledInput(
            analysis_id=controlled.analysis_id,
            registered_at=controlled.registered_at,
            source=controlled.source,
            input_file=controlled.input_file.model_copy(update={"size_bytes": -1}),
            sha256=controlled.sha256,
            owned_source=controlled.owned_source,
        )

    with pytest.raises(ValidationSystemError):
        FileValidator(
            config=make_config(tmp_path / "owner"),
            temporary_input_owner=validator_owner,
        ).validate(controlled)

    if not controlled.owned_source.is_released:
        owner.cleanup(controlled.owned_source)


def test_media_infrastructure_failure_is_validation_system_failure(
    tmp_path: Path,
    media_files: dict[str, Path],
) -> None:
    class FailingInspector:
        def probe(self, source_path: Path):
            raise MediaToolSystemError("process_start")

        def decode_audio(self, source_path: Path) -> None:
            raise AssertionError("decode must not run")

        def decode_video(self, source_path: Path, *, has_audio: bool) -> None:
            raise AssertionError("decode must not run")

    owner = LocalTemporaryInputOwner(tmp_path / "temp")
    controlled = controlled_source(
        owner,
        media_files["wav"].read_bytes(),
        original_name="sample.wav",
    )

    with pytest.raises(ValidationSystemError) as error_info:
        FileValidator(
            config=make_config(tmp_path / "temp"),
            temporary_input_owner=owner,
            media_inspector=FailingInspector(),  # type: ignore[arg-type]
        ).validate(controlled)

    assert error_info.value.phase == "process_start"
    assert not controlled.owned_source.is_released
    owner.cleanup(controlled.owned_source)
