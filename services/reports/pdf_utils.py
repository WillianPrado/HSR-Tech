# services/reports/pdf_utils.py

import os
import asyncio
from typing import Optional
from fpdf import FPDF
import markdown2
import pdfkit
from weasyprint import HTML
from jinja2 import Template


class PDFGeneratorService:
    """
    Service responsible for generating PDF files from plain text or Markdown content.
    Optimized for performance and flexibility — supports both WeasyPrint and PDFKit.
    """

    DEFAULT_CSS = """
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        h1, h2, h3, h4 { color: #2E4053; }
        ul { margin-left: 20px; }
        table, th, td { border: 1px solid #000; border-collapse: collapse; padding: 5px; }
        blockquote { color: #555; margin-left: 20px; font-style: italic; }
        code { background-color: #f4f4f4; padding: 2px 4px; font-family: monospace; }
    </style>
    """

    def __init__(self):
        """Initialize service with precompiled HTML template and detected wkhtmltopdf configuration."""
        self.css = self.DEFAULT_CSS
        self.template = Template("""
            <!DOCTYPE html>
            <html lang="en">
            <head>
                <meta charset="UTF-8">
                {{ css|safe }}
            </head>
            <body>
                {{ content|safe }}
            </body>
            </html>
        """)
        self.pdfkit_config = self._detect_pdfkit_config()

    # ----------------------------------------------------------------------
    # 🧩 PDFKit configuration detection
    # ----------------------------------------------------------------------
    def _detect_pdfkit_config(self) -> Optional[pdfkit.configuration]:
        """
        Detect wkhtmltopdf binary path for pdfkit, if available.

        Returns:
            Optional[pdfkit.configuration]: PDFKit configuration or None.
        """
        wkhtmltopdf_path = os.getenv("WKHTMLTOPDF_PATH")

        if wkhtmltopdf_path and os.path.isfile(wkhtmltopdf_path):
            return pdfkit.configuration(wkhtmltopdf=wkhtmltopdf_path)

        # Common installation paths
        for path in ["/usr/bin/wkhtmltopdf", "/usr/local/bin/wkhtmltopdf"]:
            if os.path.isfile(path):
                return pdfkit.configuration(wkhtmltopdf=path)

        # Windows fallback
        windows_path = r"C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe"
        if os.name == "nt" and os.path.isfile(windows_path):
            return pdfkit.configuration(wkhtmltopdf=windows_path)

        print("⚠️ wkhtmltopdf not found. Falling back to WeasyPrint.")
        return None

    # ----------------------------------------------------------------------
    # 🧾 Simple Text → PDF
    # ----------------------------------------------------------------------
    async def save_text_as_pdf(self, text: str, output_pdf: str) -> None:
        """
        Save plain text into a PDF file using FPDF (very lightweight and fast).

        Args:
            text (str): Content to be written to the PDF.
            output_pdf (str): Destination PDF path.
        """

        def _generate():
            pdf = FPDF()
            pdf.add_page()
            pdf.set_auto_page_break(auto=True, margin=15)
            pdf.set_font("Arial", size=12)

            for line in text.splitlines():
                pdf.multi_cell(0, 10, line)

            pdf.output(output_pdf)

        try:
            await asyncio.to_thread(_generate)
            print(f"✅ Simple PDF successfully saved: {output_pdf}")
        except Exception as e:
            print(f"❌ Error generating simple PDF: {e}")

    # ----------------------------------------------------------------------
    # 🎨 Markdown → PDF (Optimized)
    # ----------------------------------------------------------------------
    async def save_markdown_as_pdf(self, markdown_text: str, output_pdf: str, css: Optional[str] = None) -> None:
        """
        Converts Markdown text to a styled PDF using the fastest available engine.

        Priority:
        1. pdfkit (wkhtmltopdf) → very fast
        2. WeasyPrint → slower but pure Python fallback

        Args:
            markdown_text (str): Markdown-formatted content.
            output_pdf (str): Destination PDF path.
            css (Optional[str]): Custom CSS styling. Defaults to DEFAULT_CSS.
        """
        css = css or self.css

        # ✅ Pre-convert Markdown outside the thread (faster)
        html_content = markdown2.markdown(markdown_text)
        rendered_html = self.template.render(css=css, content=html_content)

        async def _generate_with_pdfkit():
            """Generate PDF using pdfkit (wkhtmltopdf) if available."""
            options = {
                "quiet": "",
                "enable-local-file-access": None,
                "encoding": "UTF-8",
                "page-size": "A4",
                "margin-top": "10mm",
                "margin-bottom": "10mm",
                "margin-left": "10mm",
                "margin-right": "10mm",
            }
            pdfkit.from_string(rendered_html, output_pdf, options=options, configuration=self.pdfkit_config)

        async def _generate_with_weasyprint():
            """Generate PDF using WeasyPrint as fallback."""
            def _generate():
                HTML(string=rendered_html).write_pdf(output_pdf)
            await asyncio.to_thread(_generate)

        try:
            if self.pdfkit_config:
                await asyncio.to_thread(lambda: asyncio.run(_generate_with_pdfkit()))
                print(f"✅ Visual Markdown PDF saved using PDFKit: {output_pdf}")
            else:
                await _generate_with_weasyprint()
                print(f"✅ Visual Markdown PDF saved using WeasyPrint: {output_pdf}")

        except Exception as e:
            print(f"❌ Error generating Markdown PDF: {e}")
