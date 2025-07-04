# quotes/utils.py
from io import BytesIO
from xhtml2pdf import pisa

def html_to_pdf(html: str) -> bytes:
    """
    Convert an HTML string to a PDF.
    Returns raw PDF bytes or raises ValueError on error.
    """
    buffer = BytesIO()
    status = pisa.CreatePDF(src=html, dest=buffer)
    if status.err:
        raise ValueError("xhtml2pdf failed")
    return buffer.getvalue()
