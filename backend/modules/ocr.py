import mimetypes
import os
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv

from modules.image_preprocess import preprocess_image_for_ocr
from modules.text_cleaner import clean_ocr_text


PDF_TEXT_MIN_LENGTH = 30
SUPPORTED_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png"}
SUPPORTED_MIME_TYPES = {"application/pdf", "image/jpeg", "image/png"}

_paddle_ocr = None


def extract_text(file_path: str) -> Dict[str, Any]:
    """Extract text from a PDF/JPG/PNG file using the project OCR routing flow."""
    load_dotenv()

    warnings: List[str] = []
    path = Path(file_path)
    file_type, mime_type = _detect_file(path)

    if not path.exists():
        return _result(
            text="",
            engine="failed",
            fallback_used=False,
            warnings=[f"File does not exist: {path}"],
            file_type=file_type or "unknown",
            is_text_pdf=False,
            mime_type=mime_type,
            preprocessed=False,
        )

    if file_type is None:
        return _result(
            text="",
            engine="failed",
            fallback_used=False,
            warnings=[f"Unsupported file type: {path.suffix or 'unknown'}"],
            file_type="unknown",
            is_text_pdf=False,
            mime_type=mime_type,
            preprocessed=False,
        )

    print(f"[OCR] file={path} file_type={file_type} mime_type={mime_type}")

    if file_type == "pdf":
        return _extract_pdf(path, mime_type, warnings)

    return _extract_image(path, mime_type, warnings)


def extract_text_from_image_path(image_path: str, *args: Any, **kwargs: Any) -> Dict[str, Any]:
    """Backward-compatible alias for older code paths."""
    return extract_text(image_path)


def run_ocr_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """LangGraph-friendly wrapper that exposes the cleaned OCR text as raw_text."""
    file_path = state.get("file_path") or state.get("image_path")
    if not file_path:
        result = _result(
            text="",
            engine="failed",
            fallback_used=False,
            warnings=["No file_path or image_path was provided to OCR."],
            file_type="unknown",
            is_text_pdf=False,
            mime_type="",
            preprocessed=False,
        )
        return {**result, "raw_text": ""}

    result = extract_text(str(file_path))
    return {**result, "raw_text": result.get("text", "")}


def _extract_pdf(path: Path, mime_type: str, warnings: List[str]) -> Dict[str, Any]:
    print("[OCR] PDF detected. Checking embedded text with PyMuPDF first.")

    try:
        pymupdf_text = _extract_pdf_text_with_pymupdf(path)
        cleaned = clean_ocr_text(pymupdf_text, [])
        if _has_enough_text(cleaned):
            print("[OCR] PyMuPDF text is sufficient. Skipping paid OCR.")
            return _result(
                text=cleaned,
                engine="pymupdf",
                fallback_used=False,
                warnings=warnings,
                file_type="pdf",
                is_text_pdf=True,
                mime_type=mime_type,
                preprocessed=False,
            )
        warnings.append("PDF embedded text is empty or too short. Treating it as a scanned PDF.")
    except Exception as exc:
        warnings.append(f"PyMuPDF text extraction failed: {exc}")

    print("[OCR] Calling Google Document AI with original PDF.")
    try:
        text = google_document_ai_ocr(str(path), mime_type)
        cleaned = clean_ocr_text(text, warnings)
        if not _has_enough_text(cleaned):
            raise ValueError("Google Document AI returned too little text.")

        return _result(
            text=cleaned,
            engine="google_document_ai",
            fallback_used=False,
            warnings=warnings,
            file_type="pdf",
            is_text_pdf=False,
            mime_type=mime_type,
            preprocessed=False,
        )
    except Exception as exc:
        warnings.append(f"Google Document AI failed: {exc}")

    print("[OCR] Falling back to PaddleOCR. PDF pages will be rendered to images first.")
    try:
        text = paddleocr_fallback(str(path), file_type="pdf")
        cleaned = clean_ocr_text(text, warnings)
        return _result(
            text=cleaned,
            engine="paddleocr" if cleaned else "failed",
            fallback_used=True,
            warnings=warnings,
            file_type="pdf",
            is_text_pdf=False,
            mime_type=mime_type,
            preprocessed=False,
        )
    except Exception as exc:
        warnings.append(f"PaddleOCR fallback failed: {exc}")
        return _failed_pdf_result(mime_type, warnings)


