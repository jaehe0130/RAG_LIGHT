import os
import re
from contextlib import redirect_stderr, redirect_stdout
from io import BytesIO, StringIO
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np
from PIL import Image, ImageOps, UnidentifiedImageError


OCR_LANGUAGES = ["ko", "en"]
DEFAULT_DOC_TYPE = "terms_or_ad"
DEFAULT_CHUNK_SIZE = 800
PDF_TEXT_MIN_LENGTH = 20

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


def extract_text_from_image_path(
    image_path: str,
    doc_type: str = DEFAULT_DOC_TYPE,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
) -> Dict[str, Any]:
    """Extract text from an image path or PDF path.

    Local test examples:
        python -c "from modules.ocr import extract_text_from_image_path; print(extract_text_from_image_path('test.png'))"
        python -c "from modules.ocr import extract_text_from_image_path; print(extract_text_from_image_path('sample.pdf'))"
    """
    warnings: List[str] = []

    if _is_pdf_path(image_path):
        return _extract_text_from_pdf_path(image_path, doc_type=doc_type, chunk_size=chunk_size, warnings=warnings)

    image = _load_image_from_path(image_path)
    if image is None:
        return _build_empty_result(
            doc_type=doc_type,
            warnings=[f"Image could not be loaded from path: {image_path}"],
        )

    processed, preprocessing = _preprocess_image(image, warnings)
    return _run_easyocr(
        processed,
        doc_type=doc_type,
        chunk_size=chunk_size,
        warnings=warnings,
        preprocessing=preprocessing,
        source_type="image",
    )


def extract_text_from_image_bytes(
    image_bytes: bytes,
    doc_type: str = DEFAULT_DOC_TYPE,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
) -> Dict[str, Any]:
    """Extract text from image bytes or PDF bytes."""
    warnings: List[str] = []

    if not image_bytes:
        return _build_empty_result(
            doc_type=doc_type,
            warnings=["Image bytes are empty."],
        )

    if _is_pdf_bytes(image_bytes):
        return _extract_text_from_pdf_bytes(image_bytes, doc_type=doc_type, chunk_size=chunk_size, warnings=warnings)

    image = _load_image_from_bytes(image_bytes)
    if image is None:
        return _build_empty_result(
            doc_type=doc_type,
            warnings=["Image bytes could not be decoded."],
        )

    processed, preprocessing = _preprocess_image(image, warnings)
    return _run_easyocr(
        processed,
        doc_type=doc_type,
        chunk_size=chunk_size,
        warnings=warnings,
        preprocessing=preprocessing,
        source_type="image",
    )


def run_ocr_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """LangGraph-friendly OCR node wrapper."""
    doc_type = state.get("doc_type", DEFAULT_DOC_TYPE)

    if state.get("image_bytes"):
        return extract_text_from_image_bytes(state["image_bytes"], doc_type=doc_type)

    if state.get("image_path"):
        return extract_text_from_image_path(state["image_path"], doc_type=doc_type)

    return _build_empty_result(
        doc_type=doc_type,
        warnings=["No image_path or image_bytes was provided to run_ocr_node."],
    )


def _get_easyocr_cache_dir() -> Path:
    cache_root = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
    if cache_root:
        cache_dir = Path(cache_root) / "RAG_LIGHT" / "EasyOCR"
    else:
        cache_dir = Path.home() / ".cache" / "rag_light" / "easyocr"

    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir


def _is_pdf_path(file_path: str) -> bool:
    return Path(file_path).suffix.lower() == ".pdf"


def _is_pdf_bytes(file_bytes: bytes) -> bool:
    return file_bytes[:5] == b"%PDF-"


def _extract_text_from_pdf_path(
    pdf_path: str,
    doc_type: str,
    chunk_size: int,
    warnings: List[str],
) -> Dict[str, Any]:
    try:
        import fitz

        document = fitz.open(pdf_path)
    except Exception as exc:
        return _build_empty_result(doc_type=doc_type, warnings=[f"PDF could not be opened: {exc}"])

    return _extract_text_from_pdf_document(document, doc_type=doc_type, chunk_size=chunk_size, warnings=warnings)


