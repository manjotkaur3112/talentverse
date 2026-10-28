"""Turn uploaded files / pasted text into clean text for the LLM."""
import io

from pypdf import PdfReader

MIN_CHARS = 50
MAX_CHARS = 20_000
MAX_PDF_PAGES = 10


class InputError(Exception):
    """Bad user input (shown as a 422 with a friendly message)."""


def read_pdf(data: bytes) -> str:
    try:
        reader = PdfReader(io.BytesIO(data))
        pages = reader.pages[:MAX_PDF_PAGES]
        return "\n".join((p.extract_text() or "") for p in pages)
    except Exception as exc:
        raise InputError("This PDF could not be read. It may be corrupted or password-protected.") from exc


def clean_text(text: str, what: str = "resume") -> str:
    text = (text or "").replace("\x00", "").strip()
    if len(text) < MIN_CHARS:
        raise InputError(
            f"There is too little readable text to be a {what}. "
            "If the file is a scanned image, paste the text instead."
        )
    return text[:MAX_CHARS]
