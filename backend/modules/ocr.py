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

    variants = _preprocess_image_variants(image, warnings)
    return _run_easyocr_variants(
        variants,
        doc_type=doc_type,
        chunk_size=chunk_size,
        warnings=warnings,
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

    variants = _preprocess_image_variants(image, warnings)
    return _run_easyocr_variants(
        variants,
        doc_type=doc_type,
        chunk_size=chunk_size,
        warnings=warnings,
        source_type="image",
    )


def run_ocr_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """LangGraph-friendly OCR node wrapper."""
    doc_type = state.get("doc_type", DEFAULT_DOC_TYPE)

    if state.get("image_bytes"):
        return _prepare_graph_ocr_result(extract_text_from_image_bytes(state["image_bytes"], doc_type=doc_type))

    if state.get("image_path"):
        return _prepare_graph_ocr_result(extract_text_from_image_path(state["image_path"], doc_type=doc_type))

    if state.get("file_path"):
        return _prepare_graph_ocr_result(extract_text_from_image_path(state["file_path"], doc_type=doc_type))

    return _build_empty_result(
        doc_type=doc_type,
        warnings=["No image_path, file_path, or image_bytes was provided to run_ocr_node."],
    )


def _prepare_graph_ocr_result(result: Dict[str, Any]) -> Dict[str, Any]:
    """Use postprocessed OCR text for the LangGraph/API path.

    main.py currently reads final_output["raw_text"], so Team B exposes the
    cleaned OCR text through raw_text only for the graph state. The standalone
    extract_* functions still keep raw_text as the EasyOCR original.
    """
    cleaned_text = result.get("cleaned_text") or result.get("raw_text") or ""
    original_raw_text = result.get("raw_text", "")

    if cleaned_text != original_raw_text:
        metadata = dict(result.get("metadata") or {})
        metadata["graph_raw_text_source"] = "cleaned_text"
        metadata["easyocr_raw_text_preserved"] = True
        result = {**result, "metadata": metadata}

    return {**result, "raw_text": cleaned_text}


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
            variants = _preprocess_image_variants(page_image, warnings)
            ocr_items, preprocessing = _read_best_easyocr_items(variants, warnings)
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


def _preprocess_image_variants(image: np.ndarray, warnings: List[str]) -> List[Tuple[str, np.ndarray, Dict[str, Any]]]:
    """Build several OCR-ready variants for JPG/PNG quality differences."""
    if len(image.shape) == 2:
        gray = image
    else:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    height, width = gray.shape[:2]
    if height == 0 or width == 0:
        warnings.append("Loaded image has invalid dimensions.")
        return [
            (
                "invalid_original",
                gray,
                {
                    "variant": "invalid_original",
                    "grayscale": True,
                    "scale": 1.0,
                    "threshold": "skipped_invalid_dimensions",
                },
            )
        ]

    longest_side = max(height, width)
    target_longest_side = 2200
    scale = max(1.0, min(3.2, target_longest_side / longest_side))

    if len(image.shape) == 2:
        color_source = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
    else:
        color_source = image

    enlarged_color = cv2.resize(color_source, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
    enlarged = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)

    # Gentle denoise keeps small Korean strokes sharper than aggressive smoothing.
    denoised = cv2.bilateralFilter(enlarged, d=5, sigmaColor=35, sigmaSpace=35)

    clahe = cv2.createCLAHE(clipLimit=2.2, tileGridSize=(8, 8))
    contrasted = clahe.apply(denoised)

    blurred = cv2.GaussianBlur(contrasted, (0, 0), sigmaX=0.8)
    sharpened = cv2.addWeighted(contrasted, 1.55, blurred, -0.55, 0)

    adaptive = cv2.adaptiveThreshold(
        sharpened,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        35,
        7,
    )

    _, otsu = cv2.threshold(
        cv2.GaussianBlur(sharpened, (3, 3), 0),
        0,
        255,
        cv2.THRESH_BINARY + cv2.THRESH_OTSU,
    )

    base_metadata = {
        "grayscale": True,
        "applied": True,
        "candidate_count": 5,
        "scale": round(scale, 3),
        "input_size": {"width": width, "height": height},
        "output_size": {"width": int(sharpened.shape[1]), "height": int(sharpened.shape[0])},
        "denoise": "bilateral_d5_sigma35",
        "contrast": "CLAHE_clip2.2_tile8x8",
        "sharpen": "unsharp_mask_1.55",
    }

    variants = [
        (
            "enhanced_gray",
            sharpened,
            {
                **base_metadata,
                "variant": "enhanced_gray",
                "threshold": "none",
            },
        ),
    ]

    if float(np.mean(gray)) < 100:
        inverted = cv2.bitwise_not(sharpened)
        variants.append(
            (
                "inverted_dark_background",
                inverted,
                {
                    **base_metadata,
                    "variant": "inverted_dark_background",
                    "threshold": "none",
                },
            )
        )

    for _, _, metadata in variants:
        metadata["candidate_count"] = len(variants)

    return variants


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


def _run_easyocr_variants(
    variants: List[Tuple[str, np.ndarray, Dict[str, Any]]],
    doc_type: str,
    chunk_size: int,
    warnings: Optional[List[str]] = None,
    source_type: str = "image",
) -> Dict[str, Any]:
    warnings = warnings or []
    items, preprocessing = _read_best_easyocr_items(variants, warnings)
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
            "preprocessing": preprocessing,
            "postprocess_applied": postprocess_applied,
        },
    }


