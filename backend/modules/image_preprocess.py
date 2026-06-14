import tempfile
from pathlib import Path
from typing import Any, Dict

import cv2


def preprocess_image_for_ocr(image_path: str) -> Dict[str, Any]:
    """Improve JPG/PNG quality before PaddleOCR and save a temporary PNG.

    This step is only used for PaddleOCR fallback. Google Document AI receives
    the original upload so we do not pay preprocessing cost unless it is needed.
    """
    source_path = Path(image_path)
    image = cv2.imread(str(source_path))
    if image is None:
        raise ValueError(f"OpenCV could not read image: {source_path}")

    original_height, original_width = image.shape[:2]

    # Convert to grayscale because OCR generally works better on one clear
    # brightness channel than on noisy color channels.
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    # Enlarge small images so small Korean and English characters become easier
    # for PaddleOCR to detect.
    longest_side = max(original_width, original_height)
    scale = 1.0
    if longest_side < 900:
        scale = 2.5
    elif longest_side < 1400:
        scale = 1.8

    if scale > 1.0:
        gray = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)

    # Remove light sensor/compression noise without destroying text strokes.
    denoised = cv2.fastNlMeansDenoising(gray, None, h=7, templateWindowSize=7, searchWindowSize=21)

    # Improve local contrast. This helps screenshots and low-contrast scans.
    clahe = cv2.createCLAHE(clipLimit=2.2, tileGridSize=(8, 8))
    contrasted = clahe.apply(denoised)

    # A mild sharpen often helps OCR separate adjacent Korean strokes.
    blurred = cv2.GaussianBlur(contrasted, (0, 0), sigmaX=0.8)
    sharpened = cv2.addWeighted(contrasted, 1.45, blurred, -0.45, 0)

    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
    temp_file.close()

    ok = cv2.imwrite(temp_file.name, sharpened)
    if not ok:
        raise ValueError(f"OpenCV could not save preprocessed image: {temp_file.name}")

    return {
        "path": temp_file.name,
        "metadata": {
            "original_width": original_width,
            "original_height": original_height,
            "scale": scale,
            "grayscale": True,
            "denoise": "fastNlMeansDenoising",
            "contrast": "CLAHE",
            "sharpen": "unsharp_mask",
        },
    }
