# services\reports\pdf_utils.py
import os
from typing import Optional
from fpdf import FPDF
import markdown2
import pdfkit
from weasyprint import HTML, CSS
from jinja2 import Template
import markdown2

# CSS global usado para PDF visual
DEFAULT_CSS_STYLE = """
<style>
    body { font-family: Arial, sans-serif; margin: 20px; }
    h1, h2, h3, h4 { color: #2E4053; }
    ul { margin-left: 20px; }
    table, th, td { border: 1px solid #000; border-collapse: collapse; padding: 5px; }
    blockquote { color: #555; margin-left: 20px; font-style: italic; }
    code { background-color: #f4f4f4; padding: 2px 4px; font-family: monospace; }
</style>
"""

def salvar_texto_em_pdf_simples(texto: str, nome_arquivo_pdf: str) -> None:
    """
    Salva um texto simples em PDF utilizando FPDF.
    """
    try:
        pdf = FPDF()
        pdf.add_page()
        pdf.set_auto_page_break(auto=True, margin=15)
        pdf.set_font("Arial", size=12)

        for linha in texto.splitlines():
            pdf.multi_cell(0, 10, linha)

        pdf.output(nome_arquivo_pdf)
        print(f"✅ PDF simples salvo com sucesso: {nome_arquivo_pdf}")
    except Exception as e:
        print(f"❌ Erro ao gerar PDF simples: {e}")

def get_pdfkit_config() -> Optional[pdfkit.configuration]:
    """
    Retorna a configuração do PDFKit com o caminho do wkhtmltopdf.
    Usa variável de ambiente ou tenta autodetectar.
    """
    wkhtmltopdf_path = os.getenv("WKHTMLTOPDF_PATH")

    if wkhtmltopdf_path:
        if not os.path.isfile(wkhtmltopdf_path):
            print(f"⚠️ Caminho inválido para wkhtmltopdf: {wkhtmltopdf_path}")
            return None
        return pdfkit.configuration(wkhtmltopdf=wkhtmltopdf_path)

    # Tentativa de autodetecção (Linux/macOS)
    for path in ["/usr/bin/wkhtmltopdf", "/usr/local/bin/wkhtmltopdf"]:
        if os.path.isfile(path):
            return pdfkit.configuration(wkhtmltopdf=path)

    # Windows fallback padrão
    windows_path = r"C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe"
    if os.name == "nt" and os.path.isfile(windows_path):
        return pdfkit.configuration(wkhtmltopdf=windows_path)

    print("❌ wkhtmltopdf não encontrado. Configure a variável de ambiente WKHTMLTOPDF_PATH.")
    return None

def salvar_markdown_em_pdf_visual(markdown_texto: str, nome_arquivo_pdf: str, css: str = DEFAULT_CSS_STYLE):
    try:
        # Converte Markdown para HTML
        html_convertido = markdown2.markdown(markdown_texto)

        # Template com estilo embutido
        html_template = Template("""
            <!DOCTYPE html>
            <html lang="pt-br">
            <head>
                <meta charset="UTF-8">
                {{ css|safe }}
            </head>
            <body>
                {{ content|safe }}
            </body>
            </html>
        """)

        html_final = html_template.render(css=css, content=html_convertido)

        HTML(string=html_final).write_pdf(nome_arquivo_pdf)
        print(f"✅ PDF salvo com sucesso com WeasyPrint: {nome_arquivo_pdf}")
    except Exception as e:
        print(f"❌ Erro ao gerar PDF com WeasyPrint: {e}")
