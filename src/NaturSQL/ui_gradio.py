"""Gradio application entry point."""

from __future__ import annotations
import asyncio
import os
import base64
import html
import re
import csv
import tempfile
from datetime import datetime
import gradio as gr
from .service.auth import AuthService
from .storage.conversations import ConversationStorage
from .service.core import ask_database
from .service.monitoring import get_system_status
from .ollama_client.llm import LLMClient

def load_markdown(filename: str) -> str:
    candidates = [
        os.path.join(os.path.dirname(__file__), "docs", "legal", filename),
        os.path.join(os.path.dirname(__file__), "docs", filename),
        os.path.join(os.path.dirname(__file__), "..", "..", filename),
    ]
    for path in candidates:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return f.read()
    return f"Fichier {filename} introuvable."

# Load logo as base64 for embedding in HTML
logo_path = os.path.join(os.path.dirname(__file__), "..", "..", "docs", "assets", "logo.png")
try:
    with open(logo_path, "rb") as f:
        b64_logo = base64.b64encode(f.read()).decode("utf-8")
    logo_html = f'<a href="#" style="text-decoration: none;" onclick="document.getElementById(\'btn-go-home\').click(); return false;"><div style="display: flex; align-items: center; gap: 10px;"><img src="data:image/png;base64,{b64_logo}" style="height: 32px;" /> <h2 style="margin:0; font-weight:600; color:black;">NaturSQL</h2></div></a>'
except Exception:
    b64_logo = ""
    logo_html = '<a href="#" style="text-decoration: none;" onclick="document.getElementById(\'btn-go-home\').click(); return false;"><h2 style="margin:0; font-weight:600; color:black;">NaturSQL</h2></a>'

# Script to remove dark mode forcefully from Gradio
force_light_mode_js = """
function() {
    document.body.classList.remove('dark');
}
"""

