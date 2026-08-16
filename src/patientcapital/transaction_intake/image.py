"""Local-only bounded image validation and Tesseract OCR."""

from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import tempfile
import warnings
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Protocol

from PIL import Image, ImageOps, UnidentifiedImageError

from patientcapital.application.errors import ApplicationError

OCR_EXTRACTOR_VERSION = "tesseract-rus-eng-v1"
_MEDIA_BY_FORMAT = {"JPEG": "image/jpeg", "PNG": "image/png"}


@dataclass(frozen=True, slots=True)
class ExtractedImageText:
    text: str
    media_type: str
    width: int
    height: int
    extractor_version: str


class ImageTextExtractor(Protocol):
    def extract(self, content: bytes, *, declared_content_type: str) -> ExtractedImageText: ...


class TesseractImageExtractor:
    """Validate, normalize and OCR an image without retaining its raw bytes."""

    def __init__(
        self,
        *,
        max_bytes: int = 8_388_608,
        max_pixels: int = 20_000_000,
        timeout_seconds: float = 20.0,
        temp_directory: Path = Path("/tmp"),
        executable: str = "tesseract",
    ) -> None:
        self._max_bytes = max_bytes
        self._max_pixels = max_pixels
        self._timeout_seconds = timeout_seconds
        self._temp_directory = temp_directory
        self._executable = executable

    def _open(self, content: bytes, declared_content_type: str) -> tuple[Image.Image, str]:
        if len(content) > self._max_bytes:
            raise ApplicationError(413, "UPLOAD_TOO_LARGE", "image exceeds configured byte limit")
        if declared_content_type not in _MEDIA_BY_FORMAT.values():
            raise ApplicationError(415, "UNSUPPORTED_IMAGE_TYPE", "only JPEG and PNG are supported")
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("error", Image.DecompressionBombWarning)
                probe = Image.open(BytesIO(content))
                media_type = _MEDIA_BY_FORMAT.get(probe.format or "")
                width, height = probe.size
                probe.verify()
        except (
            UnidentifiedImageError,
            OSError,
            SyntaxError,
            Image.DecompressionBombWarning,
        ) as exc:
            raise ApplicationError(
                422, "INVALID_IMAGE", "image bytes cannot be decoded safely"
            ) from exc
        if media_type is None or media_type != declared_content_type:
            raise ApplicationError(
                415,
                "IMAGE_TYPE_MISMATCH",
                "declared media type differs from decoded image",
            )
        if width <= 0 or height <= 0 or width * height > self._max_pixels:
            raise ApplicationError(
                413, "IMAGE_DIMENSIONS_EXCEEDED", "image dimensions exceed limit"
            )
        image = Image.open(BytesIO(content))
        image.load()
        return image, media_type

    def _run(self, path: Path) -> str:
        if shutil.which(self._executable) is None:
            raise ApplicationError(503, "OCR_UNAVAILABLE", "local Tesseract OCR is unavailable")
        try:
            completed = subprocess.run(
                [
                    self._executable,
                    str(path),
                    "stdout",
                    "-l",
                    "rus+eng",
                    "--psm",
                    "6",
                ],
                check=True,
                capture_output=True,
                text=True,
                timeout=self._timeout_seconds,
                env={"PATH": os.environ.get("PATH", "")},
            )
        except subprocess.TimeoutExpired as exc:
            raise ApplicationError(503, "OCR_TIMEOUT", "local OCR exceeded its time limit") from exc
        except subprocess.CalledProcessError as exc:
            raise ApplicationError(422, "OCR_FAILED", "local OCR could not read the image") from exc
        output = completed.stdout.strip()
        if not output:
            raise ApplicationError(422, "OCR_EMPTY", "local OCR found no text")
        return output[:100_000]

    def extract(self, content: bytes, *, declared_content_type: str) -> ExtractedImageText:
        image, media_type = self._open(content, declared_content_type)
        width, height = image.size
        self._temp_directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        prefix = f"patientcapital-ocr-{hashlib.sha256(content).hexdigest()[:8]}-"
        with tempfile.TemporaryDirectory(prefix=prefix, dir=self._temp_directory) as directory:
            temp = Path(directory)
            os.chmod(temp, 0o700)
            full_path = temp / "normalized.png"
            top_path = temp / "top.png"
            normalized = ImageOps.exif_transpose(image).convert("RGB")
            normalized.save(full_path, format="PNG")
            os.chmod(full_path, 0o600)
            top_height = max(1, round(normalized.height * 0.12))
            top = ImageOps.invert(ImageOps.grayscale(normalized.crop((0, 0, width, top_height))))
            top = top.point(lambda value: 255 if value > 89 else 0)
            top.save(top_path, format="PNG")
            os.chmod(top_path, 0o600)
            text = f"{self._run(top_path)}\n{self._run(full_path)}"
        return ExtractedImageText(
            text=text,
            media_type=media_type,
            width=width,
            height=height,
            extractor_version=OCR_EXTRACTOR_VERSION,
        )
