"""Gradio application entry point."""

from __future__ import annotations
import asyncio
import os
import base64
import html
import json
import re
import csv
import tempfile
from datetime import datetime
import gradio as gr
from datetime import datetime, date
from typing import Optional, Any
from .service.auth import AuthService, get_role_label, UserRole, ROLE_LABELS
from .storage.conversations import ConversationStorage
from .storage.users import User
from .service.core import ask_database
from .service.monitoring import get_system_status
from .ollama_client.llm import LLMClient

def load_markdown(filename: str) -> str:
    candidates = [
        os.path.join(os.path.dirname(__file__), "..", "..", "docs", "legal", filename),
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

    // --- Historique des conversations : clic, menu « ⋯ », renommage, suppression ---
    // Les actions sont transmises au serveur via un champ texte et un bouton cachés.
    const sendConvAction = (payload) => {
        const field = document.querySelector('#conv-action-input textarea, #conv-action-input input');
        const trigger = document.getElementById('conv-action-btn');
        if (!field || !trigger) return;
        field.value = JSON.stringify({...payload, nonce: Date.now()});
        field.dispatchEvent(new Event('input', {bubbles: true}));
        setTimeout(() => trigger.click(), 0);
    };
    const closeMenus = (except) => {
        document.querySelectorAll('.conv-item.menu-open').forEach((item) => {
            if (item !== except) item.classList.remove('menu-open');
        });
    };
    const startRename = (item) => {
        const titleEl = item.querySelector('.conv-title');
        if (!titleEl || item.querySelector('.conv-rename-input')) return;
        const input = document.createElement('input');
        input.className = 'conv-rename-input';
        input.value = item.dataset.title || titleEl.textContent;
        input.maxLength = 255;
        titleEl.replaceWith(input);
        input.focus();
        input.select();
        let done = false;
        const finish = (commit) => {
            if (done) return;
            done = true;
            const value = input.value.trim();
            input.replaceWith(titleEl);
            if (commit && value && value !== item.dataset.title) {
                titleEl.textContent = value;
                sendConvAction({action: 'rename', cid: Number(item.dataset.cid), title: value});
            }
        };
        input.addEventListener('keydown', (e) => {
            e.stopPropagation();
            if (e.key === 'Enter') { e.preventDefault(); finish(true); }
            if (e.key === 'Escape') { e.preventDefault(); finish(false); }
        });
        input.addEventListener('blur', () => finish(true));
        input.addEventListener('click', (e) => e.stopPropagation());
    };
    if (!window.__natursqlConvHandlers) {
        window.__natursqlConvHandlers = true;
        document.addEventListener('click', (e) => {
            const item = e.target.closest('.conv-item');
            if (!item) { closeMenus(null); return; }
            const actionBtn = e.target.closest('[data-conv-action]');
            if (e.target.closest('.conv-menu-btn')) {
                e.stopPropagation();
                const open = !item.classList.contains('menu-open');
                closeMenus(item);
                item.classList.toggle('menu-open', open);
                return;
            }
            if (actionBtn) {
                e.stopPropagation();
                closeMenus(null);
                if (actionBtn.dataset.convAction === 'rename') {
                    startRename(item);
                } else if (actionBtn.dataset.convAction === 'delete') {
                    const title = item.dataset.title || '';
                    if (window.confirm('Supprimer la discussion « ' + title + ' » ? Cette action est irréversible.')) {
                        sendConvAction({action: 'delete', cid: Number(item.dataset.cid)});
                    }
                }
                return;
            }
            if (e.target.closest('.conv-rename-input')) return;
            closeMenus(null);
            document.querySelectorAll('.conv-item.active').forEach((el) => el.classList.remove('active'));
            item.classList.add('active');
            sendConvAction({action: 'select', cid: Number(item.dataset.cid)});
        });
        document.addEventListener('keydown', (e) => {
            const item = e.target.classList && e.target.classList.contains('conv-item') ? e.target : null;
            if (item && (e.key === 'Enter' || e.key === ' ')) { e.preventDefault(); item.click(); }
            if (e.key === 'Escape') closeMenus(null);
        });
    }
}
"""

# Bouton « Conversations » : ouvre/ferme le panneau d'historique (sans aller-retour serveur).
toggle_sidebar_js = """
() => {
    const page = document.getElementById('conv-page');
    const pageVisible = page && page.offsetParent !== null;
    if (pageVisible) {
        document.body.classList.toggle('nsql-sidebar-hidden');
    } else {
        document.body.classList.remove('nsql-sidebar-hidden');
    }
}
"""

# Bascule Avec SQL / Sans SQL : purement visuelle, pour ne jamais interrompre une réponse en cours.
toggle_sql_js = """
(mode) => {
    document.body.classList.toggle('nsql-hide-sql', mode === 'Sans SQL');
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
    position: relative;
    background: white;
    padding-top: 12px !important;
    padding-bottom: 12px !important;
    padding-left: 2rem;
    padding-right: 2rem;
    border-bottom: 1px solid #e5e7eb;
    width: 100vw;
    margin-left: calc(-50vw + 50%) !important;
    margin-top: 0 !important;
    box-sizing: border-box;
    margin-bottom: 0 !important;
    gap: 0 !important;
}
/* Supprime l'espacement Gradio (16 px) entre l'en-tête et le contenu */
.header + .main-content {
    margin-top: calc(-1 * var(--layout-gap, 16px)) !important;
}
.header > .row, .header .header-bar {
    align-items: center !important;
    min-height: 48px;
}
.header-bar .html-container {
    padding: 0 !important;
}
.header-bar .prose h2 {
    line-height: 1.2 !important;
}
.header-bar .prose > a {
    display: inline-flex !important;
    align-items: center !important;
    padding: 0 !important;
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
.profile-rgpd-badge {
    display: inline-flex !important;
    align-items: center !important;
    gap: 4px !important;
    font-size: 11px !important;
    color: #4b5563 !important;
    background: #f3f4f6 !important;
    border: 1px solid #e5e7eb !important;
    border-radius: 9999px !important;
    padding: 2px 10px !important;
    margin-top: 4px !important;
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
    height: calc(100vh - 73px); /* Hauteur de l'en-tête compact */
    background: #f8f9fa;
    margin-top: 0 !important;
    gap: 0 !important;
}
.main-content {
    gap: 0 !important;
    padding-top: 0 !important;
}
/* Bouton « Conversations » : panneau d'historique masqué */
body.nsql-sidebar-hidden #conv-sidebar {
    display: none !important;
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
/* Corbeille native (« Effacer la conversation ») du Chatbot supprimée */
#conv-chat .icon-button-wrapper.top-panel { display: none !important; }
/* Mode « Sans SQL » : les blocs SQL sont masqués à l'affichage uniquement */
body.nsql-hide-sql #conv-chat .code_wrap:has(code.language-sql) { display: none !important; }
/* Indicateur « l'IA rédige sa réponse » (message temporaire) */
.typing-indicator {
    display: inline-flex;
    gap: 4px;
    align-items: center;
    padding: 4px 2px;
}
.typing-indicator span {
    width: 7px;
    height: 7px;
    border-radius: 50%;
    background: #9ca3af;
    animation: nsql-typing 1.2s infinite ease-in-out;
}
.typing-indicator span:nth-child(2) { animation-delay: 0.2s; }
.typing-indicator span:nth-child(3) { animation-delay: 0.4s; }
@keyframes nsql-typing {
    0%, 80%, 100% { opacity: 0.3; transform: translateY(0); }
    40% { opacity: 1; transform: translateY(-3px); }
}
/* Message de bienvenue (placeholder du Chatbot quand la discussion est vide) */
#conv-chat .placeholder-content, #conv-chat .placeholder {
    width: 100%;
}
#conv-chat .welcome-box {
    box-shadow: none !important;
}
/* Champ de saisie : une seule bulle arrondie, sans cadre intérieur */
#conv-input-row {
    position: relative;
    border: 1px solid #e5e7eb;
    border-radius: 24px;
    background: #ffffff;
    align-items: center;
    padding: 4px 8px;
    box-shadow: 0 2px 6px rgba(0,0,0,0.05);
    gap: 0 !important;
    flex-wrap: nowrap !important;
}
#conv-input-row > .block,
#conv-input-row label,
#conv-input-row .input-container {
    border: none !important;
    box-shadow: none !important;
    background: transparent !important;
}
#conv-input-row > .block {
    padding: 0 !important;
}
#conv-input-row textarea {
    border: none !important;
    box-shadow: none !important;
    background: transparent !important;
    padding-top: 12px !important;
}
/* Trait vertical entre le texte et le bouton d'envoi */
#conv-input-row .send-btn {
    position: relative;
    margin-left: 21px !important;
    overflow: visible !important;
}
#conv-input-row .send-btn::before {
    content: "";
    position: absolute;
    left: -12px;
    top: 4px;
    bottom: 4px;
    width: 1px;
    background: #d1d5db;
}
#conv-input-row .send-btn {
    border-radius: 50% !important;
    width: 36px !important;
    height: 36px !important;
    min-width: 36px !important;
    padding: 0 !important;
    margin-right: 4px !important;
    display: flex;
    justify-content: center;
    align-items: center;
    background: #111827 !important;
    color: white !important;
    border: none !important;
    flex: 0 0 36px !important;
}
.sidebar-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    font-weight: 600;
    margin-bottom: 16px;
}
.new-chat-btn {
    width: 100% !important;
    height: 38px !important;
    margin-bottom: 16px !important;
    border: 1px solid #d1d5db !important;
    border-radius: 8px !important;
    background: #ffffff !important;
    color: #111827 !important;
    font-size: 14px !important;
    font-weight: 500 !important;
    box-shadow: none !important;
    flex: 0 0 auto !important;
}
.new-chat-btn:hover {
    background: #f3f4f6 !important;
}
/* --- Liste des conversations (HTML) --- */
.conv-list {
    flex-grow: 1;
    overflow-y: auto;
    min-height: 0;
    padding: 0 !important;
}
.conv-group-title {
    font-size: 12px;
    color: #6b7280;
    margin: 12px 0 6px 4px;
}
.conv-group-title:first-child { margin-top: 0; }
.conv-empty {
    font-size: 13px;
    color: #9ca3af;
    padding: 8px 4px;
}
.conv-item {
    position: relative;
    display: flex;
    align-items: center;
    gap: 4px;
    padding: 8px 6px 8px 12px;
    border-radius: 8px;
    cursor: pointer;
    font-size: 13px;
    color: #374151;
    margin-bottom: 2px;
    outline: none;
}
.conv-item:hover, .conv-item:focus-visible { background: #eef0f3; }
.conv-item.active { background: #e5e7eb; font-weight: 600; color: #111827; }
.conv-title {
    flex: 1 1 auto;
    min-width: 0;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}
.conv-rename-input {
    flex: 1 1 auto;
    min-width: 0;
    font-size: 13px;
    padding: 2px 6px;
    border: 1px solid #9ca3af;
    border-radius: 6px;
    background: #ffffff;
}
.conv-menu-btn {
    flex: 0 0 auto;
    visibility: hidden;
    width: 26px;
    height: 26px;
    border: none;
    border-radius: 6px;
    background: transparent;
    color: #4b5563;
    font-size: 16px;
    line-height: 1;
    cursor: pointer;
}
.conv-item:hover .conv-menu-btn,
.conv-item:focus-within .conv-menu-btn,
.conv-item.menu-open .conv-menu-btn { visibility: visible; }
.conv-menu-btn:hover { background: #d1d5db; }
/* Neutralise les marges/paddings « prose » de Gradio : « ⋯ » centré verticalement
   avec le titre et calé à droite dans la même colonne, quel que soit le titre. */
.conv-list .conv-item .conv-menu-btn {
    margin: 0 !important;
    padding: 0 !important;
    width: 26px !important;
    min-width: 26px !important;
    height: 26px !important;
    flex: 0 0 26px !important;
    display: inline-flex !important;
    align-items: center !important;
    justify-content: center !important;
    align-self: center !important;
    margin-left: auto !important;
    line-height: 1 !important;
}
.conv-list .conv-item .conv-menu button {
    margin: 0 !important;
}
/* Écrans tactiles (pas de survol) : le menu « ⋯ » reste accessible */
@media (hover: none) {
    .conv-menu-btn { visibility: visible; }
}
.conv-menu {
    display: none;
    position: absolute;
    right: 4px;
    top: calc(100% - 2px);
    z-index: 20;
    min-width: 140px;
    padding: 4px;
    background: #ffffff;
    border: 1px solid #e5e7eb;
    border-radius: 8px;
    box-shadow: 0 6px 16px rgba(0, 0, 0, 0.12);
}
.conv-item.menu-open .conv-menu { display: block; }
.conv-menu button {
    display: block;
    width: 100%;
    text-align: left;
    padding: 7px 10px;
    border: none;
    border-radius: 6px;
    background: transparent;
    font-size: 13px;
    font-weight: 400;
    color: #111827;
    cursor: pointer;
}
.conv-menu button:hover { background: #f3f4f6; }
.conv-menu button.danger { color: #dc2626; }
.conv-menu button.danger:hover { background: #fef2f2; }
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
    gap: 10px !important;
    margin: 0 !important;
    padding: 0 !important;
    flex-wrap: nowrap !important;
}
/* Nom de l'utilisateur centré dans l'en-tête (horizontalement et verticalement) */
.block.header-user-html {
    position: absolute !important;
    left: 50%;
    top: 50%;
    transform: translate(-50%, -50%);
    width: auto !important;
    max-width: 40vw;
    pointer-events: none;
    z-index: 1;
}
.prose.header-user-html {
    position: static !important;
    transform: none !important;
}
.header-user-name {
    display: block;
    font-size: 18px;
    font-weight: 600;
    color: #111827;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}
.header-btn {
    flex: 0 0 auto !important;
    width: auto !important;
    min-width: 0 !important;
    height: 40px !important;
    padding: 0 18px !important;
    font-size: 14px !important;
    font-weight: 500 !important;
    border-radius: 8px !important;
    white-space: nowrap !important;
    align-self: center !important;
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
    flex: 0 0 auto !important;
    width: auto !important;
}
.csv-download-btn:disabled, .csv-download-btn[disabled] {
    background: #e5e7eb !important;
    color: #9ca3af !important;
    cursor: not-allowed !important;
}
/* Radios à gauche, bouton CSV calé à droite, alignés verticalement */
.chat-toolbar { flex-wrap: nowrap !important; }
.chat-toolbar-left { justify-content: flex-start !important; align-items: center !important; }
.chat-toolbar-right { justify-content: flex-end !important; align-items: center !important; }
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
    return f'<span class="header-user-name">{full_name}</span>'

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
    else:
        nom_util = getattr(user, "nom_util", "") or ""
        identifiant = nom_util.strip(".") or full_name.lower().replace(" ", "-") or "utilisateur"

    escaped_full_name = html.escape(full_name)
    escaped_id = html.escape(identifiant)
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

    # RGPD consent date
    rgpd_at = getattr(user, "rgpd_accepted_at", None)
    if rgpd_at:
        if isinstance(rgpd_at, str):
            try:
                rgpd_at = datetime.fromisoformat(rgpd_at)
            except Exception:
                pass
        rgpd_str = rgpd_at.strftime("%d/%m/%Y") if hasattr(rgpd_at, "strftime") else str(rgpd_at)
        rgpd_badge = f'<div class="profile-rgpd-badge">🛡️ Consentement RGPD : {rgpd_str}</div>'
    else:
        rgpd_badge = '<div class="profile-rgpd-badge">🛡️ Consentement RGPD : Actif</div>'

    return (
        '<div class="profile-header">\n'
        f'    <div class="profile-name">{escaped_full_name}</div>\n'
        f'    <div class="profile-id">{escaped_id}</div>\n'
        '    <div class="profile-role">\n'
        f'        {badge_html}\n'
        f'        {rgpd_badge}\n'
        '    </div>\n'
        f'{stats_html}\n'
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
    if db_ok and not status.get("mariadb_queries", True):
        db_text += " — accès aux requêtes à configurer"

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
            '                <li><strong>Précisez les intitulés :</strong> indiquez le nom complet du cours ou de la matière (ex. Qualité de développement).</li>\n'
            '                <li><strong>Spécifiez le type de séance :</strong> ciblez les cours magistraux (CM), travaux dirigés (TD) ou travaux pratiques (TP).</li>\n'
            '                <li><strong>Évitez les abréviations :</strong> formulez clairement votre demande pour obtenir une réponse précise.</li>\n'
            '                <li><strong>Exemples de questions :</strong>\n'
            '                    <ul>\n'
            '                        <li>Quels enseignants donnent des TP dans le cours Qualité de développement ?</li>\n'
            '                        <li>Quel est le volume d\'heures de cours magistraux dispensé par enseignant ?</li>\n'
            '                        <li>Quelles sont les matières dispensées au semestre 1 ?</li>\n'
            '                        <li>Donne-moi la liste des enseignants vacataires.</li>\n'
            '                    </ul>\n'
            '                </li>\n'
            '            </ul>\n'
            '        </div>\n'
            '    </details>\n'
        )
    return (
        '<div class="welcome-box">\n'
        f'    <h2 class="welcome-title">Bienvenue {prenom_str}</h2>\n'
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


def _sql_block(sql: str) -> str:
    """Bloc Markdown numéroté affichant la requête SQL générée."""
    lines = sql.strip().split("\n")
    code_lines = [f"{i+1:>3} │ {line}" for i, line in enumerate(lines)]
    return f"```sql\n{chr(10).join(code_lines)}\n```"


def _format_bot_response(sql: str | None, results: list[dict] | None, simplified: bool = False, summary: str | None = None) -> str:
    """Format query, French synthesis, and SQL results table into Markdown."""
    if not sql and not results:
        return "Desole, je n'ai pas pu comprendre la demande ou aucune donnee n'a ete trouvee."
    
    md_parts = []
    if sql and not simplified:
        md_parts.append(_sql_block(sql))

    if summary:
        md_parts.append(summary.strip())

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


# Message temporaire affiché pendant la génération d'une réponse. Il fait partie
# de l'historique affiché (et non de l'état de chargement Gradio) : aucun autre
# événement ne peut donc l'effacer avant l'arrivée de la réponse.
TYPING_HTML = '<div class="typing-indicator" aria-label="Réponse en cours"><span></span><span></span><span></span></div>'


def _is_typing(message: Any) -> bool:
    # Gradio peut renvoyer le contenu sous une autre forme (liste de parties,
    # HTML normalisé) : on cherche donc le marqueur plutôt qu'une égalité stricte.
    if not isinstance(message, dict) or message.get("role") != "assistant":
        return False
    return "typing-indicator" in _message_text(message.get("content", ""))


def _message_text(raw_msg: Any) -> str:
    """Texte brut d'un message de l'historique Gradio (str, liste de parties ou tuple)."""
    if isinstance(raw_msg, list):
        return " ".join(m.get("text", str(m)) if isinstance(m, dict) else str(m) for m in raw_msg)
    if isinstance(raw_msg, tuple):
        return str(raw_msg[0]) if raw_msg else ""
    return str(raw_msg)


def _history_from_messages(messages) -> list[dict]:
    """Historique Chatbot depuis la base, SQL toujours inclus.

    L'affichage du SQL est géré côté navigateur (mode « Sans SQL » = masqué en CSS) :
    les anciens messages enregistrés sans SQL le retrouvent ici.
    """
    history = []
    for m in messages:
        content = m.content
        if m.role == "assistant" and m.sql_generated and "```sql" not in content:
            content = f"{_sql_block(m.sql_generated)}\n\n{content}"
        history.append({"role": m.role, "content": content})
    return history


def _conv_list_html(conversations, active_cid: Optional[int] = None) -> str:
    """Liste HTML de l'historique, groupée par période, avec un menu « ⋯ » par discussion."""
    if not conversations:
        return '<div class="conv-empty">Aucune discussion pour le moment.</div>'
    parts = []
    current_group = None
    for conv in conversations:
        group = get_conv_period(conv.created_at) if isinstance(conv.created_at, datetime) else "Plus ancien"
        if group != current_group:
            parts.append(f'<div class="conv-group-title">{html.escape(group)}</div>')
            current_group = group
        title = html.escape(conv.title or "Sans titre", quote=True)
        active = " active" if conv.id == active_cid else ""
        parts.append(
            f'<div class="conv-item{active}" data-cid="{int(conv.id)}" data-title="{title}" '
            f'role="button" tabindex="0" title="{title}">'
            f'<span class="conv-title">{title}</span>'
            '<button type="button" class="conv-menu-btn" aria-label="Options de la discussion">⋯</button>'
            '<div class="conv-menu" role="menu">'
            '<button type="button" data-conv-action="rename" role="menuitem">Renommer</button>'
            '<button type="button" data-conv-action="delete" class="danger" role="menuitem">Supprimer</button>'
            '</div></div>'
        )
    return "".join(parts)


# Discussion affichée dans chaque onglet ouvert (clé : session Gradio).
# Une réponse qui arrive après un changement de discussion (« + », clic sur
# l'historique) est enregistrée en base mais n'écrase pas la discussion affichée.
_SESSION_VIEWS: dict[str, dict[str, Any]] = {}


def _view(request: Optional[gr.Request]) -> dict[str, Any]:
    key = getattr(request, "session_hash", None) or "__no_session__"
    return _SESSION_VIEWS.setdefault(key, {"token": 0, "cid": None, "pending": set()})


def _set_view(request: Optional[gr.Request], cid: Optional[int]) -> None:
    view = _view(request)
    view["token"] += 1
    view["cid"] = cid


def _forget_view(request: Optional[gr.Request]) -> None:
    _SESSION_VIEWS.pop(getattr(request, "session_hash", None) or "__no_session__", None)


def build_app():
    auth_service = AuthService()
    conv_storage = ConversationStorage()
    conv_storage.ensure_schema()

    with gr.Blocks(title="NaturSQL Profile") as demo:
        session_user = gr.State(None)
        current_conv_id = gr.State(None)

        # En-tête (Header)
        with gr.Column(elem_classes=["header"]):
            with gr.Row(elem_classes=["header-bar"]):
                gr.HTML(logo_html, scale=1)
                # Nom centré dans l'en-tête (positionné en CSS, vide si déconnecté)
                header_user_name = gr.HTML(elem_classes=["header-user-html"])
                with gr.Row(elem_classes=["header-profile-row"], visible=False) as header_profile_container:
                    conversations_btn = gr.Button("Accueil", variant="secondary", elem_classes=["header-btn"])
                    go_to_profile_btn = gr.Button("Mon Profil", variant="secondary", elem_classes=["header-btn"])

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
                    
                    signup_rgpd = gr.Checkbox(
                        label="J'ai lu et j'accepte la politique de confidentialité et les CGU *",
                        value=False,
                        elem_id="signup-rgpd-cb"
                    )
                    gr.HTML('<div style="font-size:11px;color:#6b7280;margin:-8px 0 12px 2px;">En cochant cette case, vous consentez au traitement de vos données conformément aux <a href="#" onclick="document.getElementById(\'btn-show-privacy\').click(); return false;" style="text-decoration:underline;color:#2563eb;">politique de confidentialité</a> et <a href="#" onclick="document.getElementById(\'btn-show-cgu\').click(); return false;" style="text-decoration:underline;color:#2563eb;">CGU</a> de NaturSQL.</div>')

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
                        '<div class="danger-zone-desc">La suppression de votre compte efface définitivement toutes vos conversations et données associées. Conformément à l\'Art. 7-3 du RGPD, le retrait de votre consentement s\'exerce par cette suppression.</div>'
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

            with gr.Column(visible=False, elem_classes=["profile-card"]) as legal_registry_page:
                gr.Markdown(load_markdown("registre-traitements.md"))
                btn_back_4 = gr.Button("Retour")

            # --- Page de Conversation ---
            with gr.Column(visible=False, elem_id="conv-page") as conversation_page:
                with gr.Column(elem_id="conv-sidebar"):
                    new_chat_btn = gr.Button("+ Nouvelle conversation", elem_classes=["new-chat-btn"])
                    conv_list_html = gr.HTML(_conv_list_html([]), elem_classes=["conv-list"])
                    # Canal caché : le JavaScript de l'historique y écrit l'action (sélection,
                    # renommage, suppression) puis clique sur le bouton caché.
                    conv_action_input = gr.Textbox(elem_id="conv-action-input", elem_classes=["hidden-btn"], show_label=False, container=False)
                    conv_action_btn = gr.Button(elem_id="conv-action-btn", elem_classes=["hidden-btn"])

                with gr.Column(elem_id="conv-main"):
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
                                # Toujours visible, grisé tant qu'aucun résultat n'est exportable
                                interactive=False,
                                elem_classes=["csv-download-btn"],
                            )

                    chatbot = gr.Chatbot(
                        elem_id="conv-chat",
                        show_label=False,
                        buttons=[],
                        feedback_options=None,
                        # Message de bienvenue : affiché tant que la discussion est vide
                        placeholder=_welcome_banner_html(),
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
                <div style="display: flex; align-items: flex-start; padding-left: 2rem; gap: 4rem;">
                    <div>{footer_logo}</div>
                    <div style="line-height: 1.8; color: #1f2937;">
                        <strong>Aide</strong><br>
                        <a href="#" onclick="document.getElementById('btn-show-doc').click(); return false;">Documentation</a>
                    </div>
                    <div style="line-height: 1.8; color: #1f2937;">
                        <strong>Légal</strong><br>
                        <a href="#" onclick="document.getElementById('btn-show-mentions').click(); return false;">Mentions légales</a><br>
                        <a href="#" onclick="document.getElementById('btn-show-privacy').click(); return false;">Politique de confidentialité</a><br>
                        <a href="#" onclick="document.getElementById('btn-show-cgu').click(); return false;">Conditions générales d'utilisation</a><br>
                        <a href="#" onclick="document.getElementById('btn-show-registry').click(); return false;">Registre des traitements (Art. 30)</a>
                    </div>
                </div>
                """, scale=3)
                system_status_box = gr.HTML("", scale=1)
            
            # Boutons invisibles pour déclencher l'affichage des pages depuis le footer HTML
            btn_go_home = gr.Button(elem_id="btn-go-home", elem_classes=["hidden-btn"])
            btn_show_doc = gr.Button(elem_id="btn-show-doc", elem_classes=["hidden-btn"])
            btn_show_mentions = gr.Button(elem_id="btn-show-mentions", elem_classes=["hidden-btn"])
            btn_show_privacy = gr.Button(elem_id="btn-show-privacy", elem_classes=["hidden-btn"])
            btn_show_cgu = gr.Button(elem_id="btn-show-cgu", elem_classes=["hidden-btn"])
            btn_show_registry = gr.Button(elem_id="btn-show-registry", elem_classes=["hidden-btn"])

        status_timer = gr.Timer(30)
        status_timer.tick(_status_badges_html, outputs=[system_status_box], show_progress="hidden", api_name=False)
        demo.load(_status_badges_html, outputs=[system_status_box], show_progress="hidden", api_name=False)

        # --- Callbacks ---

        def go_to_page(page_name, session):
            s_in = s_up = prof = leg_m = leg_p = leg_c = leg_r = doc = conv = gr.update(visible=False)
            if page_name == "mentions": leg_m = gr.update(visible=True)
            elif page_name == "privacy": leg_p = gr.update(visible=True)
            elif page_name == "cgu": leg_c = gr.update(visible=True)
            elif page_name == "registry": leg_r = gr.update(visible=True)
            elif page_name == "doc": doc = gr.update(visible=True)
            elif page_name == "home":
                if session is None: s_in = gr.update(visible=True)
                else: conv = gr.update(visible=True)
            elif page_name == "profile":
                if session is not None: prof = gr.update(visible=True)
            return s_in, s_up, prof, leg_m, leg_p, leg_c, leg_r, doc, conv

        page_outputs = [signin_page, signup_page, profile_page, legal_mentions_page, legal_privacy_page, legal_cgu_page, legal_registry_page, doc_page, conversation_page]
        
        btn_go_home.click(lambda s: go_to_page("home", s), inputs=[session_user], outputs=page_outputs)
        btn_show_doc.click(lambda s: go_to_page("doc", s), inputs=[session_user], outputs=page_outputs)
        btn_show_mentions.click(lambda s: go_to_page("mentions", s), inputs=[session_user], outputs=page_outputs)
        btn_show_privacy.click(lambda s: go_to_page("privacy", s), inputs=[session_user], outputs=page_outputs)
        btn_show_cgu.click(lambda s: go_to_page("cgu", s), inputs=[session_user], outputs=page_outputs)
        btn_show_registry.click(lambda s: go_to_page("registry", s), inputs=[session_user], outputs=page_outputs)
        
        btn_back_1.click(lambda s: go_to_page("home", s), inputs=[session_user], outputs=page_outputs)
        btn_back_2.click(lambda s: go_to_page("home", s), inputs=[session_user], outputs=page_outputs)
        btn_back_3.click(lambda s: go_to_page("home", s), inputs=[session_user], outputs=page_outputs)
        btn_back_4.click(lambda s: go_to_page("home", s), inputs=[session_user], outputs=page_outputs)
        btn_back_doc.click(lambda s: go_to_page("home", s), inputs=[session_user], outputs=page_outputs)
        btn_back_to_conv.click(lambda s: go_to_page("home", s), inputs=[session_user], outputs=page_outputs)

        _profile_card_md = _profile_card_html

        def do_sign_in(first_name, last_name, password, request: gr.Request = None):
            result = auth_service.login(first_name, last_name, password)
            if not result.ok:
                return (
                    gr.update(), gr.update(visible=True), gr.update(visible=False), gr.update(visible=False),
                    gr.update(visible=False), _status_html(result.message, ok=False), "", "",
                    [], _conv_list_html([]), None, "", gr.update(visible=False),
                    gr.update(), gr.update(value=None, interactive=False)
                )
            user = result.user
            gr.Info(result.message)
            _set_view(request, None)

            conversations = conv_storage.list_conversations(user.nom_util)

            header_user_name_str = _header_user_html(user)
            try:
                stats = conv_storage.get_user_activity_stats(user.nom_util)
            except Exception:
                stats = {}

            return (
                user, gr.update(visible=False), gr.update(visible=False), gr.update(visible=False),
                gr.update(visible=True), "", _profile_card_md(user, stats), "",
                gr.update(value=[], placeholder=_welcome_banner_html(user)), _conv_list_html(conversations), None,
                header_user_name_str, gr.update(visible=True),
                gr.update(value=_status_badges_html()), gr.update(value=None, interactive=False)
            )

        signin_button.click(
            do_sign_in,
            inputs=[signin_first_name, signin_last_name, signin_password],
            outputs=[
                session_user, signin_page, signup_page, profile_page, conversation_page,
                signin_status, profile_info, profile_status,
                chatbot, conv_list_html, current_conv_id, header_user_name, header_profile_container,
                system_status_box, csv_download_btn
            ]
        )

        def go_to_profile_view(user):
            s_in, s_up, prof, leg_m, leg_p, leg_c, leg_r, doc, conv = go_to_page("profile", user)
            if user is None:
                return s_in, s_up, prof, leg_m, leg_p, leg_c, leg_r, doc, conv, gr.update()
            try:
                fresh_stats = conv_storage.get_user_activity_stats(user.nom_util)
            except Exception:
                fresh_stats = {}
            card_html = _profile_card_html(user, fresh_stats)
            return s_in, s_up, prof, leg_m, leg_p, leg_c, leg_r, doc, conv, card_html

        go_to_profile_btn.click(
            go_to_profile_view,
            inputs=[session_user],
            outputs=page_outputs + [profile_info],
        )

        def do_sign_up(first_name, last_name, password, confirm, rgpd_consent):
            result = auth_service.register(password, confirm, first_name, last_name, rgpd_consent=rgpd_consent)
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
                signup_rgpd,
            ],
            outputs=[signup_page, signin_page, signup_status, signin_status],
        )

        def show_signup():
            return gr.update(visible=False), gr.update(visible=True), "", False

        def show_signin():
            return gr.update(visible=False), gr.update(visible=True), ""

        go_to_signup.click(show_signup, outputs=[signin_page, signup_page, signup_status, signup_rgpd])
        go_to_signin.click(show_signin, outputs=[signup_page, signin_page, signin_status])

        def do_disconnect(request: gr.Request = None):
            _forget_view(request)
            return (
                None, gr.update(visible=True), gr.update(visible=False), gr.update(visible=False), "", "", "",
                gr.update(visible=False, open=False), gr.update(visible=True), "",
                gr.update(value=[], placeholder=_welcome_banner_html()), _conv_list_html([]), None, "", gr.update(visible=False),
                gr.update(value=_status_badges_html()), gr.update(value=None, interactive=False)
            )

        disconnect_button.click(
            do_disconnect,
            outputs=[
                session_user, signin_page, profile_page, conversation_page, signin_first_name, signin_last_name, signin_password,
                profile_edit_form, edit_profile_button, profile_status,
                chatbot, conv_list_html, current_conv_id, header_user_name, header_profile_container,
                system_status_box, csv_download_btn
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

        def do_delete_account(user, password, request: gr.Request = None):
            if user is None:
                gr.Warning("Session expirée ou invalide.")
                return (
                    user, gr.update(), gr.update(), gr.update(),
                    gr.update(), gr.update(), "",
                    gr.update(), gr.update(), gr.update(),
                    gr.update(), gr.update()
                )
            result = auth_service.delete_account(user, password)
            if not result.ok:
                gr.Warning(result.message)
                return (
                    user, gr.update(), gr.update(), gr.update(),
                    gr.update(visible=True), gr.update(visible=False), "",
                    gr.update(), gr.update(), gr.update(),
                    gr.update(), gr.update()
                )
            gr.Info("Votre compte et toutes vos données ont été définitivement supprimés.")
            _forget_view(request)
            return (
                None, gr.update(visible=True), gr.update(visible=False), gr.update(visible=False),
                gr.update(visible=False), gr.update(visible=True), "",
                gr.update(value=[], placeholder=_welcome_banner_html()), _conv_list_html([]), None,
                "", gr.update(visible=False)
            )

        btn_confirm_delete_account.click(
            do_delete_account,
            inputs=[session_user, delete_password_input],
            outputs=[
                session_user, signin_page, profile_page, conversation_page,
                delete_confirm_section, btn_start_delete_account, delete_password_input,
                chatbot, conv_list_html, current_conv_id,
                header_user_name, header_profile_container
            ],
        )
        # -------------------- Conversation: Core Chat Logic -------------------

        def _owned_conversations(user):
            return conv_storage.list_conversations(user.nom_util) if user else []

        def add_user_msg(message, history):
            """Étape 1 : affiche la question et l'indicateur « réponse en cours »."""
            if not message or not message.strip():
                # Erreur silencieuse : stoppe la chaîne (.success) sans message à l'écran.
                raise gr.Error("Message vide.", visible=False)
            if history and _is_typing(history[-1]):
                raise gr.Error("Une réponse est déjà en cours de génération dans cette discussion. Patientez avant d'envoyer une nouvelle question.")
            return "", history + [{"role": "user", "content": message}, {"role": "assistant", "content": TYPING_HTML}]

        async def bot_respond(user, history, current_cid, request: gr.Request = None):
            """Étape 2 : génère la réponse, l'enregistre et met à jour l'historique.

            Si l'utilisateur a changé de discussion entre-temps, la réponse est
            enregistrée dans sa conversation mais la discussion affichée n'est pas touchée.
            """
            if not user or not history:
                yield gr.update(), gr.update(), gr.update(), gr.update()
                return

            base = history[:-1] if _is_typing(history[-1]) else list(history)
            try:
                async for update in _respond(user, base, current_cid, request):
                    yield update
            except Exception as e:
                # Filet de sécurité : l'indicateur de chargement ne doit jamais rester bloqué.
                _view(request)["pending"].discard(current_cid)
                yield base + [{"role": "assistant", "content": f"**Erreur :** {e}"}], gr.update(), gr.update(), gr.update()

        async def _respond(user, base, current_cid, request):
            user_msg = _message_text(base[-1]["content"])
            view = _view(request)
            token = view["token"]

            if current_cid is None:
                # La discussion apparaît dans l'historique dès le premier message,
                # avec un titre provisoire remplacé ensuite par le titre de l'IA.
                provisional = user_msg[:40] + ("..." if len(user_msg) > 40 else "")
                conv = await asyncio.to_thread(conv_storage.create_conversation, user.nom_util, provisional)
                cid = conv.id
                if view["token"] == token:
                    view["cid"] = cid
                view["pending"].add(cid)
                await asyncio.to_thread(conv_storage.add_message, cid, "user", user_msg)
                conversations = await asyncio.to_thread(_owned_conversations, user)
                yield (
                    gr.update(),
                    cid if view["cid"] == cid else gr.update(),
                    _conv_list_html(conversations, view["cid"]),
                    gr.update(),
                )
                try:
                    title = await LLMClient().generate_title(user_msg)
                    if title and title.strip():
                        await asyncio.to_thread(conv_storage.rename_conversation, cid, title)
                        conversations = await asyncio.to_thread(_owned_conversations, user)
                        yield gr.update(), gr.update(), _conv_list_html(conversations, view["cid"]), gr.update()
                except Exception:
                    pass  # Le titre provisoire reste en place.
            else:
                cid = current_cid
                view["pending"].add(cid)
                await asyncio.to_thread(conv_storage.add_message, cid, "user", user_msg)

            csv_file = None
            try:
                sql_str, results = await ask_database(user_msg)
                try:
                    summary = await LLMClient().summarize_results(user_msg, results)
                except Exception:
                    # Preserve useful data even if the second Ollama call fails.
                    summary = "Les résultats sont disponibles ci-dessous, mais la synthèse est temporairement indisponible."
                # Le SQL est toujours inclus : le mode « Sans SQL » le masque à l'affichage.
                bot_md = _format_bot_response(sql_str, results, summary=summary)
                await asyncio.to_thread(conv_storage.add_message, cid, "assistant", bot_md, sql_str)
                if results:
                    csv_file = create_results_csv(results)
            except Exception as e:
                bot_md = f"**Erreur :** {str(e)}"
                await asyncio.to_thread(conv_storage.add_message, cid, "assistant", bot_md)
            finally:
                view["pending"].discard(cid)

            conversations = await asyncio.to_thread(_owned_conversations, user)
            # Mise à jour de l'écran si l'utilisateur n'a pas changé de discussion
            # depuis l'envoi, ou s'il est revenu sur celle-ci entre-temps.
            still_here = view["token"] == token or view["cid"] == cid
            list_html = _conv_list_html(conversations, cid if still_here else view["cid"])

            if not still_here:
                # L'utilisateur regarde une autre discussion : on ne l'écrase pas.
                yield gr.update(), gr.update(), list_html, gr.update()
                return

            csv_btn_update = gr.update(value=csv_file, interactive=True) if csv_file else gr.update(value=None, interactive=False)
            yield base + [{"role": "assistant", "content": bot_md}], cid, list_html, csv_btn_update

        # Plusieurs réponses peuvent être générées en parallèle (autres discussions,
        # autres utilisateurs) : pas de file d'attente unique ni d'envoi ignoré.
        for trigger in (chat_input.submit, send_btn.click):
            trigger(
                add_user_msg,
                inputs=[chat_input, chatbot],
                outputs=[chat_input, chatbot],
                show_progress="hidden",
                trigger_mode="multiple",
                concurrency_limit=None,
            ).success(
                bot_respond,
                inputs=[session_user, chatbot, current_conv_id],
                outputs=[chatbot, current_conv_id, conv_list_html, csv_download_btn],
                show_progress="hidden",
                # Sans « multiple », Gradio ignore la réponse demandée si une autre
                # réponse est encore en cours (cause du bug « + » puis envoi).
                trigger_mode="multiple",
                concurrency_limit=None,
            )

        def do_new_conversation(user, request: gr.Request = None):
            _set_view(request, None)
            return [], None, _conv_list_html(_owned_conversations(user)), gr.update(value=None, interactive=False)

        new_chat_btn.click(
            do_new_conversation,
            inputs=[session_user],
            outputs=[chatbot, current_conv_id, conv_list_html, csv_download_btn],
            show_progress="hidden",
        )

        def do_conv_action(action_json, user, current_cid, request: gr.Request = None):
            """Sélection, renommage ou suppression d'une discussion depuis l'historique."""
            no_change = (gr.update(), gr.update(), gr.update(), gr.update())
            if not user or not action_json:
                return no_change
            try:
                payload = json.loads(action_json)
                action = payload.get("action")
                cid = int(payload.get("cid"))
            except (ValueError, TypeError, AttributeError):
                return no_change

            # Seules les discussions de l'utilisateur connecté sont modifiables.
            conversations = _owned_conversations(user)
            if cid not in {c.id for c in conversations}:
                gr.Warning("Discussion introuvable.")
                return gr.update(), gr.update(), _conv_list_html(conversations, current_cid), gr.update()

            if action == "select":
                _set_view(request, cid)
                history = _history_from_messages(conv_storage.get_messages(cid))
                if cid in _view(request)["pending"]:
                    history.append({"role": "assistant", "content": TYPING_HTML})
                return history, cid, _conv_list_html(conversations, cid), gr.update(value=None, interactive=False)

            if action == "rename":
                title = str(payload.get("title") or "").strip()
                if title and conv_storage.rename_conversation(cid, title):
                    gr.Info("Discussion renommée.")
                return gr.update(), gr.update(), _conv_list_html(_owned_conversations(user), current_cid), gr.update()

            if action == "delete":
                conv_storage.delete_conversation(cid)
                gr.Info("Discussion supprimée.")
                remaining = _owned_conversations(user)
                if cid == current_cid:
                    _set_view(request, None)
                    return [], None, _conv_list_html(remaining), gr.update(value=None, interactive=False)
                return gr.update(), gr.update(), _conv_list_html(remaining, current_cid), gr.update()

            return no_change

        conv_action_btn.click(
            do_conv_action,
            inputs=[conv_action_input, session_user, current_conv_id],
            outputs=[chatbot, current_conv_id, conv_list_html, csv_download_btn],
            show_progress="hidden",
        )

        # Bascule Avec SQL / Sans SQL : uniquement côté navigateur (voir toggle_sql_js).
        view_mode.change(None, inputs=[view_mode], outputs=None, js=toggle_sql_js)

        # Bouton « Conversations » : ouvre/ferme le panneau (JS) et affiche la page de discussion.
        conversations_btn.click(None, js=toggle_sidebar_js)
        conversations_btn.click(lambda s: go_to_page("home", s), inputs=[session_user], outputs=page_outputs, show_progress="hidden")

        demo.unload(_forget_view)

    return demo

if __name__ == "__main__":
    build_app().launch(server_name="0.0.0.0", server_port=7860, share=True, theme=theme, css=custom_css, js=force_light_mode_js)