def _read_best_easyocr_items(
    variants: List[Tuple[str, np.ndarray, Dict[str, Any]]],
    warnings: List[str],
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    best_items: List[Dict[str, Any]] = []
    best_metadata: Dict[str, Any] = {}
    best_score = -1.0
    variant_scores = []

    for variant_name, variant_image, metadata in variants:
        local_warnings: List[str] = []
        items = _read_easyocr_items(variant_image, local_warnings)
        text = "\n".join(item["text"] for item in items if item["text"]).strip()
        confidence = _average_confidence(items)
        score = _score_ocr_candidate(text, confidence, len(items))

        variant_scores.append(
            {
                "variant": variant_name,
                "score": round(score, 4),
                "confidence": confidence,
                "result_count": len(items),
                "text_length": len(text),
            }
        )

        if local_warnings:
            warnings.extend(local_warnings)

        if score > best_score:
            best_score = score
            best_items = items
            best_metadata = metadata

    return best_items, {
        **best_metadata,
        "selected_variant": best_metadata.get("variant"),
        "variant_scores": variant_scores,
    }


def _score_ocr_candidate(text: str, confidence: float, result_count: int) -> float:
    text_length_score = min(len(text) / 700, 1.0)
    count_score = min(result_count / 30, 1.0) * 0.25
    korean_count = len(re.findall(r"[가-힣]", text))
    digit_count = len(re.findall(r"\d", text))
    question_count = text.count("?")
    korean_score = min(korean_count / 80, 1.0) * 0.45
    digit_score = min(digit_count / 12, 1.0) * 0.12
    question_penalty = min(question_count / max(len(text), 1), 1.0) * 0.8
    return (confidence * 1.45) + text_length_score + count_score + korean_score + digit_score - question_penalty


def _score_ocr_candidate(text: str, confidence: float, result_count: int) -> float:
    text_length_score = min(len(text) / 700, 1.0)
    count_score = min(result_count / 30, 1.0) * 0.25
    korean_count = len(re.findall(r"[\uac00-\ud7a3]", text))
    digit_count = len(re.findall(r"\d", text))
    question_count = text.count("?")
    sentence_ending_count = len(re.findall(r"(?:\ub2c8\ub2e4|[.!?])", text))
    incomplete_action_count = len(re.findall(r"(?:\ubd80\uacfc|\uccad\uad6c|\uc801\uc6a9)\s*(?:\n|$)", text))

    korean_score = min(korean_count / 80, 1.0) * 0.45
    digit_score = min(digit_count / 12, 1.0) * 0.12
    sentence_score = min(sentence_ending_count / 8, 1.0) * 0.35
    question_penalty = min(question_count / max(len(text), 1), 1.0) * 0.8
    incomplete_action_penalty = incomplete_action_count * 0.45

    return (
        (confidence * 1.15)
        + text_length_score
        + count_score
        + korean_score
        + digit_score
        + sentence_score
        - question_penalty
        - incomplete_action_penalty
    )


def _read_easyocr_items(image: np.ndarray, warnings: List[str]) -> List[Dict[str, Any]]:
    try:
        reader = get_easyocr_reader()
        read_configs = [
            {
                "decoder": "greedy",
                "paragraph": False,
                "text_threshold": 0.35,
                "low_text": 0.2,
                "link_threshold": 0.3,
                "canvas_size": 2560,
                "mag_ratio": 1.4,
            },
        ]

        best_items: List[Dict[str, Any]] = []
        best_score = -1.0

        with redirect_stdout(StringIO()), redirect_stderr(StringIO()):
            for read_config in read_configs:
                results = reader.readtext(image, **read_config)
                items = _parse_easyocr_results(results)
                text = "\n".join(item["text"] for item in items if item["text"]).strip()
                confidence = _average_confidence(items)
                score = _score_ocr_candidate(text, confidence, len(items))

                if score > best_score:
                    best_score = score
                    best_items = items
    except Exception as exc:
        warnings.append(f"EasyOCR failed: {exc}")
        return []

    return best_items


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


def _fix_contract_percent_misread(text: str) -> str:
    context_words = (
        r"(?:"
        r"\uc704\uc57d\uae08|\uc704\uc57d|\ud658\ubd88|"
        r"\uacc4\uc57d\s*\ud574\uc9c0|\ud574\uc9c0|"
        r"\ubd80\uacfc|\uccad\uad6c|\uacf5\uc81c"
        r")"
    )
    suffix = (
        r"(?=\s*(?:"
        r"\uac00|\uc740|\ub294|\uc774|\uc744|\ub97c|\ub85c|"
        r"\ubd80\uacfc|\uccad\uad6c|\uc801\uc6a9|\uacf5\uc81c|"
        r",|\.|;|\)|$"
        r"))"
    )

    # EasyOCR can read '%' as '9' or '96' near fee/refund clauses.
    pattern = re.compile(rf"({context_words}[^\n]{{0,32}}?)(\d{{1,3}})\s*9\s*6?{suffix}")
    text = pattern.sub(r"\g<1>\g<2>%", text)

    missing_particle_pattern = re.compile(
        rf"({context_words}[^\n]{{0,32}}?)(\d{{1,3}})\s*9\s*[67]?\s+(?=(?:\ubd80\uacfc|\uccad\uad6c|\uc801\uc6a9))"
    )
    return missing_particle_pattern.sub(lambda match: f"{match.group(1)}{match.group(2)}%\uac00 ", text)


def _fix_common_korean_misreads(text: str) -> str:
    replacements = {
        "\ubd80\uacfc\ub418\ub2c8\ub2e4": "\ubd80\uacfc\ub429\ub2c8\ub2e4",
        "\ubd80\uacfc\ub428\ub2c8\ub2e4": "\ubd80\uacfc\ub429\ub2c8\ub2e4",
        "\ubd80\uacfc\ud295\ub2c8\ub2e4": "\ubd80\uacfc\ub429\ub2c8\ub2e4",
        "\ubd80\uacfc\ud2f0\ub2c8\ub2e4": "\ubd80\uacfc\ub429\ub2c8\ub2e4",
        "\uccad\uad6c\ub418\ub2c8\ub2e4": "\uccad\uad6c\ub429\ub2c8\ub2e4",
        "\uccad\uad6c\uc6d4\ub2c8\ub2e4": "\uccad\uad6c\ub429\ub2c8\ub2e4",
    }

    for wrong, right in replacements.items():
        text = text.replace(wrong, right)

    return text


def _fix_percent_particle_noise(text: str) -> str:
    action_words = r"(?:\ubd80\uacfc|\uccad\uad6c|\uc801\uc6a9)"
    return re.sub(rf"(\d{{1,3}}%\s*\uac00)\s*1\s*(?={action_words})", r"\1 ", text)


def _fix_contextual_semicolon(text: str) -> str:
    sentence_endings = (
        "\ud569\ub2c8\ub2e4",
        "\ub429\ub2c8\ub2e4",
        "\uc2b5\ub2c8\ub2e4",
        "\uc785\ub2c8\ub2e4",
        "\uc5c6\uc2b5\ub2c8\ub2e4",
        "\ubd88\uac00\ud569\ub2c8\ub2e4",
        "\ubd80\uacfc\ub429\ub2c8\ub2e4",
    )
    endings = "|".join(map(re.escape, sentence_endings))
    text = re.sub(rf"({endings})\s*[;:]", r"\1.", text)
    return re.sub(r"[;:](?=\s*$)", ".", text)


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
