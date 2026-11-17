import io
import logging
from PIL import Image
import pymupdf

try:
    import pytesseract
    HAS_PYTESSERACT = True
except ImportError:
    HAS_PYTESSERACT = False

logger = logging.getLogger(__name__)


def extract_text_from_pdf(file_bytes: bytes) -> str:
    """
    Extracts textual content from a PDF byte stream using PyMuPDF.
    If a page contains no text (e.g. scanned image), attempts OCR via pytesseract if available.
    """
    extracted_chunks = []
    try:
        doc = pymupdf.open(stream=file_bytes, filetype="pdf")
        for page_idx, page in enumerate(doc):
            page_text = page.get_text() or ""
            if page_text.strip():
                extracted_chunks.append(page_text.strip())
            else:
                # Scanned page fallback: render page to pixmap and run pytesseract if available
                if HAS_PYTESSERACT:
                    try:
                        pix = page.get_pixmap(dpi=150)
                        img = Image.open(io.BytesIO(pix.tobytes("png")))
                        ocr_text = pytesseract.image_to_string(img)
                        if ocr_text.strip():
                            extracted_chunks.append(ocr_text.strip())
                    except Exception as ocr_err:
                        logger.debug(f"Page {page_idx} OCR fallback skipped: {str(ocr_err)}")
    except Exception as e:
        logger.exception(f"PDF text extraction failed: {str(e)}")

    return "\n\n".join(extracted_chunks)


def extract_text_from_image(file_bytes: bytes) -> str:
    """
    Extracts text from PNG/JPEG image using pytesseract if available.
    """
    if not HAS_PYTESSERACT:
        return ""

    try:
        img = Image.open(io.BytesIO(file_bytes))
        text = pytesseract.image_to_string(img)
        return text.strip()
    except Exception as e:
        logger.debug(f"Image OCR skipped or failed: {str(e)}")
        return ""


def extract_text(file_bytes: bytes, content_type: str, filename: str) -> str:
    """
    Unified extractor: Dispatches based on content_type and filename extension.
    """
    lower_name = (filename or "").lower()
    if content_type == "application/pdf" or lower_name.endswith(".pdf"):
        return extract_text_from_pdf(file_bytes)
    elif content_type in ["image/png", "image/jpeg", "image/jpg"] or any(
        lower_name.endswith(ext) for ext in [".png", ".jpg", ".jpeg"]
    ):
        return extract_text_from_image(file_bytes)
    return ""