custom_css = """
html, body {
    margin: 0 !important;
    padding: 0 !important;
    background-color: #f8f9fa !important;
    min-height: 100vh;
}
.gradio-container {
    padding: 0 !important;
    margin: 0 !important;
    max-width: 100% !important;
}
.gradio-container > .main, .gradio-container > .main > .wrap {
    padding: 0 !important;
    margin: 0 !important;
    max-width: 100% !important;
}
.header {
    background: white;
    padding-top: 2.5rem !important;
    padding-bottom: 1.5rem !important;
    padding-left: 2rem;
    padding-right: 2rem;
    border-bottom: 1px solid #e5e7eb;
    width: 100vw;
    margin-left: calc(-50vw + 50%) !important;
    margin-top: -1rem !important;
    box-sizing: border-box;
    margin-bottom: 0 !important;
}
.main-content {
    min-height: calc(100vh - 320px); 
}
.auth-card {
    background: white;
    padding: 2.5rem;
    border-radius: 0.5rem;
    box-shadow: 0 4px 10px rgba(0, 0, 0, 0.05);
    margin: 3rem auto 0 auto;
    max-width: 450px;
}
.profile-card {
    background: #ffffff !important;
    padding: 2rem 2.25rem !important;
    border-radius: 12px !important;
    box-shadow: 0 4px 14px rgba(0, 0, 0, 0.05) !important;
    margin: 2rem auto !important;
    max-width: 480px !important;
    border: 1px solid #e5e7eb !important;
}
.profile-header {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    text-align: center;
    margin-bottom: 0.85rem;
    width: 100%;
}
.profile-avatar {
    width: 64px;
    height: 64px;
    border-radius: 50%;
    background: #111827;
    color: #ffffff;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 22px;
    font-weight: 700;
    margin: 0 auto 8px auto;
    box-shadow: 0 4px 8px rgba(0, 0, 0, 0.1);
    letter-spacing: 1px;
}
.profile-name {
    font-size: 22px;
    font-weight: 700;
    color: #111827;
    margin: 0 0 3px 0;
    line-height: 1.25;
    text-align: center;
}
.profile-id {
    font-size: 13px;
    font-weight: 500;
    color: #374151;
    background: #f3f4f6;
    padding: 2px 12px;
    border-radius: 9999px;
    margin: 2px 0 5px 0;
    display: inline-block;
    text-align: center;
}
.profile-role {
    font-size: 13px;
    font-weight: 500;
    color: #6b7280;
    margin: 0;
    text-align: center;
}
.profile-accordion {
    border: 1px solid #e5e7eb !important;
    border-radius: 8px !important;
    margin: 0.75rem 0 !important;
    background: #fafafa !important;
    padding: 0.5rem 0.75rem !important;
}
.profile-btn-row {
    display: flex !important;
    flex-direction: row !important;
    justify-content: center !important;
    align-items: center !important;
    gap: 12px !important;
    width: 100% !important;
    margin-top: 1rem !important;
}
.profile-btn-row button {
    flex: 1 1 0 !important;
    max-width: 190px !important;
}
.profile-back-row {
    display: flex !important;
    justify-content: center !important;
    align-items: center !important;
    width: 100% !important;
    margin-top: 0.5rem !important;
}
.profile-back-row button {
    background: none !important;
    border: none !important;
    box-shadow: none !important;
    color: #6b7280 !important;
    text-decoration: underline !important;
    font-size: 13px !important;
    cursor: pointer !important;
    padding: 4px 8px !important;
    min-width: 0 !important;
}
.profile-back-row button:hover {
    color: #111827 !important;
}
.profile-edit-actions {
    display: flex !important;
    flex-direction: row !important;
    justify-content: center !important;
    gap: 10px !important;
    margin-top: 0.75rem !important;
}
.profile-edit-actions button {
    flex: 1 1 0 !important;
    max-width: 160px !important;
}
.doc-card {
    background: white;
    padding: 2.5rem;
    border-radius: 0.5rem;
    box-shadow: 0 4px 10px rgba(0, 0, 0, 0.05);
    margin: 0 auto;
    max-width: 850px;
}
.footer {
    background: white;
    padding-top: 2rem !important;
    padding-bottom: 3rem !important;
    padding-left: 2rem;
    padding-right: 2rem;
    border-top: 1px solid #e5e7eb;
    width: 100vw;
    margin-left: calc(-50vw + 50%) !important;
    margin-bottom: -1rem !important; 
    margin-top: auto !important;
    box-sizing: border-box;
}
footer.svelte-17lrt0r, footer.svelte-1rjryqp, footer {
    display: none !important;
}
.auth-links {
    display: flex;
    justify-content: center;
    align-items: center;
    margin-top: 12px !important;
}
.auth-links button {
    background: none !important;
    border: none !important;
    box-shadow: none !important;
    color: #111111 !important;
    text-decoration: underline !important;
    font-size: 12px !important;
    padding: 0 !important;
    min-width: 0 !important;
}
.status-msg { min-height: 20px; font-size: 13px; margin-top: 8px; }
.status-msg.error { color: #d64545 !important; }
.status-msg.ok { color: #2e8b57 !important; font-weight: 600; }
.hidden-btn { display: none !important; }

/* --- Cacher la boîte de chargement Processing --- */
.progress-text { display: none !important; }
.toast-wrap { display: none !important; }
div[class*="progress-text"] { display: none !important; }

/* --- Conversation Page CSS --- */
#conv-page {
    display: flex;
    flex-direction: row;
    width: 100vw;
    margin-left: calc(-50vw + 50%) !important;
    height: calc(100vh - 132px); /* Fill space without grey band */
    background: #f8f9fa;
    border-top: 1px solid #e5e7eb;
}
#conv-sidebar {
    width: 260px;
    background: #fafafa;
    border-right: 1px solid #e5e7eb;
    display: flex;
    flex-direction: column;
    padding: 16px;
    height: 100%;
}
#conv-main {
    flex-grow: 1;
    display: flex;
    flex-direction: column;
    background: white;
    padding: 24px;
    height: 100%;
}
#conv-chat {
    flex-grow: 1;
    overflow-y: auto;
    margin-bottom: 16px;
}
.message-buttons { display: none !important; }
.message-row .button-wrap { display: none !important; }
.message-wrap .message-row button { display: none !important; }
#conv-input-row {
    position: relative;
    border: 1px solid #e5e7eb;
    border-radius: 24px;
    background: #ffffff;
    align-items: center;
    padding: 4px 8px;
    box-shadow: 0 2px 6px rgba(0,0,0,0.05);
}
#conv-input-row textarea {
    border: none !important;
    box-shadow: none !important;
    background: transparent !important;
    padding-top: 12px !important;
}
#conv-input-row .send-btn {
    border-radius: 50% !important;
    width: 36px !important;
    height: 36px !important;
    min-width: 36px !important;
    padding: 0 !important;
    margin: 0 4px 0 0 !important;
    display: flex;
    justify-content: center;
    align-items: center;
    background: #111827 !important;
    color: white !important;
    border: none !important;
}
.sidebar-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    font-weight: 600;
    margin-bottom: 16px;
}
.new-chat-btn {
    background: none !important;
    border: none !important;
    font-size: 24px !important;
    cursor: pointer;
    box-shadow: none !important;
    padding: 0 4px !important;
    min-width: 0 !important;
    line-height: 1 !important;
    color: #374151 !important;
}
.new-chat-btn:hover {
    color: #000000 !important;
}
.chat-list-title {
    font-size: 12px;
    color: #6b7280;
    margin-bottom: 8px;
    padding-left: 4px;
}
.chat-list {
    flex-grow: 1;
    overflow-y: auto;
    background: transparent !important;
    border: none !important;
}
.chat-list .wrap {
    display: flex !important;
    flex-direction: column !important;
    gap: 2px !important;
    border: none !important;
    background: transparent !important;
    box-shadow: none !important;
}
.chat-list label {
    display: block !important;
    padding: 10px 12px !important;
    cursor: pointer !important;
    border-radius: 8px !important;
    border: none !important;
    background: transparent !important;
    margin-bottom: 2px !important;
    box-shadow: none !important;
    width: 100% !important;
    box-sizing: border-box !important;
}
.chat-list label:hover {
    background: #e5e7eb !important;
}
.chat-list label.selected {
    background: #e5e7eb !important;
    font-weight: 600 !important;
}
.chat-list input[type="radio"] {
    display: none !important;
}
.chat-list input[type="radio"] + span::before {
    display: none !important; /* Hide radio circle */
}
.chat-list span {
    margin-left: 0 !important;
    display: block !important;
    white-space: nowrap !important;
    overflow: hidden !important;
    text-overflow: ellipsis !important;
    font-size: 13px !important;
    color: #374151 !important;
}
.profile-link-btn {
    background: none !important;
    border: none !important;
    box-shadow: none !important;
    padding: 0 !important;
    color: inherit !important;
    min-width: 0 !important;
    text-align: left !important;
}
.header-profile-row {
    display: flex !important;
    align-items: center !important;
    justify-content: flex-end !important;
    gap: 8px !important;
    margin: 0 !important;
    padding: 0 !important;
}
.system-status-container {
    display: flex !important;
    flex-direction: row !important;
    align-items: center !important;
    justify-content: center !important;
    gap: 16px !important;
    font-size: 12px !important;
    color: #4b5563 !important;
    padding: 6px 14px !important;
    background: #f9fafb !important;
    border: 1px solid #e5e7eb !important;
    border-radius: 6px !important;
    width: fit-content !important;
    margin: 0 2rem 0 auto !important;
}
.status-indicator {
    display: flex !important;
    align-items: center !important;
    gap: 6px !important;
    white-space: nowrap !important;
}
.status-dot {
    width: 8px !important;
    height: 8px !important;
    border-radius: 50% !important;
    display: inline-block !important;
}
.status-dot-online {
    background-color: #10b981 !important;
    box-shadow: 0 0 0 2px rgba(16, 185, 129, 0.2) !important;
}
.status-dot-offline {
    background-color: #ef4444 !important;
    box-shadow: 0 0 0 2px rgba(239, 68, 68, 0.2) !important;
}
.welcome-box {
    text-align: center !important;
    max-width: 680px !important;
    margin: 16px auto !important;
    padding: 24px !important;
    background: #ffffff !important;
    border: 1px solid #e5e7eb !important;
    border-radius: 12px !important;
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05) !important;
}
.welcome-title {
    font-size: 20px !important;
    font-weight: 600 !important;
    color: #111827 !important;
    margin: 0 0 8px 0 !important;
}
.welcome-subtitle {
    font-size: 14px !important;
    color: #6b7280 !important;
    margin: 0 0 16px 0 !important;
}
.tips-accordion {
    text-align: left !important;
    margin-top: 14px !important;
    border: 1px solid #e5e7eb !important;
    border-radius: 8px !important;
    background: #f9fafb !important;
    overflow: hidden !important;
}
.tips-summary {
    font-size: 13px !important;
    font-weight: 600 !important;
    color: #374151 !important;
    padding: 10px 14px !important;
    cursor: pointer !important;
    user-select: none !important;
    outline: none !important;
}
.tips-summary:hover {
    background: #f3f4f6 !important;
}
.tips-content {
    padding: 12px 16px !important;
    font-size: 13px !important;
    color: #4b5563 !important;
    line-height: 1.6 !important;
    border-top: 1px solid #e5e7eb !important;
    background: #ffffff !important;
}
.tips-content ul {
    margin: 0 !important;
    padding-left: 20px !important;
}
.tips-content li {
    margin-bottom: 6px !important;
}
.chat-toolbar {
    display: flex !important;
    justify-content: space-between !important;
    align-items: center !important;
    margin-bottom: 8px !important;
    padding-bottom: 6px !important;
    border-bottom: 1px solid #f3f4f6 !important;
}
.view-mode-toggle .wrap {
    display: flex !important;
    flex-direction: row !important;
    gap: 6px !important;
    border: none !important;
    background: transparent !important;
    box-shadow: none !important;
}
.view-mode-toggle label {
    font-size: 12px !important;
    padding: 4px 10px !important;
    border-radius: 6px !important;
    border: 1px solid #e5e7eb !important;
    background: #ffffff !important;
    cursor: pointer !important;
}
.view-mode-toggle label.selected {
    background: #374151 !important;
    color: #ffffff !important;
    font-weight: 500 !important;
}
.csv-download-btn {
    font-size: 12px !important;
    padding: 4px 12px !important;
    background: #111827 !important;
    color: #ffffff !important;
    border-radius: 6px !important;
    border: none !important;
}
.active-conv-actions {
    background: #f9fafb !important;
    border: 1px solid #e5e7eb !important;
    border-radius: 8px !important;
    padding: 8px 10px !important;
    margin-top: 6px !important;
    margin-bottom: 6px !important;
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05) !important;
}
.active-conv-actions input {
    font-size: 12px !important;
    padding: 4px 8px !important;
    background: #ffffff !important;
    border: 1px solid #d1d5db !important;
    border-radius: 4px !important;
    margin-bottom: 6px !important;
}
.action-box-title {
    font-size: 11px !important;
    font-weight: 600 !important;
    color: #4b5563 !important;
    margin-bottom: 6px !important;
    display: flex !important;
    align-items: center !important;
    justify-content: space-between !important;
}
.delete-btn-hover {
    color: #b91c1c !important;
    background: #fef2f2 !important;
    border: 1px solid #fecaca !important;
    transition: all 0.2s ease-in-out !important;
    font-size: 12px !important;
    padding: 2px 8px !important;
}
.delete-btn-hover:hover {
    background: #dc2626 !important;
    color: #ffffff !important;
    border-color: #dc2626 !important;
}
.clear-all-convs-btn {
    font-size: 11px !important;
    padding: 6px 10px !important;
    margin-top: 8px !important;
    color: #6b7280 !important;
    background: transparent !important;
    border: 1px dashed #d1d5db !important;
    width: 100% !important;
    cursor: pointer !important;
}
.clear-all-convs-btn:hover {
    color: #dc2626 !important;
    border-color: #dc2626 !important;
    background: #fef2f2 !important;
}
"""

