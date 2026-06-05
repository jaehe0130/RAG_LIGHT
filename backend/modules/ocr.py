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

    processed, preprocessing = _preprocess_image(image, warnings)
    return _run_easyocr(
        processed,
        doc_type=doc_type,
        chunk_size=chunk_size,
        warnings=warnings,
        preprocessing=preprocessing,
    )


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

    processed, preprocessing = _preprocess_image(image, warnings)
    return _run_easyocr(
        processed,
        doc_type=doc_type,
        chunk_size=chunk_size,
        warnings=warnings,
        preprocessing=preprocessing,
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

    enlarged = cv2.resize(
        gray,
        None,
        fx=scale,
        fy=scale,
        interpolation=cv2.INTER_CUBIC,
    )

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
            "preprocessing": preprocessing or {},
            "postprocess_applied": postprocess_applied,
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
    # EasyOCR can read "50%" as "509" in dense Korean legal text.
    # Keep this limited to refund, penalty, and cancellation contexts.
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
    # Remove an OCR noise "1" only in percent + Korean particle + fee/action contexts.
    # Examples: "50%가1 부과됩니다" -> "50%가 부과됩니다"
    action_words = r"(?:부과|청구|적용)"
    return re.sub(rf"(\d{{1,3}}%\s*가)\s*1\s*(?={action_words})", r"\1 ", text)


def _fix_contextual_semicolon(text: str) -> str:
    # Convert a semicolon to a period only when it follows a Korean sentence ending.
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
            "result_count": 0,
            "preprocessing": {},
            "postprocess_applied": False,
        },
    }
