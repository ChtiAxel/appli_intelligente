"""Gradio application entry point.

Implements the authentication screens (Sign In / Sign Up / Profil)
from the Figma mockup (docs/mockup/AppliIntelligent.png), wired to the
real `appia` database through `service.auth.AuthService` (see
docs/monitoring/sprint-00.md, US-01 to US-09).

Login uses an auto-generated "nom.prenom" identifiant, not an email.
"""

from __future__ import annotations

CUSTOM_CSS = """
html, body {
    background: #ffffff !important;
}
:root {
    color-scheme: light !important;
}
.gradio-container, .dark .gradio-container {
    background: #ffffff !important;
    font-family: -apple-system, "Segoe UI", Roboto, sans-serif;
}
.dark, .dark body {
    --body-background-fill: #ffffff !important;
    --background-fill-primary: #ffffff !important;
    --background-fill-secondary: #ffffff !important;
    --block-background-fill: #ffffff !important;
}
#auth-shell {
    max-width: 420px;
    margin: 40px auto 0 auto;
    padding: 0 20px;
}
.brand-row {
    display: flex;
    align-items: center;
    gap: 8px;
    color: #111111;
    font-weight: 600;
    font-size: 14px;
    padding: 4px 4px 20px 4px;
}
.brand-row .brand-icon {
    width: 16px;
    height: 16px;
    border: 2px solid #111111;
    transform: rotate(45deg);
    display: inline-block;
    flex-shrink: 0;
}
.auth-card {
    background: #ffffff !important;
    border: 1px solid #e4e4e4 !important;
    border-radius: 12px !important;
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05) !important;
    padding: 28px 26px 22px 26px !important;
    max-width: 300px !important;
    margin: 0 auto !important;
}
.auth-title {
    text-align: center;
    font-weight: 700;
    font-size: 13px;
    letter-spacing: 0.02em;
    color: #111111;
    margin-bottom: 16px;
}
.auth-card label span, .auth-card label {
    font-weight: 600 !important;
    font-size: 12px !important;
    color: #222222 !important;
}
.auth-card input[type="text"],
.auth-card input[type="password"] {
    background: #ffffff !important;
    border: 1px solid #d9d9d9 !important;
    border-radius: 6px !important;
    font-size: 13px !important;
    color: #111111 !important;
}
.auth-card button.primary {
    background: #111111 !important;
    border: none !important;
    color: #ffffff !important;
    border-radius: 8px !important;
    font-weight: 600 !important;
    font-size: 13px !important;
}
.auth-card button.primary:hover { background: #2a2a2a !important; }
.auth-links {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-top: 10px !important;
}
.auth-links button {
    background: none !important;
    border: none !important;
    box-shadow: none !important;
    color: #555555 !important;
    font-size: 12px !important;
    padding: 0 !important;
    min-width: 0 !important;
}
.auth-links button.link-underline { text-decoration: underline !important; color: #111111 !important; }
#legal-footer {
    max-width: 420px;
    margin: 20px auto 40px auto;
    padding: 0 20px;
    color: #333333;
}
#legal-footer .legal-title-row {
    display: flex;
    align-items: center;
    gap: 8px;
    font-weight: 700;
    font-size: 13px;
    color: #111111;
    margin-bottom: 8px;
}
#legal-footer .legal-title-row .brand-icon {
    width: 14px;
    height: 14px;
    border: 2px solid #111111;
    transform: rotate(45deg);
    display: inline-block;
}
#legal-footer a {
    display: block;
    color: #666666 !important;
    text-decoration: none;
    font-size: 12px;
    margin-top: 5px;
}
.status-msg { min-height: 20px; font-size: 13px; margin-top: 8px; }
.status-msg.error { color: #d64545 !important; }
.status-msg.ok { color: #2e8b57 !important; font-weight: 600; }
#profile-card-row {
    background: #ffffff !important;
    border: 1px solid #e4e4e4 !important;
    border-radius: 12px !important;
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05) !important;
    padding: 20px 22px !important;
    align-items: center !important;
    gap: 16px;
}
#profile-info { display: flex; align-items: center; gap: 14px; flex-grow: 1; }
#profile-avatar {
    width: 52px;
    height: 52px;
    border-radius: 50%;
    background: #dddddd;
    flex-shrink: 0;
}
.profile-name { font-weight: 700; font-size: 14px; color: #111111; }
.profile-username { font-size: 12px; color: #666666; margin-top: 2px; }
#disconnect-btn {
    background: #e03e3e !important;
    border: none !important;
    color: #ffffff !important;
    border-radius: 8px !important;
    font-weight: 600 !important;
    font-size: 12px !important;
    flex-shrink: 0;
}
#disconnect-btn:hover { background: #c62f2f !important; }
.edit-link button {
    background: none !important;
    border: none !important;
    box-shadow: none !important;
    color: #555555 !important;
    text-decoration: underline;
    font-size: 12px !important;
}
"""