def _extract_text_from_pdf_bytes(
    pdf_bytes: bytes,
    doc_type: str,
    chunk_size: int,
    warnings: List[str],
) -> Dict[str, Any]:
    try:
        import fitz

        document = fitz.open(stream=pdf_bytes, filetype="pdf")
    except Exception as exc:
        return _build_empty_result(doc_type=doc_type, warnings=[f"PDF bytes could not be opened: {exc}"])

    return _extract_text_from_pdf_document(document, doc_type=doc_type, chunk_size=chunk_size, warnings=warnings)


def _extract_text_from_pdf_document(
    document,
    doc_type: str,
    chunk_size: int,
    warnings: List[str],
) -> Dict[str, Any]:
    raw_parts: List[str] = []
    confidence_values: List[float] = []
    page_modes: List[Dict[str, Any]] = []
    preprocessing_steps: List[Dict[str, Any]] = []
    ocr_result_count = 0

    try:
        page_count = len(document)
        for page_index, page in enumerate(document):
            page_text = _clean_text(page.get_text("text"))

            if len(page_text) >= PDF_TEXT_MIN_LENGTH:
                raw_parts.append(page_text)
                page_modes.append({"page": page_index + 1, "mode": "text"})
                continue

            page_image = _render_pdf_page_to_bgr(page)
            processed, preprocessing = _preprocess_image(page_image, warnings)
            ocr_items = _read_easyocr_items(processed, warnings)
            ocr_text = "\n".join(item["text"] for item in ocr_items if item["text"]).strip()

            raw_parts.append(ocr_text)
            preprocessing_steps.append({"page": page_index + 1, **preprocessing})
            page_modes.append({"page": page_index + 1, "mode": "ocr"})
            ocr_result_count += len(ocr_items)
            confidence_values.extend(item["confidence"] for item in ocr_items if item.get("text"))
    finally:
        document.close()

    raw_text = "\n\n".join(part for part in raw_parts if part).strip()
    cleaned_text, postprocess_applied = _postprocess_text(raw_text)
    chunks = _chunk_text(cleaned_text, chunk_size=chunk_size)

    if not raw_text:
        warnings.append("PDF text extraction and OCR result are both empty.")

    return {
        "raw_text": raw_text,
        "cleaned_text": cleaned_text,
        "chunks": chunks,
        "confidence": _average_numbers(confidence_values) if confidence_values else (1.0 if raw_text else 0.0),
        "warnings": warnings,
        "metadata": {
            "engine": "easyocr",
            "languages": OCR_LANGUAGES,
            "doc_type": doc_type,
            "result_count": ocr_result_count,
            "source_type": "pdf",
            "pdf_engine": "pymupdf",
            "pdf_pages": page_count,
            "pdf_page_modes": page_modes,
            "preprocessing": preprocessing_steps,
            "postprocess_applied": postprocess_applied,
        },
    }


def _render_pdf_page_to_bgr(page) -> np.ndarray:
    # 2.5x roughly maps ordinary PDF pages to OCR-friendly resolution.
    import fitz

    matrix = fitz.Matrix(2.5, 2.5)
    pixmap = page.get_pixmap(matrix=matrix, alpha=False)
    image = np.frombuffer(pixmap.samples, dtype=np.uint8).reshape(pixmap.height, pixmap.width, pixmap.n)

    if pixmap.n == 1:
        return cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)

    return cv2.cvtColor(image, cv2.COLOR_RGB2BGR)


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


def _preprocess_image(image: np.ndarray, warnings: List[str]) -> Tuple[np.ndarray, Dict[str, Any]]:
    """Preprocess dense Korean terms/ad screenshots for OCR."""
    if len(image.shape) == 2:
        gray = image
    else:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    height, width = gray.shape[:2]
    if height == 0 or width == 0:
        warnings.append("Loaded image has invalid dimensions.")
        return gray, {
            "grayscale": True,
            "scale": 1.0,
            "denoise": False,
            "contrast": False,
            "threshold": "skipped_invalid_dimensions",
        }

    longest_side = max(height, width)
    if longest_side < 900:
        scale = 3.0
    elif longest_side < 1600:
        scale = 2.4
    elif longest_side < 2400:
        scale = 1.8
    else:
        scale = 1.25

    enlarged = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
    denoised = cv2.fastNlMeansDenoising(enlarged, None, h=7, templateWindowSize=7, searchWindowSize=21)

    clahe = cv2.createCLAHE(clipLimit=2.6, tileGridSize=(8, 8))
    contrasted = clahe.apply(denoised)

    blurred = cv2.GaussianBlur(contrasted, (0, 0), sigmaX=1.0)
    sharpened = cv2.addWeighted(contrasted, 1.45, blurred, -0.45, 0)

    binary = cv2.adaptiveThreshold(
        sharpened,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        41,
        9,
    )

    kernel = np.ones((1, 1), np.uint8)
    cleaned = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel, iterations=1)

    return cleaned, {
        "grayscale": True,
        "scale": scale,
        "denoise": "fastNlMeansDenoising_h7",
        "contrast": "CLAHE_clip2.6_tile8x8",
        "sharpen": "unsharp_mask_1.45",
        "threshold": "adaptive_gaussian_block41_c9",
        "morphology": "open_1x1",
        "input_size": {"width": width, "height": height},
        "output_size": {"width": int(cleaned.shape[1]), "height": int(cleaned.shape[0])},
    }


