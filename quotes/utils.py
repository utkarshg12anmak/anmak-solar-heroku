# quotes/utils.py

import asyncio
from pyppeteer import launch
import img2pdf

async def _capture_png(html: str) -> bytes:
    """
    Headless‐Chrome screenshot of full page.
    """
    browser = await launch(
        args=["--no-sandbox", "--disable-setuid-sandbox"]
    )
    page = await browser.newPage()
    await page.setContent(html, waitUntil="networkidle0")
    png = await page.screenshot({"fullPage": True, "type": "png"})
    await browser.close()
    return png

def html_to_png(html: str) -> bytes:
    """
    Render HTML to PNG bytes.
    """
    return asyncio.run(_capture_png(html))

def png_to_pdf(png_bytes: bytes) -> bytes:
    """
    Convert PNG bytes to a single‐page PDF.
    """
    # img2pdf.convert accepts raw PNG bytes
    return img2pdf.convert(png_bytes)