theme = gr.themes.Default(
    primary_hue="gray",
    neutral_hue="slate",
).set(
    body_background_fill="#f8f9fa",
    block_background_fill="#ffffff",
    block_border_color="#e5e7eb",
    block_border_width="1px",
    block_shadow="none",
    button_primary_background_fill="#374151",
    button_primary_background_fill_hover="#1f2937",
    button_primary_text_color="#ffffff",
    button_cancel_background_fill="#ef4444",
    button_cancel_background_fill_hover="#dc2626",
    button_cancel_text_color="#ffffff",
    color_accent_soft="#f3f4f6",
)

def _status_html(message: str, ok: bool) -> str:
    if not message:
        return ""
    css_class = "status-msg ok" if ok else "status-msg error"
    return f'<div class="{css_class}">{message}</div>'

def _profile_card_html(user) -> str:
    if not user:
        return (
            '<div class="profile-header">'
            '<div class="profile-role">Erreur de chargement</div>'
            '</div>'
        )
    prenom = " ".join((getattr(user, "prenom", "") or "").split())
    nom = " ".join((getattr(user, "nom", "") or "").split())
    full_name = f"{prenom} {nom}".strip() or "Utilisateur"

    if prenom and nom:
        clean_prenom = re.sub(r"\s+", "-", prenom.lower())
        clean_nom = re.sub(r"\s+", "-", nom.lower())
        identifiant = f"{clean_prenom}.{clean_nom}"
        initials = f"{prenom[0].upper()}{nom[0].upper()}"
    else:
        nom_util = getattr(user, "nom_util", "") or ""
        identifiant = nom_util.strip(".") or full_name.lower().replace(" ", "-") or "utilisateur"
        initials = full_name[0].upper() if full_name else "U"

    escaped_full_name = html.escape(full_name)
    escaped_id = html.escape(identifiant)
    escaped_initials = html.escape(initials)

    return (
        '<div class="profile-header">\n'
        f'    <div class="profile-avatar">{escaped_initials}</div>\n'
        f'    <div class="profile-name">{escaped_full_name}</div>\n'
        f'    <div class="profile-id">{escaped_id}</div>\n'
        '    <div class="profile-role">Utilisateur Standard</div>\n'
        '</div>'
    )

_profile_card_md = _profile_card_html


def create_results_csv(results: list[dict]) -> str | None:
    """Generate a temporary CSV file formatted for Excel."""
    if not results:
        return None
    tmp = tempfile.NamedTemporaryFile(
        delete=False, suffix=".csv", prefix="natursql_export_", mode="w", encoding="utf-8-sig", newline=""
    )
    headers = list(results[0].keys())
    writer = csv.DictWriter(tmp, fieldnames=headers, delimiter=";")
    writer.writeheader()
    for row in results:
        writer.writerow(row)
    tmp.close()
    return tmp.name