def _extract_image(path: Path, mime_type: str, warnings: List[str]) -> Dict[str, Any]:
    print("[OCR] Image detected. Calling Google Document AI with original image.")

    try:
        text = google_document_ai_ocr(str(path), mime_type)
        cleaned = clean_ocr_text(text, warnings)
        if not _has_enough_text(cleaned):
            raise ValueError("Google Document AI returned too little text.")

        return _result(
            text=cleaned,
            engine="google_document_ai",
            fallback_used=False,
            warnings=warnings,
            file_type="image",
            is_text_pdf=False,
            mime_type=mime_type,
            preprocessed=False,
        )
    except Exception as exc:
        warnings.append(f"Google Document AI failed: {exc}")

    print("[OCR] Falling back to PaddleOCR after OpenCV preprocessing.")
    preprocessed_path: Optional[str] = None
    try:
        preprocessed = preprocess_image_for_ocr(str(path))
        preprocessed_path = preprocessed["path"]
        warnings.append(f"OpenCV preprocessing applied: {preprocessed['metadata']}")

        text = paddleocr_fallback(preprocessed_path, file_type="image")
        cleaned = clean_ocr_text(text, warnings)
        return _result(
            text=cleaned,
            engine="paddleocr" if cleaned else "failed",
            fallback_used=True,
            warnings=warnings,
            file_type="image",
            is_text_pdf=False,
            mime_type=mime_type,
            preprocessed=True,
        )
    except Exception as exc:
        warnings.append(f"PaddleOCR fallback failed: {exc}")
        return _result(
            text="",
            engine="failed",
            fallback_used=True,
            warnings=warnings,
            file_type="image",
            is_text_pdf=False,
            mime_type=mime_type,
            preprocessed=preprocessed_path is not None,
        )
    finally:
        _remove_temp_file(preprocessed_path)


def google_document_ai_ocr(file_path: str, mime_type: str) -> str:
    """Run Google Document AI using Application Default Credentials.

    Set these values in .env:
        GOOGLE_CLOUD_PROJECT_ID
        DOCUMENT_AI_LOCATION
        DOCUMENT_AI_PROCESSOR_ID
    """
    project_id = os.getenv("GOOGLE_CLOUD_PROJECT_ID")
    location = os.getenv("DOCUMENT_AI_LOCATION")
    processor_id = os.getenv("DOCUMENT_AI_PROCESSOR_ID")

    missing = [
        name
        for name, value in {
            "GOOGLE_CLOUD_PROJECT_ID": project_id,
            "DOCUMENT_AI_LOCATION": location,
            "DOCUMENT_AI_PROCESSOR_ID": processor_id,
        }.items()
        if not value
    ]
    if missing:
        raise ValueError(f"Missing Document AI env vars: {', '.join(missing)}")

    try:
        from google.api_core.client_options import ClientOptions
        from google.cloud import documentai
    except ImportError as exc:
        raise ImportError("Install google-cloud-documentai to use Google Document AI.") from exc

    client_options = ClientOptions(api_endpoint=f"{location}-documentai.googleapis.com")
    client = documentai.DocumentProcessorServiceClient(client_options=client_options)
    processor_name = client.processor_path(project_id, location, processor_id)

    with open(file_path, "rb") as file_obj:
        content = file_obj.read()

    request = documentai.ProcessRequest(
        name=processor_name,
        raw_document=documentai.RawDocument(content=content, mime_type=mime_type),
    )
    response = client.process_document(request=request)
    text = (response.document.text or "").strip()

    if not text:
        raise ValueError("Google Document AI returned empty text.")

    print(f"[OCR] Google Document AI succeeded. chars={len(text)}")
    return text


def paddleocr_fallback(file_path: str, file_type: str) -> str:
    """Run PaddleOCR fallback. PDFs are rendered to images before OCR."""
    ocr = _get_paddle_ocr()

    if file_type == "pdf":
        image_paths = _render_pdf_pages_to_temp_images(file_path)
        try:
            page_texts = []
            for index, image_path in enumerate(image_paths, start=1):
                print(f"[OCR] PaddleOCR page {index}: {image_path}")
                page_texts.append(_run_paddle_on_image(ocr, image_path))
            return "\n\n".join(text for text in page_texts if text).strip()
        finally:
            for image_path in image_paths:
                _remove_temp_file(image_path)

    return _run_paddle_on_image(ocr, file_path)


