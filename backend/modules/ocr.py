import os
import re
from contextlib import redirect_stderr, redirect_stdout
from io import BytesIO
from io import StringIO
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np
from PIL import Image, ImageOps, UnidentifiedImageError


OCR_LANGUAGES = ["ko", "en"]
DEFAULT_DOC_TYPE = "terms_or_ad"
DEFAULT_CHUNK_SIZE = 800

_reader = None


def get_easyocr_reader():
    """Create the EasyOCR reader lazily and reuse it across OCR calls."""
    global _reader

    if _reader is None:
        import easyocr

        model_dir = _get_easyocr_cache_dir()
        with redirect_stdout(StringIO()), redirect_stderr(StringIO()):
            _reader = easyocr.Reader(
                OCR_LANGUAGES,
                gpu=False,
                model_storage_directory=str(model_dir),
                user_network_directory=str(model_dir),
            )

    return _reader


def _get_easyocr_cache_dir() -> Path:
    cache_root = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
    if cache_root:
        cache_dir = Path(cache_root) / "RAG_LIGHT" / "EasyOCR"
    else:
        cache_dir = Path.home() / ".cache" / "rag_light" / "easyocr"

    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir


def extract_text_from_image_path(
    image_path: str,
    doc_type: str = DEFAULT_DOC_TYPE,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
) -> Dict[str, Any]:
    """Extract OCR text from an image path.

    Local test example:
        python -c "from modules.ocr import extract_text_from_image_path; print(extract_text_from_image_path('test.png'))"
    """
    warnings: List[str] = []

    image = _load_image_from_path(image_path)
    if image is None:
        return _build_empty_result(
            doc_type=doc_type,
            warnings=[f"Image could not be loaded from path: {image_path}"],
        )

    processed = _preprocess_image(image, warnings)
    return _run_easyocr(processed, doc_type=doc_type, chunk_size=chunk_size, warnings=warnings)


def extract_text_from_image_bytes(
    image_bytes: bytes,
    doc_type: str = DEFAULT_DOC_TYPE,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
) -> Dict[str, Any]:
    """Extract OCR text from image bytes.

    Local test example:
        python -c "from pathlib import Path; from modules.ocr import extract_text_from_image_bytes; print(extract_text_from_image_bytes(Path('test.png').read_bytes()))"
    """
    warnings: List[str] = []

    if not image_bytes:
        return _build_empty_result(
            doc_type=doc_type,
            warnings=["Image bytes are empty."],
        )

    image = _load_image_from_bytes(image_bytes)
    if image is None:
        return _build_empty_result(
            doc_type=doc_type,
            warnings=["Image bytes could not be decoded."],
        )

    processed = _preprocess_image(image, warnings)
    return _run_easyocr(processed, doc_type=doc_type, chunk_size=chunk_size, warnings=warnings)


def run_ocr_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """LangGraph-friendly OCR node wrapper.

    Expected state keys:
        image_path: optional path to an uploaded image
        image_bytes: optional raw uploaded image bytes
        doc_type: optional document type metadata
    """
    doc_type = state.get("doc_type", DEFAULT_DOC_TYPE)

    if state.get("image_bytes"):
        return extract_text_from_image_bytes(state["image_bytes"], doc_type=doc_type)

    if state.get("image_path"):
        return extract_text_from_image_path(state["image_path"], doc_type=doc_type)

    return _build_empty_result(
        doc_type=doc_type,
        warnings=["No image_path or image_bytes was provided to run_ocr_node."],
    )


def _load_image_from_path(image_path: str) -> Optional[np.ndarray]:
    try:
        with Image.open(image_path) as image:
            return _pil_to_bgr(image)
    except (FileNotFoundError, UnidentifiedImageError, OSError):
        return None


def _load_image_from_bytes(image_bytes: bytes) -> Optional[np.ndarray]:
    try:
        with Image.open(BytesIO(image_bytes)) as image:
            return _pil_to_bgr(image)
    except (UnidentifiedImageError, OSError):
        return None


def _pil_to_bgr(image: Image.Image) -> np.ndarray:
    image = ImageOps.exif_transpose(image).convert("RGB")
    rgb = np.array(image)
    return cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)


