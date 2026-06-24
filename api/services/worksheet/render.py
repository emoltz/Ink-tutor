"""PDF -> base64 PNG rendering (no AI)."""

from __future__ import annotations

import base64
from io import BytesIO

from PIL import Image


def render_pdf(pdf_bytes: bytes) -> str:
    """Render first page to base64 PNG."""
    try:
        import fitz
    except ImportError as exc:  # pragma: no cover - deployment config
        raise RuntimeError("Install pymupdf to render PDFs") from exc

    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    try:
        if doc.page_count == 0:
            raise ValueError("PDF has no pages")
        pix = doc.load_page(0).get_pixmap(matrix=fitz.Matrix(1.5, 1.5), alpha=False)
        image = Image.open(BytesIO(pix.tobytes("png"))).convert("RGB")
        out = BytesIO()
        image.save(out, format="PNG")
        return base64.b64encode(out.getvalue()).decode("ascii")
    finally:
        doc.close()