def _get_paddle_ocr() -> Any:
    global _paddle_ocr

    if _paddle_ocr is None:
        try:
            from paddleocr import PaddleOCR
        except ImportError as exc:
            raise ImportError("Install paddleocr and paddlepaddle to use PaddleOCR fallback.") from exc

        # PaddleOCR uses lang="korean" for Korean text and still handles common
        # English words/numbers in mixed Korean documents reasonably well.
        _paddle_ocr = PaddleOCR(use_textline_orientation=True, lang="korean")

    return _paddle_ocr


def _run_paddle_on_image(ocr: Any, image_path: str) -> str:
    result = ocr.ocr(image_path)
    lines: List[str] = []

    if not result:
        return ""

    for block in result:
        if not block:
            continue
        for item in block:
            if len(item) < 2:
                continue
            text_info = item[1]
            if isinstance(text_info, (list, tuple)) and text_info:
                line = str(text_info[0]).strip()
                if line:
                    lines.append(line)

    return "\n".join(lines).strip()


def _extract_pdf_text_with_pymupdf(path: Path) -> str:
    try:
        import fitz
    except ImportError as exc:
        raise ImportError("Install PyMuPDF to read PDF text.") from exc

    parts: List[str] = []
    document = fitz.open(str(path))
    try:
        for page_index, page in enumerate(document, start=1):
            page_text = (page.get_text("text") or "").strip()
            print(f"[OCR] PyMuPDF page={page_index} chars={len(page_text)}")
            if page_text:
                parts.append(page_text)
    finally:
        document.close()

    return "\n\n".join(parts).strip()


def _render_pdf_pages_to_temp_images(file_path: str, zoom: float = 2.5) -> List[str]:
    try:
        import fitz
    except ImportError as exc:
        raise ImportError("Install PyMuPDF to render PDF pages for PaddleOCR.") from exc

    image_paths: List[str] = []
    document = fitz.open(file_path)
    try:
        matrix = fitz.Matrix(zoom, zoom)
        for page_index, page in enumerate(document, start=1):
            pixmap = page.get_pixmap(matrix=matrix, alpha=False)
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=f"_page_{page_index}.png")
            temp_file.close()
            pixmap.save(temp_file.name)
            image_paths.append(temp_file.name)
    finally:
        document.close()

    return image_paths


def _detect_file(path: Path) -> tuple[Optional[str], str]:
    extension = path.suffix.lower()
    guessed_mime_type, _ = mimetypes.guess_type(str(path))

    if extension == ".pdf":
        return "pdf", guessed_mime_type or "application/pdf"

    if extension in {".jpg", ".jpeg"}:
        return "image", guessed_mime_type or "image/jpeg"

    if extension == ".png":
        return "image", guessed_mime_type or "image/png"

    return None, guessed_mime_type or ""


def is_supported_upload(filename: str, content_type: str | None = None) -> bool:
    path = Path(filename)
    _, mime_type = _detect_file(path)
    extension_ok = path.suffix.lower() in SUPPORTED_EXTENSIONS
    mime_ok = not content_type or content_type in SUPPORTED_MIME_TYPES
    detected_mime_ok = not mime_type or mime_type in SUPPORTED_MIME_TYPES
    return extension_ok and mime_ok and detected_mime_ok


def _has_enough_text(text: str) -> bool:
    return len(text.replace(" ", "").replace("\n", "")) >= PDF_TEXT_MIN_LENGTH


def _remove_temp_file(path: Optional[str]) -> None:
    if not path:
        return
    try:
        os.remove(path)
    except OSError as exc:
        print(f"[OCR] Failed to remove temp file {path}: {exc}")


def _failed_pdf_result(mime_type: str, warnings: List[str]) -> Dict[str, Any]:
    return _result(
        text="",
        engine="failed",
        fallback_used=True,
        warnings=warnings,
        file_type="pdf",
        is_text_pdf=False,
        mime_type=mime_type,
        preprocessed=False,
    )


def _result(
    text: str,
    engine: str,
    fallback_used: bool,
    warnings: List[str],
    file_type: str,
    is_text_pdf: bool,
    mime_type: str,
    preprocessed: bool,
) -> Dict[str, Any]:
    return {
        "text": text,
        "engine": engine,
        "fallback_used": fallback_used,
        "warnings": warnings,
        "metadata": {
            "file_type": file_type,
            "is_text_pdf": is_text_pdf,
            "mime_type": mime_type,
            "preprocessed": preprocessed,
        },
    }
