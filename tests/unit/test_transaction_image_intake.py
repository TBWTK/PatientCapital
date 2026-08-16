from io import BytesIO
from pathlib import Path
from subprocess import CompletedProcess, TimeoutExpired

import pytest
from PIL import Image

from patientcapital.application.errors import ApplicationError
from patientcapital.transaction_intake.image import TesseractImageExtractor


def _image_bytes(image_format: str = "JPEG", size: tuple[int, int] = (8, 8)) -> bytes:
    buffer = BytesIO()
    Image.new("RGB", size, "white").save(buffer, format=image_format)
    return buffer.getvalue()


def test_valid_image_is_ocrd_locally_and_temporary_files_are_removed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[Path] = []
    monkeypatch.setattr("patientcapital.transaction_intake.image.shutil.which", lambda _: "/ocr")

    def run(command: list[str], **_: object) -> CompletedProcess[str]:
        calls.append(Path(command[1]))
        assert calls[-1].is_file()
        return CompletedProcess(command, 0, stdout="Покупка 1 ОФЗ", stderr="")

    monkeypatch.setattr("patientcapital.transaction_intake.image.subprocess.run", run)
    extractor = TesseractImageExtractor(temp_directory=tmp_path)

    extracted = extractor.extract(_image_bytes(), declared_content_type="image/jpeg")

    assert extracted.media_type == "image/jpeg"
    assert extracted.width == 8
    assert extracted.height == 8
    assert extracted.text == "Покупка 1 ОФЗ\nПокупка 1 ОФЗ"  # noqa: RUF001
    assert len(calls) == 2
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize(
    ("content_type", "content", "code"),
    [
        ("application/pdf", b"not-an-image", "UNSUPPORTED_IMAGE_TYPE"),
        ("image/jpeg", b"not-an-image", "INVALID_IMAGE"),
        ("image/png", _image_bytes("JPEG"), "IMAGE_TYPE_MISMATCH"),
    ],
)
def test_image_type_and_magic_must_agree(
    tmp_path: Path, content_type: str, content: bytes, code: str
) -> None:
    extractor = TesseractImageExtractor(temp_directory=tmp_path)
    with pytest.raises(ApplicationError) as error:
        extractor.extract(content, declared_content_type=content_type)
    assert error.value.code == code


def test_image_byte_and_pixel_limits_fail_closed(tmp_path: Path) -> None:
    content = _image_bytes(size=(8, 8))
    with pytest.raises(ApplicationError) as bytes_error:
        TesseractImageExtractor(max_bytes=2, temp_directory=tmp_path).extract(
            content, declared_content_type="image/jpeg"
        )
    assert bytes_error.value.code == "UPLOAD_TOO_LARGE"

    with pytest.raises(ApplicationError) as pixels_error:
        TesseractImageExtractor(max_pixels=63, temp_directory=tmp_path).extract(
            content, declared_content_type="image/jpeg"
        )
    assert pixels_error.value.code == "IMAGE_DIMENSIONS_EXCEEDED"


def test_ocr_timeout_is_visible_and_temporary_files_are_removed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("patientcapital.transaction_intake.image.shutil.which", lambda _: "/ocr")

    def timeout(*_: object, **__: object) -> None:
        raise TimeoutExpired("tesseract", 0.01)

    monkeypatch.setattr("patientcapital.transaction_intake.image.subprocess.run", timeout)
    extractor = TesseractImageExtractor(temp_directory=tmp_path, timeout_seconds=0.01)

    with pytest.raises(ApplicationError) as error:
        extractor.extract(_image_bytes(), declared_content_type="image/jpeg")
    assert error.value.code == "OCR_TIMEOUT"
    assert list(tmp_path.iterdir()) == []