def _status_badges_html() -> str:
    """Return HTML status indicators for MariaDB and Ollama without emoji."""
    status = get_system_status()
    db_ok = status.get("mariadb", False)
    ollama_ok = status.get("ollama", False)

    db_class = "status-dot-online" if db_ok else "status-dot-offline"
    db_text = "En ligne" if db_ok else "Hors ligne"

    ollama_class = "status-dot-online" if ollama_ok else "status-dot-offline"
    ollama_text = "Pret" if ollama_ok else "Indisponible"

    return (
        '<div class="system-status-container">\n'
        '    <div class="status-indicator">\n'
        f'        <span class="status-dot {db_class}"></span>\n'
        f'        <span>Base de donnees (MariaDB) : {db_text}</span>\n'
        '    </div>\n'
        '    <div class="status-indicator">\n'
        f'        <span class="status-dot {ollama_class}"></span>\n'
        f'        <span>Serveur IA (Ollama) : {ollama_text}</span>\n'
        '    </div>\n'
        '</div>'
    )


def _welcome_banner_html(user=None, include_tips=True) -> str:
    """Return welcome box without emoji (kept for test compatibility)."""
    prenom = getattr(user, "prenom", "") if user else ""
    prenom_str = html.escape(prenom.strip()) if prenom else "Utilisateur"
    tips_block = ""
    if include_tips:
        tips_block = (
            '    <details class="tips-accordion">\n'
            '        <summary class="tips-summary">Conseils de formulation</summary>\n'
            '        <div class="tips-content">\n'
            '            <ul>\n'
            '                <li><strong>Precisez les intitules :</strong> Indiquez le nom complet du cours ou de la matiere (ex. Qualite de developpement).</li>\n'
            '                <li><strong>Specifiez le type de seance :</strong> Ciblez les cours magistraux (CM), travaux diriges (TD) ou travaux pratiques (TP).</li>\n'
            '                <li><strong>Evitez les abreviations :</strong> Formulez clairement votre demande pour optimiser la generation de la requete SQL.</li>\n'
            '                <li><strong>Exemples de questions types :</strong>\n'
            '                    <ul>\n'
            '                        <li>Quels enseignants donnent des TP dans le cours Qualite de developpement ?</li>\n'
            '                        <li>Quel est le volume d\'heures de cours magistraux dispense par enseignant ?</li>\n'
            '                        <li>Quelles sont les matieres dispensees au semestre 1 ?</li>\n'
            '                        <li>Donne-moi la liste des enseignants vacataires.</li>\n'
            '                    </ul>\n'
            '                </li>\n'
            '            </ul>\n'
            '        </div>\n'
            '    </details>\n'
        )
    return (
        '<div class="welcome-box">\n'
        f'    <h2 class="welcome-title">Bonjour {prenom_str}, que souhaitez-vous analyser aujourd\'hui ?</h2>\n'
        '    <p class="welcome-subtitle">Posez vos questions sur les maquettes pedagogiques, les volumes horaires et les plannings en langage naturel.</p>\n'
        f'{tips_block}'
        '</div>'
    )


def get_conv_period(dt: datetime) -> str:
    """Classify conversation creation date into period categories."""
    diff = (datetime.now().date() - dt.date()).days
    if diff == 0:
        return "Aujourd'hui"
    elif diff <= 7:
        return "7 derniers jours"
    return "Plus ancien"


def _format_bot_response(sql: str | None, results: list[dict] | None, simplified: bool = False) -> str:
    """Format query, French synthesis, and SQL results table into Markdown."""
    if not sql and not results:
        return "Desole, je n'ai pas pu comprendre la demande ou aucune donnee n'a ete trouvee."
    
    md_parts = []
    if sql and not simplified:
        lines = sql.strip().split("\n")
        code_lines = [f"{i+1:>3} │ {line}" for i, line in enumerate(lines)]
        md_parts.append(f"```sql\n{chr(10).join(code_lines)}\n```")
    
    if results:
        headers = list(results[0].keys())
        active_headers = []
        for h in headers:
            if any(row.get(h) is not None and str(row.get(h)).strip() != "" for row in results):
                active_headers.append(h)
        
        if not active_headers:
            active_headers = headers
            
        display_headers = [h.replace("_", " ").title() for h in active_headers]

        # Tableau Markdown des resultats
        table_lines = []
        table_lines.append("| " + " | ".join(display_headers) + " |")
        table_lines.append("|" + "|".join(["---"] * len(active_headers)) + "|")
        for i, row in enumerate(results):
            if i >= 50:
                table_lines.append(f"*... {len(results)-50} resultats supplementaires masques ...*")
                break
            r_str = []
            for h in active_headers:
                val = row.get(h)
                if val is None or str(val).strip() == "" or str(val) == "None":
                    r_str.append("-")
                else:
                    r_str.append(str(val).replace("|", "\\|"))
            table_lines.append("| " + " | ".join(r_str) + " |")
        md_parts.append("\n".join(table_lines))
    else:
        md_parts.append("\n*Aucun resultat trouve.*")
        
    return "\n\n".join(md_parts)


