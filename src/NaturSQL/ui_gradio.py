"""Gradio application entry point."""

from __future__ import annotations
import os
import base64
import gradio as gr
from .service.auth import AuthService
from .storage.conversations import ConversationStorage
from .service.core import ask_database

def load_markdown(filename: str) -> str:
    path = os.path.join(os.path.dirname(__file__), "docs", "legal", filename)
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    return f"Fichier {filename} introuvable."

# Load logo as base64 for embedding in HTML
logo_path = os.path.join(os.path.dirname(__file__), "logo.png")
try:
    with open(logo_path, "rb") as f:
        b64_logo = base64.b64encode(f.read()).decode("utf-8")
    logo_html = f'<div style="display: flex; align-items: center; gap: 10px;"><img src="data:image/png;base64,{b64_logo}" style="height: 32px;" /> <h2 style="margin:0; font-weight:600; color:black;">NaturSQL</h2></div>'
except Exception:
    b64_logo = ""
    logo_html = '<h2 style="margin:0; font-weight:600; color:black;">NaturSQL</h2>'

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
    margin-bottom: 3rem !important;
}
.main-content {
    min-height: calc(100vh - 320px); 
}
.auth-card {
    background: white;
    padding: 2.5rem;
    border-radius: 0.5rem;
    box-shadow: 0 4px 10px rgba(0, 0, 0, 0.05);
    margin: 0 auto;
    max-width: 450px;
}
.profile-card {
    background: white;
    padding: 2.5rem;
    border-radius: 0.5rem;
    box-shadow: 0 4px 10px rgba(0, 0, 0, 0.05);
    margin: 0 auto;
    max-width: 500px;
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

/* --- Conversation Page CSS --- */
#conv-page {
    display: flex;
    flex-direction: row;
    width: 100vw;
    margin-left: calc(-50vw + 50%) !important;
    height: calc(100vh - 180px); /* Fill space between header and footer */
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
    font-size: 20px !important;
    cursor: pointer;
    box-shadow: none !important;
    padding: 0 !important;
    min-width: 0 !important;
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
}
.chat-list {
    flex-grow: 1;
    overflow-y: auto;
}
.chat-list input[type="radio"] {
    display: none;
}
.chat-list label {
    display: block;
    padding: 8px 12px;
    cursor: pointer;
    border-radius: 6px;
    margin-bottom: 4px;
    font-size: 14px;
}
.chat-list label:hover {
    background: #e5e7eb;
}
.chat-list label.selected {
    background: #e5e7eb;
    font-weight: 600;
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
            gr.HTML(logo_html)

        # Contenu principal
        with gr.Column(elem_classes=["main-content"]):
            
            # --- Page de Connexion ---
            with gr.Column(visible=True) as signin_page:
                with gr.Column(elem_classes=["auth-card"]):
                    gr.Markdown("### Sign In", elem_classes=["text-center"])
                    gr.HTML('<div style="font-size:11px;color:#888;margin:-6px 0 10px 0;">Tous les champs sont obligatoires.</div>')
                    
                    signin_username = gr.Textbox(label="Identifiant *", placeholder="dupont.jean")
                    signin_password = gr.Textbox(label="Mot de passe *", type="password", placeholder="Mot de passe")
                    
                    signin_status = gr.HTML()
                    signin_button = gr.Button("Se connecter", variant="primary")
                    
                    with gr.Row(elem_classes=["auth-links"]):
                        go_to_signup = gr.Button("Créer un compte")
            
            # --- Page d'Inscription ---
            with gr.Column(visible=False) as signup_page:
                with gr.Column(elem_classes=["auth-card"]):
                    gr.Markdown("### Sign Up", elem_classes=["text-center"])
                    gr.HTML('<div style="font-size:11px;color:#888;margin:-6px 0 10px 0;">Tous les champs sont obligatoires. Votre identifiant de connexion (nom.prenom) sera généré automatiquement.</div>')
                    
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
                btn_back_to_conv = gr.Button("← Retour aux conversations", size="sm")
                with gr.Row():
                    gr.HTML('<img src="https://ui-avatars.com/api/?name=User&background=random" style="border-radius: 50%; width: 80px; height: 80px;" />')
                    profile_info = gr.Markdown("Chargement du profil...")
                
                profile_status = gr.HTML()
                
                with gr.Row():
                    edit_profile_button = gr.Button("Modifier le profil")
                    disconnect_button = gr.Button("Déconnexion", variant="stop")
                    save_profile_button = gr.Button("Enregistrer", visible=False, variant="primary")
                
                with gr.Column(visible=False) as profile_edit_form:
                    edit_first_name = gr.Textbox(label="Prénom *", placeholder="Jean")
                    edit_last_name = gr.Textbox(label="Nom *", placeholder="Dupont")

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
                        gr.HTML("<div>≡ NaturSQL</div>")
                        new_chat_btn = gr.Button("⊕", elem_classes=["new-chat-btn"])
                    
                    search_bar = gr.Textbox(placeholder="Search", show_label=False, elem_classes=["search-bar"])
                    gr.HTML('<div class="chat-list-title">Chats</div>')
                    
                    conv_radio = gr.Radio(choices=[], show_label=False, elem_classes=["chat-list"])
                    
                    with gr.Row(elem_classes=["user-info-sidebar"]):
                        sidebar_user_html = gr.HTML()
                        go_to_profile_btn = gr.Button("Profil", elem_classes=["profile-link-btn"])

                with gr.Column(elem_id="conv-main"):
                    chatbot = gr.Chatbot(
                        elem_id="conv-chat",
                        show_label=False,
                    )
                    with gr.Row(elem_id="conv-input-row"):
                        chat_input = gr.Textbox(
                            placeholder="What would you like to know?",
                            show_label=False,
                            container=False,
                            scale=9
                        )
                        send_btn = gr.Button("↑", min_width=50, scale=1)

        # Pied de page (Footer)
        with gr.Column(elem_classes=["footer"]):
            footer_logo = f'<img src="data:image/png;base64,{b64_logo}" style="height: 48px; margin-right: 4rem;" />' if b64_logo else ""
                
            gr.HTML(f"""
            <div style='display: flex; align-items: flex-start; padding-left: 2rem;'>
                <div>
                    {footer_logo}
                </div>
                <div style='line-height: 1.8; color: #1f2937;'>
                    <strong>Légal</strong><br>
                    <a href="#" style="color: #1f2937; text-decoration: none;" onclick="document.getElementById('btn-show-mentions').click(); return false;">Mentions légales</a><br>
                    <a href="#" style="color: #1f2937; text-decoration: none;" onclick="document.getElementById('btn-show-privacy').click(); return false;">Politique de confidentialité</a><br>
                    <a href="#" style="color: #1f2937; text-decoration: none;" onclick="document.getElementById('btn-show-cgu').click(); return false;">Conditions générales d'utilisation</a>
                </div>
            </div>
            """)
            
            # Boutons invisibles pour déclencher l'affichage des pages légales depuis le footer HTML
            btn_show_mentions = gr.Button(elem_id="btn-show-mentions", elem_classes=["hidden-btn"])
            btn_show_privacy = gr.Button(elem_id="btn-show-privacy", elem_classes=["hidden-btn"])
            btn_show_cgu = gr.Button(elem_id="btn-show-cgu", elem_classes=["hidden-btn"])

        # --- Callbacks ---

        def go_to_page(page_name, session):
            s_in = s_up = prof = leg_m = leg_p = leg_c = conv = gr.update(visible=False)
            if page_name == "mentions": leg_m = gr.update(visible=True)
            elif page_name == "privacy": leg_p = gr.update(visible=True)
            elif page_name == "cgu": leg_c = gr.update(visible=True)
            elif page_name == "home":
                if session is None: s_in = gr.update(visible=True)
                else: conv = gr.update(visible=True)
            elif page_name == "profile":
                if session is not None: prof = gr.update(visible=True)
            return s_in, s_up, prof, leg_m, leg_p, leg_c, conv

        page_outputs = [signin_page, signup_page, profile_page, legal_mentions_page, legal_privacy_page, legal_cgu_page, conversation_page]
        
        btn_show_mentions.click(lambda s: go_to_page("mentions", s), inputs=[session_user], outputs=page_outputs)
        btn_show_privacy.click(lambda s: go_to_page("privacy", s), inputs=[session_user], outputs=page_outputs)
        btn_show_cgu.click(lambda s: go_to_page("cgu", s), inputs=[session_user], outputs=page_outputs)
        
        btn_back_1.click(lambda s: go_to_page("home", s), inputs=[session_user], outputs=page_outputs)
        btn_back_2.click(lambda s: go_to_page("home", s), inputs=[session_user], outputs=page_outputs)
        btn_back_3.click(lambda s: go_to_page("home", s), inputs=[session_user], outputs=page_outputs)
        btn_back_to_conv.click(lambda s: go_to_page("home", s), inputs=[session_user], outputs=page_outputs)

        def _profile_card_md(user) -> str:
            if not user:
                return "Erreur de chargement"
            return f"**{user.full_name}**\n\nIdentifiant : {user.nom_util}"

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

        def do_sign_in(username, password):
            result = auth_service.login(username, password)
            if not result.ok:
                return (
                    gr.update(), gr.update(visible=True), gr.update(visible=False), gr.update(visible=False),
                    gr.update(visible=False), _status_html(result.message, ok=False), "", "",
                    [], gr.update(choices=[]), {}, None, ""
                )
            user = result.user
            gr.Info(result.message)
            
            conversations = conv_storage.list_conversations(user.nom_util)
            choices, conv_map = _build_conv_choices(conversations)
            
            sidebar_user_html_str = f'<img src="https://ui-avatars.com/api/?name={user.nom_util}&background=random" /> <span>{user.full_name}</span>'
            
            return (
                user, gr.update(visible=False), gr.update(visible=False), gr.update(visible=False),
                gr.update(visible=True), "", _profile_card_md(user), _status_html(result.message, ok=True),
                [], gr.update(choices=choices, value=None), conv_map, None, sidebar_user_html_str
            )

        signin_button.click(
            do_sign_in,
            inputs=[signin_username, signin_password],
            outputs=[
                session_user, signin_page, signup_page, profile_page, conversation_page,
                signin_status, profile_info, profile_status,
                chatbot, conv_radio, conv_id_map, current_conv_id, sidebar_user_html
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
                None, gr.update(visible=True), gr.update(visible=False), gr.update(visible=False), "", "",
                gr.update(visible=False), gr.update(visible=True), gr.update(visible=False), "",
                [], gr.update(choices=[]), {}, None, ""
            )

        disconnect_button.click(
            do_disconnect,
            outputs=[
                session_user, signin_page, profile_page, conversation_page, signin_username, signin_password,
                profile_edit_form, edit_profile_button, save_profile_button, profile_status,
                chatbot, conv_radio, conv_id_map, current_conv_id, sidebar_user_html
            ]
        )

        def start_edit(user):
            if user is None:
                return gr.update(), gr.update(), gr.update(visible=False), gr.update(visible=True)
            return user.prenom_ens, user.nom_ens, gr.update(visible=True), gr.update(visible=False)

        edit_profile_button.click(
            start_edit,
            inputs=session_user,
            outputs=[edit_first_name, edit_last_name, profile_edit_form, edit_profile_button]
        ).then(lambda: gr.update(visible=True), outputs=save_profile_button)

        def do_save_profile(user, first_name, last_name):
            if user is None:
                return (
                    user, _status_html("Session expirée, merci de vous reconnecter.", ok=False), "",
                    gr.update(visible=False), gr.update(visible=True), gr.update(visible=False)
                )
            result = auth_service.update_profile(user, first_name, last_name)
            if not result.ok:
                return (
                    user, _status_html(result.message, ok=False), _profile_card_md(user),
                    gr.update(visible=True), gr.update(visible=False), gr.update(visible=True)
                )
            updated_user = result.user
            gr.Info(result.message)
            return (
                updated_user, _status_html(result.message, ok=True), _profile_card_md(updated_user),
                gr.update(visible=False), gr.update(visible=True), gr.update(visible=False)
            )

        save_profile_button.click(
            do_save_profile,
            inputs=[session_user, edit_first_name, edit_last_name],
            outputs=[session_user, profile_status, profile_info, profile_edit_form, edit_profile_button, save_profile_button]
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

        def bot_respond(user, history, current_cid, cid_map):
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
                conv = conv_storage.create_conversation(user.nom_util, title)
                current_cid = conv.id
                conv_storage.add_message(current_cid, "user", user_msg)
            else:
                conv_storage.add_message(current_cid, "user", user_msg)

            try:
                sql_str, results = ask_database(user_msg)
                bot_md = _format_bot_response(sql_str, results)
                conv_storage.add_message(current_cid, "assistant", bot_md, sql_str)
            except Exception as e:
                bot_md = f"**Erreur :** {str(e)}"
                conv_storage.add_message(current_cid, "assistant", bot_md)

            history.append({"role": "assistant", "content": bot_md})

            conversations = conv_storage.list_conversations(user.nom_util)
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
            outputs=[chat_input, chatbot]
        ).then(
            bot_respond,
            inputs=[session_user, chatbot, current_conv_id, conv_id_map],
            outputs=[chatbot, current_conv_id, conv_radio, conv_id_map]
        )
        send_btn.click(
            add_user_msg,
            inputs=[chat_input, chatbot],
            outputs=[chat_input, chatbot]
        ).then(
            bot_respond,
            inputs=[session_user, chatbot, current_conv_id, conv_id_map],
            outputs=[chatbot, current_conv_id, conv_radio, conv_id_map]
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
    build_app().launch(server_name="0.0.0.0", server_port=7860, share=False, theme=theme, css=custom_css, js=force_light_mode_js)