BRAND_HTML = (
    '<div class="brand-row"><span class="brand-icon"></span><span>NaturSQL</span></div>'
)

LEGAL_HTML = """
<div id="legal-footer">
  <div class="legal-title-row"><span class="brand-icon"></span><span>Legal</span></div>
  <a href="#">Legal Notice</a>
  <a href="#">Privacy Policy</a>
  <a href="#">Cookie management</a>
  <a href="#">General Terms of Use</a>
</div>
"""


def _status_html(message: str, ok: bool) -> str:
    if not message:
        return ""
    css_class = "status-msg ok" if ok else "status-msg error"
    return f'<div class="{css_class}">{message}</div>'


def build_app():
    """Build the Sign In / Sign Up / Profil Gradio app."""
    import gradio as gr

    from NaturSQL.service.auth import AuthService

    auth_service = AuthService()

    with gr.Blocks(css=CUSTOM_CSS, title="NaturSQL", theme=gr.themes.Default()) as demo:
        session_user = gr.State(None)  # dataclasses.User | None

        # ---------------------------------------------------------- Sign In
        with gr.Column(visible=True, elem_id="auth-shell") as signin_page:
            gr.HTML(BRAND_HTML)
            with gr.Column(elem_classes=["auth-card"]):
                gr.HTML('<div class="auth-title">NaturSQL</div>')
                gr.HTML(
                    '<div style="font-size:11px;color:#888;margin:-6px 0 10px 0;">'
                    "Tous les champs sont obligatoires.</div>"
                )
                signin_username = gr.Textbox(
                    label="Identifiant *", placeholder="nom.prenom"
                )
                signin_password = gr.Textbox(
                    label="Mot de passe *", type="password", placeholder="Mot de passe"
                )
                signin_status = gr.HTML()
                signin_button = gr.Button("Sign In", variant="primary")
                with gr.Row(elem_classes=["auth-links"]):
                    forgot_from_signin = gr.Button(
                        "Forgot password?", size="sm", variant="secondary"
                    )
                    go_to_signup = gr.Button(
                        "Create an account",
                        size="sm",
                        variant="secondary",
                        elem_classes=["link-underline"],
                    )
            gr.HTML(LEGAL_HTML)

        # ---------------------------------------------------------- Sign Up
        with gr.Column(visible=False, elem_id="auth-shell") as signup_page:
            gr.HTML(BRAND_HTML)
            with gr.Column(elem_classes=["auth-card"]):
                gr.HTML('<div class="auth-title">NaturSQL</div>')
                gr.HTML(
                    '<div style="font-size:11px;color:#888;margin:-6px 0 10px 0;">'
                    "Tous les champs sont obligatoires. Votre identifiant de connexion "
                    "(nom.prenom) sera généré automatiquement.</div>"
                )
                signup_first_name = gr.Textbox(label="First Name *", placeholder="Prénom")
                signup_last_name = gr.Textbox(label="Last Name *", placeholder="Nom")
                signup_password = gr.Textbox(
                    label="Password *",
                    type="password",
                    placeholder="Mot de passe",
                    info="8 caractères min., 1 majuscule, 1 chiffre, 1 caractère spécial.",
                )
                signup_confirm = gr.Textbox(
                    label="Confirm password *",
                    type="password",
                    placeholder="Confirmer le mot de passe",
                )
                signup_status = gr.HTML()
                signup_button = gr.Button("Sign Up", variant="primary")
                with gr.Row(elem_classes=["auth-links"]):
                    forgot_from_signup = gr.Button(
                        "Forgot password?", size="sm", variant="secondary"
                    )
                    go_to_signin = gr.Button(
                        "Sign In",
                        size="sm",
                        variant="secondary",
                        elem_classes=["link-underline"],
                    )
            gr.HTML(LEGAL_HTML)

        # ---------------------------------------------------------- Profil
        with gr.Column(visible=False, elem_id="auth-shell") as profile_page:
            gr.HTML(BRAND_HTML)
            with gr.Row(elem_id="profile-card-row"):
                profile_card = gr.HTML()
                disconnect_button = gr.Button(
                    "Disconnect", variant="stop", elem_id="disconnect-btn", scale=0
                )
            with gr.Row(elem_classes=["edit-link"]):
                edit_profile_button = gr.Button("Edit profile", size="sm")
                save_profile_button = gr.Button(
                    "Save", visible=False, variant="primary", size="sm"
                )
            with gr.Column(visible=False) as profile_edit_form:
                edit_first_name = gr.Textbox(label="First Name *", placeholder="Prénom")
                edit_last_name = gr.Textbox(label="Last Name *", placeholder="Nom")
            profile_status = gr.HTML()
            gr.HTML(LEGAL_HTML)

        # ------------------------------------------------------- callbacks

        def _profile_card_html(user) -> str:
            return (
                '<div id="profile-info">'
                '<div id="profile-avatar"></div>'
                "<div>"
                f'<div class="profile-name">{user.full_name}</div>'
                f'<div class="profile-username">Identifiant : {user.nom_util}</div>'
                "</div></div>"
            )

        def do_sign_in(username, password):
            result = auth_service.login(username, password)
            if not result.ok:
                return (
                    gr.update(),  # session_user
                    gr.update(visible=True),  # signin_page
                    gr.update(visible=False),  # signup_page
                    gr.update(visible=False),  # profile_page
                    _status_html(result.message, ok=False),
                    "",
                    "",
                )
            user = result.user
            gr.Info(result.message)
            return (
                user,
                gr.update(visible=False),
                gr.update(visible=False),
                gr.update(visible=True),
                "",
                _profile_card_html(user),
                _status_html(result.message, ok=True),
            )

        signin_button.click(
            do_sign_in,
            inputs=[signin_username, signin_password],
            outputs=[
                session_user,
                signin_page,
                signup_page,
                profile_page,
                signin_status,
                profile_card,
                profile_status,
            ],
        )

        def do_sign_up(first_name, last_name, password, confirm):
            result = auth_service.register(password, confirm, first_name, last_name)
            if not result.ok:
                return gr.update(visible=True), gr.update(visible=False), _status_html(
                    result.message, ok=False
                )
            # US-03: message de confirmation (avec l'identifiant généré) puis
            # redirection vers /login.
            gr.Info(result.message)
            return (
                gr.update(visible=False),
                gr.update(visible=True),
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
            outputs=[signup_page, signin_page, signin_status],
        )

        def show_signup():
            return gr.update(visible=False), gr.update(visible=True)

        def show_signin():
            return gr.update(visible=False), gr.update(visible=True)

        go_to_signup.click(show_signup, outputs=[signin_page, signup_page])
        go_to_signin.click(show_signin, outputs=[signup_page, signin_page])
        forgot_from_signin.click(
            lambda: _status_html(
                "Contactez un administrateur pour réinitialiser votre mot de passe.",
                ok=True,
            ),
            outputs=signin_status,
        )
        forgot_from_signup.click(
            lambda: _status_html(
                "Contactez un administrateur pour réinitialiser votre mot de passe.",
                ok=True,
            ),
            outputs=signup_status,
        )

        def do_disconnect():
            # US-09 : déconnexion -> retour à la page de connexion (US-10)
            return (
                None,
                gr.update(visible=True),
                gr.update(visible=False),
                "",
                "",
                gr.update(visible=False),
                gr.update(visible=True),
                gr.update(visible=False),
                "",
            )

        disconnect_button.click(
            do_disconnect,
            outputs=[
                session_user,
                signin_page,
                profile_page,
                signin_username,
                signin_password,
                profile_edit_form,
                edit_profile_button,
                save_profile_button,
                profile_status,
            ],
        )

        def start_edit(user):
            if user is None:
                return gr.update(), gr.update(), gr.update(visible=False), gr.update(visible=True)
            return (
                user.prenom_ens,
                user.nom_ens,
                gr.update(visible=True),
                gr.update(visible=False),
            )

        edit_profile_button.click(
            start_edit,
            inputs=session_user,
            outputs=[
                edit_first_name,
                edit_last_name,
                profile_edit_form,
                edit_profile_button,
            ],
        ).then(lambda: gr.update(visible=True), outputs=save_profile_button)

        def do_save_profile(user, first_name, last_name):
            if user is None:
                return (
                    user,
                    _status_html("Session expirée, merci de vous reconnecter.", ok=False),
                    "",
                    gr.update(visible=False),
                    gr.update(visible=True),
                    gr.update(visible=False),
                )
            result = auth_service.update_profile(user, first_name, last_name)
            if not result.ok:
                return (
                    user,
                    _status_html(result.message, ok=False),
                    _profile_card_html(user),
                    gr.update(visible=True),
                    gr.update(visible=False),
                    gr.update(visible=True),
                )
            updated_user = result.user
            gr.Info(result.message)
            return (
                updated_user,
                _status_html(result.message, ok=True),
                _profile_card_html(updated_user),
                gr.update(visible=False),
                gr.update(visible=True),
                gr.update(visible=False),
            )

        save_profile_button.click(
            do_save_profile,
            inputs=[session_user, edit_first_name, edit_last_name],
            outputs=[
                session_user,
                profile_status,
                profile_card,
                profile_edit_form,
                edit_profile_button,
                save_profile_button,
            ],
        )

    return demo


if __name__ == "__main__":
    build_app().launch()
