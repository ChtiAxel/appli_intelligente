"""Gradio application entry point."""

from __future__ import annotations
import asyncio
import os
import base64
import html
import re
import gradio as gr
from datetime import datetime, date
from typing import Optional, Any
from .service.auth import AuthService, get_role_label, UserRole, ROLE_LABELS
from .storage.conversations import ConversationStorage
from .storage.users import User
from .service.core import ask_database

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
    background: linear-gradient(135deg, #1e293b 0%, #334155 100%) !important;
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
.profile-avatar-img {
    width: 64px !important;
    height: 64px !important;
    border-radius: 50% !important;
    object-fit: cover !important;
    margin: 0 auto 8px auto !important;
    box-shadow: 0 4px 8px rgba(0, 0, 0, 0.1) !important;
    display: block !important;
    border: 2px solid #e5e7eb !important;
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
.profile-badge {
    display: inline-flex !important;
    align-items: center !important;
    gap: 5px !important;
    padding: 3px 12px !important;
    border-radius: 9999px !important;
    font-size: 12px !important;
    font-weight: 600 !important;
    letter-spacing: 0.02em !important;
    margin: 4px 0 6px 0 !important;
    border-width: 1px !important;
    border-style: solid !important;
}
.badge-prof {
    background-color: #eff6ff !important;
    border-color: #bfdbfe !important;
    color: #1d4ed8 !important;
}
.badge-secretaire {
    background-color: #ecfdf5 !important;
    border-color: #a7f3d0 !important;
    color: #047857 !important;
}
.badge-admin {
    background-color: #fef2f2 !important;
    border-color: #fecaca !important;
    color: #b91c1c !important;
}
.profile-stats-grid {
    display: grid !important;
    grid-template-columns: repeat(3, 1fr) !important;
    gap: 8px !important;
    background: #f9fafb !important;
    border: 1px solid #e5e7eb !important;
    border-radius: 8px !important;
    padding: 12px 6px !important;
    margin: 0.85rem 0 !important;
    text-align: center !important;
    width: 100% !important;
    box-sizing: border-box !important;
}
.profile-stat-box {
    display: flex !important;
    flex-direction: column !important;
    align-items: center !important;
    justify-content: center !important;
}
.profile-stat-value {
    font-size: 15px !important;
    font-weight: 700 !important;
    color: #111827 !important;
    line-height: 1.2 !important;
}
.profile-stat-label {
    font-size: 11px !important;
    color: #6b7280 !important;
    margin-top: 3px !important;
}
.danger-zone {
    margin-top: 1.5rem !important;
    padding: 1rem !important;
    border: 1px solid #fecaca !important;
    background-color: #fef2f2 !important;
    border-radius: 8px !important;
    text-align: left !important;
    width: 100% !important;
    box-sizing: border-box !important;
}
.danger-zone-title {
    font-size: 14px !important;
    font-weight: 700 !important;
    color: #991b1b !important;
    margin-bottom: 4px !important;
}
.danger-zone-desc {
    font-size: 12px !important;
    color: #7f1d1d !important;
    margin-bottom: 12px !important;
    line-height: 1.4 !important;
}
.delete-confirm-box {
    margin-top: 0.75rem !important;
    padding: 0.85rem !important;
    background: #ffffff !important;
    border: 1px solid #fca5a5 !important;
    border-radius: 6px !important;
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
.search-bar {
    margin-bottom: 16px;
}
.search-bar input {
    border-radius: 20px !important;
    background: #ffffff !important;
    border: 1px solid #e5e7eb !important;
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
.user-info-sidebar {
    margin-top: auto;
    padding-top: 16px;
    border-top: 1px solid #e5e7eb;
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 14px;
    font-weight: 500;
}
.user-info-sidebar img {
    border-radius: 50%;
    width: 24px;
    height: 24px;
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

_FRENCH_MONTHS = {
    1: "janv.", 2: "févr.", 3: "mars", 4: "avr.", 5: "mai", 6: "juin",
    7: "juil.", 8: "août", 9: "sept.", 10: "oct.", 11: "nov.", 12: "déc."
}

ROLE_CONFIGS = {
    "PROF": {"label": "Enseignant", "class": "badge-prof", "icon": "🎓"},
    "SECRETAIRE": {"label": "Secrétaire", "class": "badge-secretaire", "icon": "📋"},
    "ADMIN": {"label": "Administrateur", "class": "badge-admin", "icon": "🛡️"},
}

def _header_user_html(user: Optional[User]) -> str:
    if not user:
        return ""
    full_name = html.escape(getattr(user, "full_name", "") or "Utilisateur")
    avatar_val = getattr(user, "avatar", None)
    if avatar_val and str(avatar_val).strip():
        thumb = f'<img src="{html.escape(str(avatar_val).strip())}" style="width: 24px; height: 24px; border-radius: 50%; object-fit: cover;" alt="{full_name}" />'
    else:
        prenom = getattr(user, "prenom", "") or ""
        nom = getattr(user, "nom", "") or ""
        init = f"{(prenom[0] if prenom else '')}{(nom[0] if nom else 'U')}".upper() or "U"
        thumb = f'<div style="width: 24px; height: 24px; border-radius: 50%; background: #111827; color: #ffffff; display: inline-flex; align-items: center; justify-content: center; font-size: 11px; font-weight: 700;">{html.escape(init)}</div>'
    return f'<div style="display: flex; align-items: center; gap: 8px;">{thumb}<span style="font-weight: 500; font-size: 14px; color: #374151;">{full_name}</span></div>'

def _profile_card_html(user, stats=None) -> str:
    if not user:
        return (
            '<div class="profile-header">\n'
            '    <div class="profile-role">Erreur de chargement</div>\n'
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

    # Avatar rendering
    avatar_val = getattr(user, "avatar", None)
    if avatar_val and str(avatar_val).strip():
        escaped_avatar = html.escape(str(avatar_val).strip())
        avatar_html = f'<img src="{escaped_avatar}" class="profile-avatar-img" alt="{escaped_full_name}" />'
    else:
        avatar_html = f'<div class="profile-avatar">{escaped_initials}</div>'

    # Role badge
    raw_role = getattr(user, "role", "PROF") or "PROF"
    role_key = str(raw_role).upper()
    role_cfg = ROLE_CONFIGS.get(role_key, ROLE_CONFIGS["PROF"])
    badge_html = f'<div class="profile-badge {role_cfg["class"]}">{role_cfg["icon"]} {role_cfg["label"]}</div>'

    # Activity stats
    if stats is None:
        try:
            nom_util = getattr(user, "nom_util", "")
            if nom_util:
                stats = ConversationStorage().get_user_activity_stats(nom_util)
            else:
                stats = {}
        except Exception:
            stats = {}

    conv_count = 0
    question_count = 0
    if isinstance(stats, dict):
        conv_count = stats.get("conversations", stats.get("total_conversations", 0)) or 0
        question_count = stats.get("questions", stats.get("total_questions", 0)) or 0

    # Member since date
    created_at = getattr(user, "created_at", None)
    if created_at is None:
        created_at = datetime.now()
    elif isinstance(created_at, str):
        try:
            created_at = datetime.fromisoformat(created_at)
        except Exception:
            try:
                created_at = datetime.strptime(created_at, "%Y-%m-%d %H:%M:%S")
            except Exception:
                created_at = datetime.now()

    formatted_date = f"{created_at.day} {_FRENCH_MONTHS.get(created_at.month, '')} {created_at.year}"

    stats_html = (
        '    <div class="profile-stats-grid">\n'
        '        <div class="profile-stat-box">\n'
        f'            <div class="profile-stat-value">{conv_count}</div>\n'
        '            <div class="profile-stat-label">Conversations</div>\n'
        '        </div>\n'
        '        <div class="profile-stat-box">\n'
        f'            <div class="profile-stat-value">{question_count}</div>\n'
        '            <div class="profile-stat-label">Questions posées</div>\n'
        '        </div>\n'
        '        <div class="profile-stat-box">\n'
        f'            <div class="profile-stat-value">{formatted_date}</div>\n'
        '            <div class="profile-stat-label">Membre depuis</div>\n'
        '        </div>\n'
        '    </div>'
    )

    return (
        '<div class="profile-header">\n'
        f'    {avatar_html}\n'
        f'    <div class="profile-name">{escaped_full_name}</div>\n'
        f'    <div class="profile-id">{escaped_id}</div>\n'
        '    <div class="profile-role">\n'
        f'        {badge_html}\n'
        '    </div>\n'
        f'{stats_html}\n'
        '</div>'
    )

_profile_card_md = _profile_card_html


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
                    go_to_profile_btn = gr.Button("👤 Mon Profil", variant="secondary", size="sm")

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

                with gr.Accordion("Changer d'avatar", open=False, elem_classes=["profile-accordion"]) as avatar_accordion:
                    avatar_input = gr.Textbox(
                        label="URL de l'avatar (ou laissez vide pour les initiales)",
                        placeholder="https://... ou laissez vide",
                        lines=1,
                        max_lines=1,
                    )
                    with gr.Row():
                        btn_preset_prof = gr.Button("🎓 Enseignant", size="sm")
                        btn_preset_secretaire = gr.Button("📋 Secrétaire", size="sm")
                        btn_preset_admin = gr.Button("🛡️ Admin", size="sm")
                        btn_clear_avatar = gr.Button("✖ Initiales", size="sm")
                    btn_save_avatar = gr.Button("Mettre à jour l'avatar", variant="primary")

                with gr.Accordion("Changer de mot de passe", open=False, elem_classes=["profile-accordion"]) as password_accordion:
                    current_pwd_input = gr.Textbox(label="Mot de passe actuel *", type="password", placeholder="••••••••")
                    new_pwd_input = gr.Textbox(
                        label="Nouveau mot de passe *",
                        type="password",
                        placeholder="••••••••",
                        info="8 car. min, 1 majuscule, 1 chiffre, 1 car. spécial",
                    )
                    confirm_pwd_input = gr.Textbox(label="Confirmer le nouveau mot de passe *", type="password", placeholder="••••••••")
                    btn_submit_pwd = gr.Button("Mettre à jour le mot de passe", variant="primary")

                with gr.Column(elem_classes=["danger-zone"]) as danger_zone_section:
                    gr.HTML(
                        '<div class="danger-zone-title">⚠️ Zone de danger (RGPD)</div>'
                        '<div class="danger-zone-desc">La suppression de votre compte efface définitivement toutes vos conversations et données associées.</div>'
                    )
                    btn_start_delete_account = gr.Button("Supprimer mon compte", variant="stop", size="sm")

                    with gr.Column(visible=False, elem_classes=["delete-confirm-box"]) as delete_confirm_section:
                        gr.Markdown("⚠️ **Attention :** Cette action est irréversible. Pour confirmer la suppression définitive de votre compte, saisissez votre mot de passe.")
                        delete_password_input = gr.Textbox(label="Mot de passe de confirmation *", type="password", placeholder="••••••••")
                        with gr.Row():
                            btn_confirm_delete_account = gr.Button("Confirmer la suppression définitive", variant="stop")
                            btn_cancel_delete_account = gr.Button("Annuler", variant="secondary")

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

            # --- Page de Conversation ---
            with gr.Column(visible=False, elem_id="conv-page") as conversation_page:
                with gr.Column(elem_id="conv-sidebar"):
                    with gr.Row(elem_classes=["sidebar-header"]):
                        gr.HTML("<div style='flex-grow: 1; margin: 0; padding: 0;'>≡ NaturSQL</div>", scale=1)
                        new_chat_btn = gr.Button("+", elem_classes=["new-chat-btn"], scale=0, min_width=30)
                    
                    search_bar = gr.Textbox(placeholder="Search", show_label=False, container=False, elem_classes=["search-bar"])
                    gr.HTML('<div class="chat-list-title">Chats</div>')
                    
                    conv_radio = gr.Radio(choices=[], show_label=False, container=False, elem_classes=["chat-list"])
                    
                    with gr.Row(elem_classes=["user-info-sidebar"]):
                        gr.HTML("<div></div>")

                with gr.Column(elem_id="conv-main"):
                    chatbot = gr.Chatbot(
                        elem_id="conv-chat",
                        show_label=False,
                        buttons=[],
                        feedback_options=None
                    )
                    with gr.Row(elem_id="conv-input-row"):
                        chat_input = gr.Textbox(
                            placeholder="What would you like to know?",
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
                    <strong>Légal</strong><br>
                    <a href="#" style="color: #1f2937; text-decoration: none;" onclick="document.getElementById('btn-show-mentions').click(); return false;">Mentions légales</a><br>
                    <a href="#" style="color: #1f2937; text-decoration: none;" onclick="document.getElementById('btn-show-privacy').click(); return false;">Politique de confidentialité</a><br>
                    <a href="#" style="color: #1f2937; text-decoration: none;" onclick="document.getElementById('btn-show-cgu').click(); return false;">Conditions générales d'utilisation</a>
                </div>
            </div>
            """)
            
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
                    label = f"{c.title} #{c.id}"
                choices.append(label)
                conv_map[label] = c.id
            return choices, conv_map

        def do_sign_in(first_name, last_name, password):
            result = auth_service.login(first_name, last_name, password)
            if not result.ok:
                return (
                    gr.update(), gr.update(visible=True), gr.update(visible=False), gr.update(visible=False),
                    gr.update(visible=False), _status_html(result.message, ok=False), "", "",
                    [], gr.update(choices=[]), {}, None, "", gr.update(visible=False)
                )
            user = result.user
            gr.Info(result.message)
            
            conversations = conv_storage.list_conversations(user.nom_util)
            choices, conv_map = _build_conv_choices(conversations)
            
            header_user_name_str = _header_user_html(user)
            try:
                stats = conv_storage.get_user_activity_stats(user.nom_util)
            except Exception:
                stats = {}
            
            return (
                user, gr.update(visible=False), gr.update(visible=False), gr.update(visible=False),
                gr.update(visible=True), "", _profile_card_md(user, stats), "",
                gr.update(value=[]), gr.update(choices=choices, value=None), conv_map, None, header_user_name_str, gr.update(visible=True)
            )

        signin_button.click(
            do_sign_in,
            inputs=[signin_first_name, signin_last_name, signin_password],
            outputs=[
                session_user, signin_page, signup_page, profile_page, conversation_page,
                signin_status, profile_info, profile_status,
                chatbot, conv_radio, conv_id_map, current_conv_id, header_user_name, header_profile_container
            ]
        )

        def go_to_profile_view(user):
            s_in, s_up, prof, leg_m, leg_p, leg_c, doc, conv = go_to_page("profile", user)
            if user is None:
                return s_in, s_up, prof, leg_m, leg_p, leg_c, doc, conv, gr.update(), gr.update()
            try:
                fresh_stats = conv_storage.get_user_activity_stats(user.nom_util)
            except Exception:
                fresh_stats = {}
            card_html = _profile_card_html(user, fresh_stats)
            current_avatar = getattr(user, "avatar", None) or ""
            return s_in, s_up, prof, leg_m, leg_p, leg_c, doc, conv, card_html, current_avatar

        go_to_profile_btn.click(
            go_to_profile_view,
            inputs=[session_user],
            outputs=page_outputs + [profile_info, avatar_input],
        )

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
                gr.update(visible=False), gr.update(visible=True), "", "", "", "", ""
            )

        disconnect_button.click(
            do_disconnect,
            outputs=[
                session_user, signin_page, profile_page, conversation_page, signin_first_name, signin_last_name, signin_password,
                profile_edit_form, edit_profile_button, profile_status,
                chatbot, conv_radio, conv_id_map, current_conv_id, header_user_name, header_profile_container,
                delete_confirm_section, btn_start_delete_account, delete_password_input, current_pwd_input, new_pwd_input, confirm_pwd_input, avatar_input
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
                try:
                    stats = conv_storage.get_user_activity_stats(user.nom_util)
                except Exception:
                    stats = {}
                return (
                    user, _status_html(result.message, ok=False), _profile_card_md(user, stats),
                    gr.update(visible=True, open=True), gr.update(visible=False), gr.update()
                )
            updated_user = result.user or user
            gr.Info(result.message)
            header_str = _header_user_html(updated_user)
            try:
                stats = conv_storage.get_user_activity_stats(updated_user.nom_util)
            except Exception:
                stats = {}
            return (
                updated_user, _status_html(result.message, ok=True), _profile_card_md(updated_user, stats),
                gr.update(visible=False, open=False), gr.update(visible=True), header_str
            )

        save_profile_button.click(
            do_save_profile,
            inputs=[session_user, edit_first_name, edit_last_name],
            outputs=[session_user, profile_status, profile_info, profile_edit_form, edit_profile_button, header_user_name]
        )

        # --- Avatar Management (R5) ---
        btn_preset_prof.click(lambda: "https://api.dicebear.com/7.x/bottts/svg?seed=prof", outputs=[avatar_input])
        btn_preset_secretaire.click(lambda: "https://api.dicebear.com/7.x/bottts/svg?seed=secretaire", outputs=[avatar_input])
        btn_preset_admin.click(lambda: "https://api.dicebear.com/7.x/bottts/svg?seed=admin", outputs=[avatar_input])
        btn_clear_avatar.click(lambda: "", outputs=[avatar_input])

        def do_save_avatar(user, avatar_url):
            if user is None:
                gr.Warning("Session expirée, veuillez vous reconnecter.")
                return user, gr.update(), gr.update(), gr.update()
            clean_avatar = (avatar_url or "").strip() or None
            result = auth_service.update_avatar(user, clean_avatar)
            if not result.ok:
                gr.Warning(result.message)
                return user, gr.update(), gr.update(), gr.update()
            gr.Info("Avatar mis à jour avec succès !")
            updated_user = result.user or user
            try:
                fresh_stats = conv_storage.get_user_activity_stats(updated_user.nom_util)
            except Exception:
                fresh_stats = {}
            card_html = _profile_card_html(updated_user, fresh_stats)
            header_html = _header_user_html(updated_user)
            return updated_user, card_html, header_html, (clean_avatar or "")

        btn_save_avatar.click(
            do_save_avatar,
            inputs=[session_user, avatar_input],
            outputs=[session_user, profile_info, header_user_name, avatar_input],
        )

        # --- Secure Password Change (R2) ---
        def do_change_password(user, current_p, new_p, confirm_p):
            if user is None:
                gr.Warning("Session expirée, veuillez vous reconnecter.")
                return user, gr.update(), gr.update(), gr.update()
            result = auth_service.change_password(user, current_p, new_p, confirm_p)
            if not result.ok:
                gr.Warning(result.message)
                return user, gr.update(), gr.update(), gr.update()
            gr.Info(result.message)
            updated_user = result.user or user
            return updated_user, "", "", ""

        btn_submit_pwd.click(
            do_change_password,
            inputs=[session_user, current_pwd_input, new_pwd_input, confirm_pwd_input],
            outputs=[session_user, current_pwd_input, new_pwd_input, confirm_pwd_input],
        )

        # --- GDPR Account Deletion (R6) ---
        btn_start_delete_account.click(
            lambda: (gr.update(visible=True), gr.update(visible=False), ""),
            outputs=[delete_confirm_section, btn_start_delete_account, delete_password_input],
        )
        btn_cancel_delete_account.click(
            lambda: (gr.update(visible=False), gr.update(visible=True), ""),
            outputs=[delete_confirm_section, btn_start_delete_account, delete_password_input],
        )

        def do_delete_account(user, password):
            if user is None:
                gr.Warning("Session expirée ou invalide.")
                return (
                    user, gr.update(), gr.update(), gr.update(),
                    gr.update(), gr.update(), "",
                    gr.update(), gr.update(), gr.update(), gr.update(),
                    gr.update(), gr.update()
                )
            result = auth_service.delete_account(user, password)
            if not result.ok:
                gr.Warning(result.message)
                return (
                    user, gr.update(), gr.update(), gr.update(),
                    gr.update(visible=True), gr.update(visible=False), "",
                    gr.update(), gr.update(), gr.update(), gr.update(),
                    gr.update(), gr.update()
                )
            gr.Info("Votre compte et toutes vos données ont été définitivement supprimés.")
            return (
                None, gr.update(visible=True), gr.update(visible=False), gr.update(visible=False),
                gr.update(visible=False), gr.update(visible=True), "",
                [], gr.update(choices=[]), {}, None,
                "", gr.update(visible=False)
            )

        btn_confirm_delete_account.click(
            do_delete_account,
            inputs=[session_user, delete_password_input],
            outputs=[
                session_user, signin_page, profile_page, conversation_page,
                delete_confirm_section, btn_start_delete_account, delete_password_input,
                chatbot, conv_radio, conv_id_map, current_conv_id,
                header_user_name, header_profile_container
            ],
        )
        # -------------------- Conversation: Core Chat Logic -------------------

        def _format_bot_response(sql: str | None, results: list[dict] | None) -> str:
            if not sql and not results:
                return "Désolé, je n'ai pas pu comprendre la demande ou aucune donnée n'a été trouvée."
            
            md_parts = []
            if sql:
                lines = sql.strip().split("\n")
                code_lines = [f"{i+1:>3} │ {line}" for i, line in enumerate(lines)]
                md_parts.append(f"```sql\n{chr(10).join(code_lines)}\n```")
            
            if results:
                headers = list(results[0].keys())
                
                # Filtrer les colonnes completement vides
                active_headers = []
                for h in headers:
                    if any(row.get(h) is not None and str(row.get(h)).strip() != "" for row in results):
                        active_headers.append(h)
                
                if not active_headers:
                    active_headers = headers
                    
                display_headers = [h.replace("_", " ").title() for h in active_headers]
                
                if len(active_headers) == 1:
                    # Affichage en liste à puces si une seule colonne
                    md_parts.append(f"**{display_headers[0]} :**\n")
                    for i, row in enumerate(results):
                        if i >= 50:
                            md_parts.append(f"\n*... {len(results)-50} résultats supplémentaires masqués ...*")
                            break
                        val = row.get(active_headers[0])
                        val_str = str(val) if val is not None and str(val).strip() != "" else "-"
                        md_parts.append(f"- {val_str}")
                else:
                    # Affichage en tableau Markdown (doit être joint par des sauts de ligne simples)
                    table_lines = []
                    table_lines.append("| " + " | ".join(display_headers) + " |")
                    table_lines.append("|" + "|".join(["---"] * len(active_headers)) + "|")
                    for i, row in enumerate(results):
                        if i >= 50:
                            table_lines.append(f"*... {len(results)-50} résultats supplémentaires masqués ...*")
                            break
                        r_str = []
                        for h in active_headers:
                            val = row.get(h)
                            if val is None or str(val).strip() == "" or str(val) == "None":
                                r_str.append("-")
                            else:
                                r_str.append(str(val).replace("|", "\\|")) # Echapement des pipes
                        table_lines.append("| " + " | ".join(r_str) + " |")
                    md_parts.append("\n".join(table_lines))
            else:
                md_parts.append("\n*Aucun résultat trouvé.*")
                
            return "\n\n".join(md_parts)

        def add_user_msg(message, history):
            """Step 1: show user message immediately."""
            if not message:
                return gr.update(), history
            return "", history + [{"role": "user", "content": message}]

        async def bot_respond(user, history, current_cid, cid_map):
            """Step 2: generate answer and save."""
            if not user or not history:
                yield history, current_cid, gr.update(), cid_map
                return

            raw_msg = history[-1]["content"]
            if isinstance(raw_msg, list):
                user_msg = " ".join([m.get("text", str(m)) if isinstance(m, dict) else str(m) for m in raw_msg])
            elif isinstance(raw_msg, tuple):
                user_msg = str(raw_msg[0]) if raw_msg else ""
            else:
                user_msg = str(raw_msg)
            
            if current_cid is None:
                title = user_msg[:50] + ("..." if len(user_msg) > 50 else "")
                conv = await asyncio.to_thread(conv_storage.create_conversation, user.nom_util, title)
                current_cid = conv.id
                await asyncio.to_thread(conv_storage.add_message, current_cid, "user", user_msg)
            else:
                await asyncio.to_thread(conv_storage.add_message, current_cid, "user", user_msg)

            # --- Appel réel à l'IA et à la BDD ---
            try:
                sql_str, results = await ask_database(user_msg)
                bot_md = _format_bot_response(sql_str, results)
                await asyncio.to_thread(conv_storage.add_message, current_cid, "assistant", bot_md, sql_str)
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

            yield history, current_cid, gr.update(choices=choices, value=selected_label), new_map

        # Wire up chat submit
        chat_input.submit(
            add_user_msg,
            inputs=[chat_input, chatbot],
            outputs=[chat_input, chatbot],
            show_progress="hidden"
        ).then(
            bot_respond,
            inputs=[session_user, chatbot, current_conv_id, conv_id_map],
            outputs=[chatbot, current_conv_id, conv_radio, conv_id_map],
            show_progress="minimal"
        )
        send_btn.click(
            add_user_msg,
            inputs=[chat_input, chatbot],
            outputs=[chat_input, chatbot],
            show_progress="hidden"
        ).then(
            bot_respond,
            inputs=[session_user, chatbot, current_conv_id, conv_id_map],
            outputs=[chatbot, current_conv_id, conv_radio, conv_id_map],
            show_progress="minimal"
        )

        def do_new_conversation(user):
            if not user:
                return [], None, gr.update()
            conversations = conv_storage.list_conversations(user.nom_util)
            choices, _ = _build_conv_choices(conversations)
            return [], None, gr.update(choices=choices, value=None)

        new_chat_btn.click(
            do_new_conversation,
            inputs=[session_user],
            outputs=[chatbot, current_conv_id, conv_radio]
        )

        def do_load_conversation(label, cmap):
            if not label or label not in cmap:
                return [], None
            cid = cmap[label]
            messages = conv_storage.get_messages(cid)
            history = [{"role": m.role, "content": m.content} for m in messages]
            return history, cid

        conv_radio.change(
            do_load_conversation,
            inputs=[conv_radio, conv_id_map],
            outputs=[chatbot, current_conv_id]
        )

        def do_search_conversations(query, user, cmap):
            if not user:
                return gr.update()
            conversations = conv_storage.list_conversations(user.nom_util)
            choices, _ = _build_conv_choices(conversations)
            if query:
                q = query.lower()
                choices = [c for c in choices if q in c.lower()]
            return gr.update(choices=choices)

        search_bar.change(
            do_search_conversations,
            inputs=[search_bar, session_user, conv_id_map],
            outputs=[conv_radio]
        )

    return demo

if __name__ == "__main__":
    build_app().launch(server_name="0.0.0.0", server_port=7860, share=True, theme=theme, css=custom_css, js=force_light_mode_js)