def _preprocess_image(image: np.ndarray, warnings: List[str]) -> np.ndarray:
    """Preprocess text-heavy images such as terms pages and ad screenshots."""
    if len(image.shape) == 2:
        gray = image
    else:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    height, width = gray.shape[:2]
    if height == 0 or width == 0:
        warnings.append("Loaded image has invalid dimensions.")
        return gray

    scale = 2.0
    if max(height, width) < 1200:
        scale = 2.5

    enlarged = cv2.resize(
        gray,
        None,
        fx=scale,
        fy=scale,
        interpolation=cv2.INTER_CUBIC,
    )

    denoised = cv2.fastNlMeansDenoising(
        enlarged,
        None,
        h=10,
        templateWindowSize=7,
        searchWindowSize=21,
    )

    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    contrasted = clahe.apply(denoised)

    binary = cv2.adaptiveThreshold(
        contrasted,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        31,
        11,
    )

    return binary


def _run_easyocr(
    image: np.ndarray,
    doc_type: str,
    chunk_size: int,
    warnings: Optional[List[str]] = None,
) -> Dict[str, Any]:
    warnings = warnings or []

    try:
        reader = get_easyocr_reader()
        with redirect_stdout(StringIO()), redirect_stderr(StringIO()):
            results = reader.readtext(image)
    except Exception as exc:
        return _build_empty_result(
            doc_type=doc_type,
            warnings=warnings + [f"EasyOCR failed: {exc}"],
        )

    items = _parse_easyocr_results(results)
    raw_text = "\n".join(item["text"] for item in items if item["text"]).strip()
    cleaned_text = _clean_text(raw_text)
    chunks = _chunk_text(cleaned_text, chunk_size=chunk_size)
    confidence = _average_confidence(items)

    if not raw_text:
        warnings.append("OCR result is empty. The image may be blank, too blurry, or unsupported.")

    return {
        "raw_text": raw_text,
        "cleaned_text": cleaned_text,
        "chunks": chunks,
        "confidence": confidence,
        "warnings": warnings,
        "metadata": {
            "engine": "easyocr",
            "languages": OCR_LANGUAGES,
            "doc_type": doc_type,
            "result_count": len(items),
        },
    }


def _parse_easyocr_results(results: List[Tuple[Any, str, float]]) -> List[Dict[str, Any]]:
    parsed = []

    for result in results:
        if len(result) < 3:
            continue

        bbox, text, confidence = result
        parsed.append(
            {
                "bbox": bbox,
                "text": str(text).strip(),
                "confidence": float(confidence),
            }
        )

    return parsed


def _clean_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _chunk_text(text: str, chunk_size: int = DEFAULT_CHUNK_SIZE) -> List[str]:
    if not text:
        return []

    sentences = re.split(r"(?<=[.!?。！？\n])\s+", text)
    chunks: List[str] = []
    current = ""

    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue

        if len(sentence) > chunk_size:
            if current:
                chunks.append(current.strip())
                current = ""
            chunks.extend(_split_by_length(sentence, chunk_size))
            continue

        next_chunk = f"{current} {sentence}".strip()
        if len(next_chunk) <= chunk_size:
            current = next_chunk
        else:
            if current:
                chunks.append(current.strip())
            current = sentence

    if current:
        chunks.append(current.strip())

    return chunks


def _split_by_length(text: str, chunk_size: int) -> List[str]:
    return [text[index : index + chunk_size].strip() for index in range(0, len(text), chunk_size)]


def _average_confidence(items: List[Dict[str, Any]]) -> float:
    confidences = [item["confidence"] for item in items if item.get("text")]
    if not confidences:
        return 0.0

    return round(sum(confidences) / len(confidences), 4)


def _build_empty_result(doc_type: str, warnings: List[str]) -> Dict[str, Any]:
    return {
        "raw_text": "",
        "cleaned_text": "",
        "chunks": [],
        "confidence": 0.0,
        "warnings": warnings,
        "metadata": {
            "engine": "easyocr",
            "languages": OCR_LANGUAGES,
            "doc_type": doc_type,
        },
    }