def _run_easyocr(
    image: np.ndarray,
    doc_type: str,
    chunk_size: int,
    warnings: Optional[List[str]] = None,
    preprocessing: Optional[Dict[str, Any]] = None,
    source_type: str = "image",
) -> Dict[str, Any]:
    warnings = warnings or []
    items = _read_easyocr_items(image, warnings)
    raw_text = "\n".join(item["text"] for item in items if item["text"]).strip()
    cleaned_text, postprocess_applied = _postprocess_text(raw_text)
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
            "source_type": source_type,
            "preprocessing": preprocessing or {},
            "postprocess_applied": postprocess_applied,
        },
    }


def _read_easyocr_items(image: np.ndarray, warnings: List[str]) -> List[Dict[str, Any]]:
    try:
        reader = get_easyocr_reader()
        with redirect_stdout(StringIO()), redirect_stderr(StringIO()):
            results = reader.readtext(image)
    except Exception as exc:
        warnings.append(f"EasyOCR failed: {exc}")
        return []

    return _parse_easyocr_results(results)


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


def _postprocess_text(raw_text: str) -> Tuple[str, bool]:
    cleaned = _clean_text(raw_text)
    corrected = cleaned

    corrected = _fix_contract_percent_misread(corrected)
    corrected = _fix_common_korean_misreads(corrected)
    corrected = _fix_percent_particle_noise(corrected)
    corrected = _fix_contextual_semicolon(corrected)
    corrected = _clean_text(corrected)

    return corrected, corrected != cleaned


def _fix_contract_percent_misread(text: str) -> str:
    context_words = r"(?:위약금|위약|환불|계약\s*해지|해지|부과|공제)"
    suffix = r"(?=\s*(?:가|이|은|는|을|를|로|와|과|,|\.|;|\)|$))"
    pattern = re.compile(rf"({context_words}[^\n]{{0,24}}?)509{suffix}")
    text = pattern.sub(r"\g<1>50%", text)

    compact_pattern = re.compile(rf"({context_words}[^\n]{{0,24}}?)50\s*9{suffix}")
    return compact_pattern.sub(r"\g<1>50%", text)


def _fix_common_korean_misreads(text: str) -> str:
    replacements = {
        "부과되니다": "부과됩니다",
        "부과됩나다": "부과됩니다",
        "부과됨니다": "부과됩니다",
    }

    for wrong, right in replacements.items():
        text = text.replace(wrong, right)

    return text


def _fix_percent_particle_noise(text: str) -> str:
    action_words = r"(?:부과|청구|적용)"
    return re.sub(rf"(\d{{1,3}}%\s*가)\s*1\s*(?={action_words})", r"\1 ", text)


def _fix_contextual_semicolon(text: str) -> str:
    sentence_endings = (
        "합니다",
        "됩니다",
        "습니다",
        "입니다",
        "없습니다",
        "불가합니다",
        "부과됩니다",
    )
    endings = "|".join(map(re.escape, sentence_endings))
    text = re.sub(rf"({endings})\s*;", r"\1.", text)
    return re.sub(r";(?=\s*$)", ".", text)


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
    return _average_numbers(confidences)


def _average_numbers(values: List[float]) -> float:
    if not values:
        return 0.0

    return round(sum(values) / len(values), 4)


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
            "result_count": 0,
            "preprocessing": {},
            "postprocess_applied": False,
        },
    }
