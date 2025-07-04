# quotes/utils.py

import asyncio
from playwright.async_api import async_playwright
import img2pdf

import asyncio
from playwright.async_api import async_playwright

async def _capture_html_as_png(html_content, output_path):
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        await page.set_content(html_content)
        await page.screenshot(path=output_path, full_page=True)
        await browser.close()

def html_to_png(html_content, output_path="/tmp/screenshot.png"):
    asyncio.run(_capture_html_as_png(html_content, output_path))
    with open(output_path, "rb") as f:
        return f.read()

def png_to_pdf(png_bytes):
    """Convert PNG bytes to PDF bytes using img2pdf."""
    return img2pdf.convert(png_bytes)

def html_to_pdf_with_chrome(html_content, pdf_options=None):
    """
    Renders the given HTML string to PDF using a headless Chromium browser.
    Returns PDF bytes.
    """
    async def run():
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            page = await browser.new_page()
            await page.set_content(html_content)  # REMOVED base_url
            pdf = await page.pdf(
                format="A4",
                print_background=True,
                margin={"top": "10mm", "bottom": "10mm", "left": "10mm", "right": "10mm"},
                **(pdf_options or {})
            )
            await browser.close()
            return pdf

    return asyncio.run(run())