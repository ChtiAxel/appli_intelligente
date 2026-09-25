#!/usr/bin/env python3
"""
Script de génération du Manuel Utilisateur en PDF.
Convertit MANUEL_UTILISATEUR.md en un document PDF soigné et prêt à l'impression
en s'appuyant sur Python-Markdown et Playwright Chromium.
"""

import os
import base64
import re
import markdown
from playwright.sync_api import sync_playwright

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
MD_PATH = os.path.join(ROOT_DIR, "MANUEL_UTILISATEUR.md")
PDF_PATH = os.path.join(ROOT_DIR, "MANUEL_UTILISATEUR.pdf")
DOCS_ASSETS_PDF = os.path.join(ROOT_DIR, "docs", "assets", "MANUEL_UTILISATEUR.pdf")
LOGO_PATH = os.path.join(ROOT_DIR, "docs", "assets", "logo.png")

def get_base64_logo():
    if os.path.exists(LOGO_PATH):
        with open(LOGO_PATH, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")
    return ""

def format_custom_blocks(html_content: str) -> str:
    """Améliore le rendu des blocs d'encarts de captures d'écran et citations."""
    # Transformer les citations de captures d'écran en cartes visuelles dédiées
    pattern = r'<blockquote>\s*<p>📷 <strong>\[(.*?)\]<\/strong><br \/>\s*<em>(.*?)<\/em><\/p>\s*<\/blockquote>'
    replacement = r'''
    <div class="screenshot-placeholder">
        <div class="screenshot-header">📷 \1</div>
        <div class="screenshot-desc">\2</div>
    </div>
    '''
    return re.sub(pattern, replacement, html_content, flags=re.DOTALL)

def build_html():
    with open(MD_PATH, "r", encoding="utf-8") as f:
        md_text = f.read()

    # Découper le premier titre pour la page de garde
    content_without_main_title = re.sub(r'^#\s+Manuel d\'Utilisation - NaturSQL\s*\n', '', md_text)

    # Conversion Markdown vers HTML
    html_body = markdown.markdown(
        content_without_main_title,
        extensions=[
            'tables',
            'fenced_code',
            'admonition',
            'toc',
            'nl2br'
        ]
    )

    html_body = format_custom_blocks(html_body)
    b64_logo = get_base64_logo()
    logo_img = f'<img src="data:image/png;base64,{b64_logo}" class="cover-logo" alt="Logo NaturSQL" />' if b64_logo else ""

    html_full = f"""<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <title>NaturSQL - Manuel d'Utilisation</title>
    <style>
        @page {{
            size: A4;
            margin: 22mm 16mm 22mm 16mm;
        }}

        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            color: #1f2937;
            line-height: 1.6;
            font-size: 11pt;
            background: #ffffff;
            margin: 0;
            padding: 0;
        }}

        /* Page de garde */
        .cover-page {{
            page-break-after: always;
            height: 100vh;
            display: flex;
            flex-direction: column;
            justify-content: center;
            align-items: center;
            text-align: center;
            padding: 40px 20px;
            box-sizing: border-box;
        }}

        .cover-logo {{
            height: 90px;
            margin-bottom: 25px;
        }}

        .cover-title {{
            font-size: 28pt;
            font-weight: 800;
            color: #1e3a8a;
            margin: 0 0 10px 0;
            letter-spacing: -0.5px;
        }}

        .cover-subtitle {{
            font-size: 14pt;
            color: #4b5563;
            margin-bottom: 40px;
            font-weight: 400;
        }}

        .cover-badge {{
            display: inline-block;
            background: #eff6ff;
            color: #1d4ed8;
            border: 1px solid #bfdbfe;
            padding: 6px 16px;
            border-radius: 9999px;
            font-size: 10pt;
            font-weight: 600;
            margin-bottom: 60px;
        }}

        .cover-meta {{
            margin-top: auto;
            border-top: 1px solid #e5e7eb;
            padding-top: 25px;
            width: 80%;
            font-size: 9.5pt;
            color: #6b7280;
            line-height: 1.8;
        }}

        .cover-meta strong {{
            color: #374151;
        }}

        /* Titres et structure */
        h1, h2, h3, h4 {{
            color: #111827;
            font-weight: 700;
            page-break-after: avoid;
        }}

        h2 {{
            font-size: 15pt;
            color: #1e40af;
            border-bottom: 2px solid #e2e8f0;
            padding-bottom: 6px;
            margin-top: 28px;
            margin-bottom: 14px;
            page-break-before: auto;
        }}

        h3 {{
            font-size: 12.5pt;
            color: #1f2937;
            margin-top: 20px;
            margin-bottom: 10px;
        }}

        p {{
            margin: 0 0 12px 0;
            text-align: justify;
        }}

        ul, ol {{
            margin: 0 0 14px 0;
            padding-left: 22px;
        }}

        li {{
            margin-bottom: 6px;
        }}

        /* Tableaux */
        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 18px 0;
            font-size: 9.5pt;
            page-break-inside: avoid;
        }}

        th {{
            background: #f1f5f9;
            color: #1e293b;
            font-weight: 700;
            text-align: left;
            padding: 10px 12px;
            border: 1px solid #cbd5e1;
        }}

        td {{
            padding: 8px 12px;
            border: 1px solid #e2e8f0;
            vertical-align: top;
        }}

        tr:nth-child(even) td {{
            background: #f8fafc;
        }}

        /* Citations & FAQ */
        blockquote {{
            margin: 12px 0;
            padding: 10px 16px;
            background: #f8fafc;
            border-left: 4px solid #3b82f6;
            color: #334155;
            font-size: 10pt;
            page-break-inside: avoid;
        }}

        /* Encart capture d'écran */
        .screenshot-placeholder {{
            border: 2px dashed #94a3b8;
            border-radius: 8px;
            background: #f8fafc;
            padding: 16px 20px;
            margin: 16px 0;
            text-align: center;
            page-break-inside: avoid;
        }}

        .screenshot-header {{
            font-weight: 700;
            color: #2563eb;
            font-size: 10.5pt;
            margin-bottom: 6px;
        }}

        .screenshot-desc {{
            color: #64748b;
            font-style: italic;
            font-size: 9pt;
        }}

        /* Ligne de séparation */
        hr {{
            border: none;
            border-top: 1px solid #e2e8f0;
            margin: 24px 0;
        }}

        code {{
            background: #f1f5f9;
            color: #0f172a;
            padding: 2px 6px;
            border-radius: 4px;
            font-family: Consolas, monospace;
            font-size: 9pt;
        }}
    </style>
</head>
<body>

    <!-- Page de Couverture -->
    <div class="cover-page">
        {logo_img}
        <h1 class="cover-title">NaturSQL</h1>
        <div class="cover-subtitle">Manuel d'Utilisation Officiel</div>
        <div class="cover-badge">Version 1.0 — Public Non Technique</div>

        <p style="max-width: 500px; color: #4b5563; font-size: 10.5pt; line-height: 1.7; margin-bottom: 40px;">
            Guide pratique pour l'interrogation en langage naturel des bases de données pédagogiques (services enseignants, maquettes de cours et prérequis).
        </p>

        <div class="cover-meta">
            <strong>Équipe de réalisation :</strong> Axel NAVE, Raphael DEROO, Rémy RAMPELBERGHE, Noa GAILLARD<br>
            <strong>Établissement :</strong> IUT Littoral Côte d'Opale — Département Informatique (Calais)<br>
            <strong>Module :</strong> SAE Application Intelligente & Qualité de Développement (R5-08A)
        </div>
    </div>

    <!-- Contenu du manuel -->
    <div class="content-body">
        {html_body}
    </div>

</body>
</html>
"""
    return html_full

def generate():
    print("1. Construction du document HTML stylisé...")
    html_content = build_html()

    print("2. Lancement du moteur Chromium via Playwright...")
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.set_content(html_content, wait_until="networkidle")

        print("3. Export du document PDF haute fidélité...")
        header_html = """
        <div style="font-size: 8.5pt; font-family: Segoe UI, Arial, sans-serif; color: #94a3b8; width: 100%; text-align: right; padding-right: 16mm;">
            NaturSQL — Manuel d'Utilisation
        </div>
        """

        footer_html = """
        <div style="font-size: 8.5pt; font-family: Segoe UI, Arial, sans-serif; color: #94a3b8; width: 100%; display: flex; justify-content: space-between; padding-left: 16mm; padding-right: 16mm;">
            <span>IUT Littoral Côte d'Opale</span>
            <span>Page <span class="pageNumber"></span> sur <span class="totalPages"></span></span>
        </div>
        """

        page.pdf(
            path=PDF_PATH,
            format="A4",
            print_background=True,
            display_header_footer=True,
            header_template=header_html,
            footer_template=footer_html,
            margin={
                "top": "22mm",
                "bottom": "22mm",
                "left": "16mm",
                "right": "16mm"
            }
        )

        browser.close()

    print(f"[OK] PDF genere avec succes a la racine : {PDF_PATH}")

    # Copie dans docs/assets pour telechargement direct sur le site MkDocs
    if os.path.exists(os.path.dirname(DOCS_ASSETS_PDF)):
        with open(PDF_PATH, "rb") as f_in:
            with open(DOCS_ASSETS_PDF, "wb") as f_out:
                f_out.write(f_in.read())
        print(f"[OK] PDF copie dans docs/assets/ pour le site web : {DOCS_ASSETS_PDF}")

if __name__ == "__main__":
    generate()
