"""Gradio application entry point."""

from __future__ import annotations
import os
import base64
import gradio as gr
from .service.auth import AuthService

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

    with gr.Blocks(theme=theme, css=custom_css, js=force_light_mode_js, title="NaturSQL Profile") as demo:
        session_user = gr.State(None)

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
                    <a href="#" style="color: #1f2937; text-decoration: none;" onclick="document.querySelector('#btn-show-mentions button').click(); return false;">Mentions légales</a><br>
                    <a href="#" style="color: #1f2937; text-decoration: none;" onclick="document.querySelector('#btn-show-privacy button').click(); return false;">Politique de confidentialité</a><br>
                    <a href="#" style="color: #1f2937; text-decoration: none;" onclick="document.querySelector('#btn-show-cgu button').click(); return false;">Conditions générales d'utilisation</a>
                </div>
            </div>
            """)
            
            # Boutons invisibles pour déclencher l'affichage des pages légales depuis le footer HTML
            btn_show_mentions = gr.Button(elem_id="btn-show-mentions", elem_classes=["hidden-btn"])
            btn_show_privacy = gr.Button(elem_id="btn-show-privacy", elem_classes=["hidden-btn"])
            btn_show_cgu = gr.Button(elem_id="btn-show-cgu", elem_classes=["hidden-btn"])

        # --- Callbacks ---

        def go_to_page(page_name, session):
            s_in = s_up = prof = leg_m = leg_p = leg_c = gr.update(visible=False)
            if page_name == "mentions": leg_m = gr.update(visible=True)
            elif page_name == "privacy": leg_p = gr.update(visible=True)
            elif page_name == "cgu": leg_c = gr.update(visible=True)
            elif page_name == "home":
                if session is None: s_in = gr.update(visible=True)
                else: prof = gr.update(visible=True)
            return s_in, s_up, prof, leg_m, leg_p, leg_c

        page_outputs = [signin_page, signup_page, profile_page, legal_mentions_page, legal_privacy_page, legal_cgu_page]
        
        btn_show_mentions.click(lambda s: go_to_page("mentions", s), inputs=[session_user], outputs=page_outputs)
        btn_show_privacy.click(lambda s: go_to_page("privacy", s), inputs=[session_user], outputs=page_outputs)
        btn_show_cgu.click(lambda s: go_to_page("cgu", s), inputs=[session_user], outputs=page_outputs)
        
        btn_back_1.click(lambda s: go_to_page("home", s), inputs=[session_user], outputs=page_outputs)
        btn_back_2.click(lambda s: go_to_page("home", s), inputs=[session_user], outputs=page_outputs)
        btn_back_3.click(lambda s: go_to_page("home", s), inputs=[session_user], outputs=page_outputs)

        def _profile_card_md(user) -> str:
            if not user:
                return "Erreur de chargement"
            return f"**{user.full_name}**\n\nIdentifiant : {user.nom_util}"

        def do_sign_in(username, password):
            result = auth_service.login(username, password)
            if not result.ok:
                return (
                    gr.update(), gr.update(visible=True), gr.update(visible=False), gr.update(visible=False),
                    _status_html(result.message, ok=False), "", ""
                )
            user = result.user
            return (
                user, gr.update(visible=False), gr.update(visible=False), gr.update(visible=True),
                "", _profile_card_md(user), _status_html(result.message, ok=True)
            )

        signin_button.click(
            do_sign_in,
            inputs=[signin_username, signin_password],
            outputs=[session_user, signin_page, signup_page, profile_page, signin_status, profile_info, profile_status]
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
                None, gr.update(visible=True), gr.update(visible=False), "", "",
                gr.update(visible=False), gr.update(visible=True), gr.update(visible=False), ""
            )

        disconnect_button.click(
            do_disconnect,
            outputs=[
                session_user, signin_page, profile_page, signin_username, signin_password,
                profile_edit_form, edit_profile_button, save_profile_button, profile_status
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

    return demo

if __name__ == "__main__":
    build_app().launch(server_name="0.0.0.0", server_port=7860, share=False)