def build_app():
    auth_service = AuthService()
    conv_storage = ConversationStorage()
    conv_storage.ensure_schema()

    with gr.Blocks(title="NaturSQL Profile") as demo:
        session_user = gr.State(None)
        current_conv_id = gr.State(None)
        conv_id_map = gr.State({})  # maps radio choices to DB IDs

        # En-tête (Header)
        with gr.Column(elem_classes=["header"]):
            with gr.Row():
                gr.HTML(logo_html, scale=1)
                with gr.Row(elem_classes=["header-profile-row"], visible=False) as header_profile_container:
                    header_user_name = gr.HTML(elem_classes=["header-user-html"])
                    go_to_profile_btn = gr.Button("Mon Profil", variant="secondary", size="sm")

        # Contenu principal
        with gr.Column(elem_classes=["main-content"]):
            
            # --- Page de Connexion ---
            with gr.Column(visible=True) as signin_page:
                with gr.Column(elem_classes=["auth-card"]):
                    gr.Markdown("### Sign In", elem_classes=["text-center"])
                    gr.HTML('<div style="font-size:11px;color:#888;margin:-6px 0 10px 0;">Tous les champs sont obligatoires.</div>')
                    
                    signin_first_name = gr.Textbox(label="Prénom *", placeholder="Jean")
                    signin_last_name = gr.Textbox(label="Nom *", placeholder="Dupont")
                    signin_password = gr.Textbox(label="Mot de passe *", type="password", placeholder="Mot de passe")
                    
                    signin_status = gr.HTML()
                    signin_button = gr.Button("Se connecter", variant="primary")
                    
                    with gr.Row(elem_classes=["auth-links"]):
                        go_to_signup = gr.Button("Créer un compte")
            
            # --- Page d'Inscription ---
            with gr.Column(visible=False) as signup_page:
                with gr.Column(elem_classes=["auth-card"]):
                    gr.Markdown("### Sign Up", elem_classes=["text-center"])
                    gr.HTML('<div style="font-size:11px;color:#888;margin:-6px 0 10px 0;">Tous les champs sont obligatoires.</div>')
                    
                    signup_first_name = gr.Textbox(label="Prénom *", placeholder="Jean")
                    signup_last_name = gr.Textbox(label="Nom *", placeholder="Dupont")
                    signup_password = gr.Textbox(label="Mot de passe *", type="password", placeholder="Mot de passe", info="8 caractères min., 1 majuscule, 1 chiffre, 1 caractère spécial.")
                    signup_confirm = gr.Textbox(label="Confirmer le mot de passe *", type="password", placeholder="Confirmer le mot de passe")
                    
                    signup_status = gr.HTML()
                    signup_button = gr.Button("S'inscrire", variant="primary")
                    
                    with gr.Row(elem_classes=["auth-links"]):
                        go_to_signin = gr.Button("Se connecter")

            # --- Page de Profil ---
            with gr.Column(visible=False, elem_classes=["profile-card"]) as profile_page:
                profile_info = gr.HTML(
                    value='<div class="profile-header"><div class="profile-role">Chargement du profil...</div></div>'
                )
                profile_status = gr.HTML()

                with gr.Accordion("Modifier mes informations", open=True, visible=False, elem_classes=["profile-accordion"]) as profile_edit_form:
                    with gr.Row():
                        edit_first_name = gr.Textbox(label="Prénom *", placeholder="Jean", lines=1, max_lines=1, scale=1)
                        edit_last_name = gr.Textbox(label="Nom *", placeholder="Dupont", lines=1, max_lines=1, scale=1)
                    with gr.Row(elem_classes=["profile-edit-actions"]):
                        save_profile_button = gr.Button("Enregistrer", variant="primary", scale=1)
                        cancel_profile_button = gr.Button("Annuler", variant="secondary", scale=1)

                with gr.Row(elem_classes=["profile-btn-row"]):
                    edit_profile_button = gr.Button("Modifier le profil", variant="primary")
                    disconnect_button = gr.Button("Déconnexion", variant="stop")

                with gr.Row(elem_classes=["profile-back-row"]):
                    btn_back_to_conv = gr.Button("← Retour aux conversations", size="sm")

            # --- Pages Légales ---
            with gr.Column(visible=False, elem_classes=["profile-card"]) as legal_mentions_page:
                gr.Markdown(load_markdown("mentions-legales.md"))
                btn_back_1 = gr.Button("Retour")
                
            with gr.Column(visible=False, elem_classes=["profile-card"]) as legal_privacy_page:
                gr.Markdown(load_markdown("politique-confidentialite.md"))
                btn_back_2 = gr.Button("Retour")
                
            with gr.Column(visible=False, elem_classes=["profile-card"]) as legal_cgu_page:
                gr.Markdown(load_markdown("conditions-generales-utilisation.md"))
                btn_back_3 = gr.Button("Retour")

            with gr.Column(visible=False, elem_id="conv-page") as conversation_page:
                with gr.Column(elem_id="conv-sidebar"):
                    with gr.Row(elem_classes=["sidebar-header"]):
                        gr.HTML("<div style='flex-grow: 1; margin: 0; padding: 0;'>NaturSQL</div>", scale=1)
                        new_chat_btn = gr.Button("+", elem_classes=["new-chat-btn"], scale=0, min_width=30)

                    gr.HTML('<div class="chat-list-title">Discussions</div>')
                    
                    conv_radio = gr.Radio(choices=[], show_label=False, container=False, elem_classes=["chat-list"])

                    with gr.Column(elem_classes=["active-conv-actions"], visible=False) as active_conv_box:
                        gr.HTML('<div class="action-box-title">Gestion de la discussion</div>')
                        rename_title_input = gr.Textbox(placeholder="Nouveau titre...", show_label=False, container=False, lines=1)
                        with gr.Row():
                            btn_rename_confirm = gr.Button("Renommer", size="sm", variant="secondary", scale=1)
                            btn_delete_confirm = gr.Button("Supprimer", size="sm", variant="stop", elem_classes=["delete-btn-hover"], scale=1)

                with gr.Column(elem_id="conv-main"):
                    welcome_box = gr.HTML("", elem_classes=["welcome-container"], visible=False)

                    with gr.Row(elem_classes=["chat-toolbar"]):
                        with gr.Row(elem_classes=["chat-toolbar-left"]):
                            view_mode = gr.Radio(
                                choices=["Avec SQL", "Sans SQL"],
                                value="Avec SQL",
                                label="",
                                container=False,
                                elem_classes=["view-mode-toggle"],
                            )
                        with gr.Row(elem_classes=["chat-toolbar-right"]):
                            csv_download_btn = gr.DownloadButton(
                                "Telecharger en CSV",
                                size="sm",
                                visible=False,
                                elem_classes=["csv-download-btn"],
                            )

                    chatbot = gr.Chatbot(
                        elem_id="conv-chat",
                        show_label=False,
                        buttons=[],
                        feedback_options=None
                    )
                    with gr.Row(elem_id="conv-input-row"):
                        chat_input = gr.Textbox(
                            placeholder="Posez votre question sur les enseignements...",
                            show_label=False,
                            container=False,
                            scale=9
                        )
                        send_btn = gr.Button("↑", elem_classes=["send-btn"], scale=0)

            # --- Page de Documentation Utilisateur ---
            with gr.Column(visible=False, elem_classes=["doc-card"]) as doc_page:
                gr.Markdown(load_markdown("documentation_utilisateur.md"))
                btn_back_doc = gr.Button("Retour")

        # Pied de page (Footer)
        with gr.Column(elem_classes=["footer"]):
            footer_logo = f'<a href="#" style="text-decoration: none;" onclick="document.getElementById(\'btn-go-home\').click(); return false;"><img src="data:image/png;base64,{b64_logo}" style="height: 48px; margin-right: 4rem;" /></a>' if b64_logo else ""
                
            with gr.Row():
                gr.HTML(f"""
                <div style='display: flex; align-items: flex-start; padding-left: 2rem; gap: 4rem;'>
                    <div>
                        {footer_logo}
                    </div>
                    <div style='line-height: 1.8; color: #1f2937;'>
                        <strong>Aide</strong><br>
                        <a href="#" style="color: #1f2937; text-decoration: none;" onclick="document.getElementById('btn-show-doc').click(); return false;">Documentation</a>
                    </div>
                    <div style='line-height: 1.8; color: #1f2937;'>
                        <strong>Legal</strong><br>
                        <a href="#" style="color: #1f2937; text-decoration: none;" onclick="document.getElementById('btn-show-mentions').click(); return false;">Mentions legales</a><br>
                        <a href="#" style="color: #1f2937; text-decoration: none;" onclick="document.getElementById('btn-show-privacy').click(); return false;">Politique de confidentialite</a><br>
                        <a href="#" style="color: #1f2937; text-decoration: none;" onclick="document.getElementById('btn-show-cgu').click(); return false;">Conditions generales d'utilisation</a>
                    </div>
                </div>
                """, scale=3)
                system_status_box = gr.HTML(_status_badges_html(), scale=1)
            
            # Boutons invisibles pour déclencher l'affichage des pages depuis le footer HTML
            btn_go_home = gr.Button(elem_id="btn-go-home", elem_classes=["hidden-btn"])
            btn_show_doc = gr.Button(elem_id="btn-show-doc", elem_classes=["hidden-btn"])
            btn_show_mentions = gr.Button(elem_id="btn-show-mentions", elem_classes=["hidden-btn"])
            btn_show_privacy = gr.Button(elem_id="btn-show-privacy", elem_classes=["hidden-btn"])
            btn_show_cgu = gr.Button(elem_id="btn-show-cgu", elem_classes=["hidden-btn"])

        # --- Callbacks ---

        def go_to_page(page_name, session):
            s_in = s_up = prof = leg_m = leg_p = leg_c = doc = conv = gr.update(visible=False)
            if page_name == "mentions": leg_m = gr.update(visible=True)
            elif page_name == "privacy": leg_p = gr.update(visible=True)
            elif page_name == "cgu": leg_c = gr.update(visible=True)
            elif page_name == "doc": doc = gr.update(visible=True)
            elif page_name == "home":
                if session is None: s_in = gr.update(visible=True)
                else: conv = gr.update(visible=True)
            elif page_name == "profile":
                if session is not None: prof = gr.update(visible=True)
            return s_in, s_up, prof, leg_m, leg_p, leg_c, doc, conv

        page_outputs = [signin_page, signup_page, profile_page, legal_mentions_page, legal_privacy_page, legal_cgu_page, doc_page, conversation_page]
        
        btn_go_home.click(lambda s: go_to_page("home", s), inputs=[session_user], outputs=page_outputs)
        btn_show_doc.click(lambda s: go_to_page("doc", s), inputs=[session_user], outputs=page_outputs)
        btn_show_mentions.click(lambda s: go_to_page("mentions", s), inputs=[session_user], outputs=page_outputs)
        btn_show_privacy.click(lambda s: go_to_page("privacy", s), inputs=[session_user], outputs=page_outputs)
        btn_show_cgu.click(lambda s: go_to_page("cgu", s), inputs=[session_user], outputs=page_outputs)
        
        btn_back_1.click(lambda s: go_to_page("home", s), inputs=[session_user], outputs=page_outputs)
        btn_back_2.click(lambda s: go_to_page("home", s), inputs=[session_user], outputs=page_outputs)
        btn_back_3.click(lambda s: go_to_page("home", s), inputs=[session_user], outputs=page_outputs)
        btn_back_doc.click(lambda s: go_to_page("home", s), inputs=[session_user], outputs=page_outputs)
        btn_back_to_conv.click(lambda s: go_to_page("home", s), inputs=[session_user], outputs=page_outputs)

        _profile_card_md = _profile_card_html

        def _build_conv_choices(conversations):
            choices = []
            conv_map = {}
            for c in conversations:
                label = c.title
                if label in conv_map:
                    label = f"{label} #{c.id}"
                choices.append(label)
                conv_map[label] = c.id
            return choices, conv_map

        def do_sign_in(first_name, last_name, password):
            result = auth_service.login(first_name, last_name, password)
            if not result.ok:
                return (
                    gr.update(), gr.update(visible=True), gr.update(visible=False), gr.update(visible=False),
                    gr.update(visible=False), _status_html(result.message, ok=False), "", "",
                    [], gr.update(choices=[]), {}, None, "", gr.update(visible=False),
                    gr.update(), gr.update(), gr.update(visible=False), "", gr.update(visible=False, value=None)
                )
            user = result.user
            gr.Info(result.message)
            
            conversations = conv_storage.list_conversations(user.nom_util)
            choices, conv_map = _build_conv_choices(conversations)
            
            header_user_name_str = f'<div style="font-weight: 500; font-size: 14px; color: #374151;">{html.escape(user.full_name)}</div>'
            welcome_html = _welcome_banner_html(user)
            status_html = _status_badges_html()
            
            return (
                user, gr.update(visible=False), gr.update(visible=False), gr.update(visible=False),
                gr.update(visible=True), "", _profile_card_md(user), "",
                gr.update(value=[]), gr.update(choices=choices, value=None), conv_map, None, header_user_name_str, gr.update(visible=True),
                gr.update(value="", visible=False), gr.update(value=status_html), gr.update(visible=False), "", gr.update(visible=False, value=None)
            )

        signin_button.click(
            do_sign_in,
            inputs=[signin_first_name, signin_last_name, signin_password],
            outputs=[
                session_user, signin_page, signup_page, profile_page, conversation_page,
                signin_status, profile_info, profile_status,
                chatbot, conv_radio, conv_id_map, current_conv_id, header_user_name, header_profile_container,
                welcome_box, system_status_box, active_conv_box, rename_title_input, csv_download_btn
            ]
        )

        go_to_profile_btn.click(lambda s: go_to_page("profile", s), inputs=[session_user], outputs=page_outputs)

        def do_sign_up(first_name, last_name, password, confirm):
            result = auth_service.register(password, confirm, first_name, last_name)
            if not result.ok:
                return (
                    gr.update(visible=True),
                    gr.update(visible=False),
                    _status_html(result.message, ok=False),
                    "",
                )
            return (
                gr.update(visible=False),
                gr.update(visible=True),
                "",
                _status_html(result.message, ok=True),
            )

        signup_button.click(
            do_sign_up,
            inputs=[
                signup_first_name,
                signup_last_name,
                signup_password,
                signup_confirm,
            ],
            outputs=[signup_page, signin_page, signup_status, signin_status],
        )

        def show_signup():
            return gr.update(visible=False), gr.update(visible=True), ""

        def show_signin():
            return gr.update(visible=False), gr.update(visible=True), ""

        go_to_signup.click(show_signup, outputs=[signin_page, signup_page, signup_status])
        go_to_signin.click(show_signin, outputs=[signup_page, signin_page, signin_status])

        def do_disconnect():
            return (
                None, gr.update(visible=True), gr.update(visible=False), gr.update(visible=False), "", "", "",
                gr.update(visible=False, open=False), gr.update(visible=True), "",
                gr.update(value=[]), gr.update(choices=[]), {}, None, "", gr.update(visible=False),
                gr.update(visible=False), gr.update(value=_status_badges_html()), gr.update(visible=False), "", gr.update(visible=False, value=None)
            )

        disconnect_button.click(
            do_disconnect,
            outputs=[
                session_user, signin_page, profile_page, conversation_page, signin_first_name, signin_last_name, signin_password,
                profile_edit_form, edit_profile_button, profile_status,
                chatbot, conv_radio, conv_id_map, current_conv_id, header_user_name, header_profile_container,
                welcome_box, system_status_box, active_conv_box, rename_title_input, csv_download_btn
            ]
        )

        def start_edit(user):
            if user is None:
                return gr.update(), gr.update(), gr.update(visible=False, open=False), gr.update(visible=True)
            return user.prenom, user.nom, gr.update(visible=True, open=True), gr.update(visible=False)

        edit_profile_button.click(
            start_edit,
            inputs=[session_user],
            outputs=[edit_first_name, edit_last_name, profile_edit_form, edit_profile_button]
        )

        def cancel_edit():
            return gr.update(visible=False, open=False), gr.update(visible=True), ""

        cancel_profile_button.click(
            cancel_edit,
            outputs=[profile_edit_form, edit_profile_button, profile_status]
        )

        def do_save_profile(user, first_name, last_name):
            if user is None:
                return (
                    user, _status_html("Session expirée, merci de vous reconnecter.", ok=False), "",
                    gr.update(visible=False, open=False), gr.update(visible=True), gr.update()
                )
            result = auth_service.update_profile(user, first_name, last_name)
            if not result.ok:
                return (
                    user, _status_html(result.message, ok=False), _profile_card_md(user),
                    gr.update(visible=True, open=True), gr.update(visible=False), gr.update()
                )
            updated_user = result.user
            gr.Info(result.message)
            header_str = f'<div style="font-weight: 500; font-size: 14px; color: #374151;">{html.escape(updated_user.full_name)}</div>'
            return (
                updated_user, _status_html(result.message, ok=True), _profile_card_md(updated_user),
                gr.update(visible=False, open=False), gr.update(visible=True), header_str
            )

        save_profile_button.click(
            do_save_profile,
            inputs=[session_user, edit_first_name, edit_last_name],
            outputs=[session_user, profile_status, profile_info, profile_edit_form, edit_profile_button, header_user_name]
        )
        # -------------------- Conversation: Core Chat Logic -------------------

        def add_user_msg(message, history):
            """Step 1: show user message immediately and hide welcome banner."""
            if not message:
                return gr.update(), history, gr.update()
            return "", history + [{"role": "user", "content": message}], gr.update(visible=False)

        async def bot_respond(user, history, current_cid, cid_map, mode):
            """Step 2: generate answer, update CSV export and conversation list."""
            if not user or not history:
                yield history, current_cid, gr.update(), cid_map, gr.update(), gr.update(), gr.update()
                return

            raw_msg = history[-1]["content"]
            if isinstance(raw_msg, list):
                user_msg = " ".join([m.get("text", str(m)) if isinstance(m, dict) else str(m) for m in raw_msg])
            elif isinstance(raw_msg, tuple):
                user_msg = str(raw_msg[0]) if raw_msg else ""
            else:
                user_msg = str(raw_msg)
            
            is_new = (current_cid is None)
            current_title = ""
            if is_new:
                # Titrage intelligent par l'IA
                try:
                    llm = LLMClient()
                    title = await llm.generate_title(user_msg)
                except Exception:
                    title = user_msg[:40] + ("..." if len(user_msg) > 40 else "")
                conv = await asyncio.to_thread(conv_storage.create_conversation, user.nom_util, title)
                current_cid = conv.id
                current_title = conv.title
                await asyncio.to_thread(conv_storage.add_message, current_cid, "user", user_msg)
            else:
                await asyncio.to_thread(conv_storage.add_message, current_cid, "user", user_msg)
                for lbl, cid in cid_map.items():
                    if cid == current_cid:
                        current_title = lbl.rsplit(" #", 1)[0] if " #" in lbl else lbl
                        break

            csv_file = None
            simplified = (mode in ("Sans SQL", "Mode Simplifie"))
            try:
                sql_str, results = await ask_database(user_msg)
                bot_md = _format_bot_response(sql_str, results, simplified=simplified)
                await asyncio.to_thread(conv_storage.add_message, current_cid, "assistant", bot_md, sql_str)
                if results:
                    csv_file = create_results_csv(results)
            except Exception as e:
                bot_md = f"**Erreur :** {str(e)}"
                await asyncio.to_thread(conv_storage.add_message, current_cid, "assistant", bot_md)

            history.append({"role": "assistant", "content": bot_md})

            conversations = await asyncio.to_thread(conv_storage.list_conversations, user.nom_util)
            choices, new_map = _build_conv_choices(conversations)
            
            selected_label = None
            for lbl, cid in new_map.items():
                if cid == current_cid:
                    selected_label = lbl
                    break

            csv_btn_update = gr.update(value=csv_file, visible=True) if csv_file else gr.update(value=None, visible=False)
            active_box_update = gr.update(visible=True)
            rename_input_update = gr.update(value=current_title)

            yield (
                history,
                current_cid,
                gr.update(choices=choices, value=selected_label),
                new_map,
                csv_btn_update,
                active_box_update,
                rename_input_update,
            )

        # Wire up chat submit
        chat_input.submit(
            add_user_msg,
            inputs=[chat_input, chatbot],
            outputs=[chat_input, chatbot, welcome_box],
            show_progress="hidden"
        ).then(
            bot_respond,
            inputs=[session_user, chatbot, current_conv_id, conv_id_map, view_mode],
            outputs=[chatbot, current_conv_id, conv_radio, conv_id_map, csv_download_btn, active_conv_box, rename_title_input],
            show_progress="minimal"
        )
        send_btn.click(
            add_user_msg,
            inputs=[chat_input, chatbot],
            outputs=[chat_input, chatbot, welcome_box],
            show_progress="hidden"
        ).then(
            bot_respond,
            inputs=[session_user, chatbot, current_conv_id, conv_id_map, view_mode],
            outputs=[chatbot, current_conv_id, conv_radio, conv_id_map, csv_download_btn, active_conv_box, rename_title_input],
            show_progress="minimal"
        )

        def do_new_conversation(user):
            if not user:
                return [], None, gr.update(), gr.update(visible=False), gr.update(visible=False), "", gr.update(visible=False, value=None)
            conversations = conv_storage.list_conversations(user.nom_util)
            choices, _ = _build_conv_choices(conversations)
            return (
                [],
                None,
                gr.update(choices=choices, value=None),
                gr.update(value="", visible=False),
                gr.update(visible=False),
                "",
                gr.update(visible=False, value=None),
            )

        new_chat_btn.click(
            do_new_conversation,
            inputs=[session_user],
            outputs=[chatbot, current_conv_id, conv_radio, welcome_box, active_conv_box, rename_title_input, csv_download_btn]
        )

        def do_select_conversation(evt: gr.SelectData, cmap, mode):
            label = evt.value
            if not label or label not in cmap:
                return [], None, gr.update(), gr.update(visible=False), "", gr.update(visible=False, value=None)
            cid = cmap[label]
            messages = conv_storage.get_messages(cid)
            simplified = (mode in ("Sans SQL", "Mode Simplifie"))
            history = []
            for m in messages:
                content = m.content
                if m.role == "assistant" and m.sql_generated:
                    if simplified and "```sql" in content:
                        parts = content.split("```\n\n", 1)
                        content = parts[1] if len(parts) > 1 else content
                    elif not simplified and "```sql" not in content:
                        lines = m.sql_generated.strip().split("\n")
                        code_lines = [f"{i+1:>3} │ {line}" for i, line in enumerate(lines)]
                        content = f"```sql\n{chr(10).join(code_lines)}\n```\n\n" + content
                history.append({"role": m.role, "content": content})
            
            clean_title = label.rsplit(" #", 1)[0] if " #" in label else label

            welcome_update = gr.update(visible=False)
            active_box_update = gr.update(visible=True)
            rename_update = gr.update(value=clean_title)
            csv_update = gr.update(visible=False, value=None)

            return history, cid, welcome_update, active_box_update, rename_update, csv_update

        conv_radio.select(
            do_select_conversation,
            inputs=[conv_id_map, view_mode],
            outputs=[chatbot, current_conv_id, welcome_box, active_conv_box, rename_title_input, csv_download_btn]
        )

        def do_toggle_view_mode(mode, cid):
            if not cid:
                return gr.update()
            messages = conv_storage.get_messages(cid)
            simplified = (mode in ("Sans SQL", "Mode Simplifie"))
            history = []
            for m in messages:
                content = m.content
                if m.role == "assistant" and m.sql_generated:
                    if simplified and "```sql" in content:
                        parts = content.split("```\n\n", 1)
                        content = parts[1] if len(parts) > 1 else content
                    elif not simplified and "```sql" not in content:
                        lines = m.sql_generated.strip().split("\n")
                        code_lines = [f"{i+1:>3} │ {line}" for i, line in enumerate(lines)]
                        content = f"```sql\n{chr(10).join(code_lines)}\n```\n\n" + content
                history.append({"role": m.role, "content": content})
            return history

        view_mode.change(
            do_toggle_view_mode,
            inputs=[view_mode, current_conv_id],
            outputs=[chatbot],
        )

        def do_rename_conversation(cid, new_title, user):
            if not cid or not new_title or not new_title.strip():
                return gr.update(), gr.update()
            ok = conv_storage.rename_conversation(cid, new_title.strip())
            if not ok:
                return gr.update(), gr.update()
            gr.Info("Discussion renommee avec succes.")
            conversations = conv_storage.list_conversations(user.nom_util)
            choices, new_map = _build_conv_choices(conversations)
            selected_label = None
            for lbl, c_id in new_map.items():
                if c_id == cid:
                    selected_label = lbl
                    break
            return gr.update(choices=choices, value=selected_label), new_map

        btn_rename_confirm.click(
            do_rename_conversation,
            inputs=[current_conv_id, rename_title_input, session_user],
            outputs=[conv_radio, conv_id_map],
        )

        def do_delete_conversation(cid, user):
            if not cid or not user:
                return gr.update(), gr.update(), [], None, gr.update(visible=False), gr.update(visible=False), "", gr.update(visible=False, value=None)
            conv_storage.delete_conversation(cid)
            gr.Info("Discussion supprimee.")
            conversations = conv_storage.list_conversations(user.nom_util)
            choices, new_map = _build_conv_choices(conversations)
            return (
                gr.update(choices=choices, value=None),
                new_map,
                [],
                None,
                gr.update(value="", visible=False),
                gr.update(visible=False),
                "",
                gr.update(visible=False, value=None),
            )

        btn_delete_confirm.click(
            do_delete_conversation,
            inputs=[current_conv_id, session_user],
            outputs=[conv_radio, conv_id_map, chatbot, current_conv_id, welcome_box, active_conv_box, rename_title_input, csv_download_btn],
        )

    return demo

if __name__ == "__main__":
    build_app().launch(server_name="0.0.0.0", server_port=7860, share=True, theme=theme, css=custom_css, js=force_light_mode_js)
