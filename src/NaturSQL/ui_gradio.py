"""Gradio application entry point.

Implements the authentication screens (Sign In / Sign Up / Profil)
from the Figma mockup (docs/mockup/AppliIntelligent.png), wired to the
real `appia` database through `service.auth.AuthService` (see
docs/monitoring/sprint-00.md, US-01 to US-09).
"""

from __future__ import annotations

CUSTOM_CSS = """
.gradio-container {
    background: #101010 !important;
    font-family: -apple-system, "Segoe UI", Roboto, sans-serif;
}
#auth-shell {
    max-width: 380px;
    margin: 48px auto 0 auto;
}
.brand-row {
    display: flex;
    align-items: center;
    gap: 8px;
    color: #ffffff;
    font-weight: 600;
    font-size: 15px;
    padding: 4px 4px 16px 4px;
}
.brand-row .brand-icon {
    width: 20px;
    height: 20px;
    border-radius: 5px;
    background: #ffffff;
    display: inline-block;
}
.auth-card {
    background: #ffffff !important;
    border-radius: 14px !important;
    padding: 28px 26px 20px 26px !important;
}
.auth-title {
    text-align: center;
    font-weight: 700;
    font-size: 13px;
    letter-spacing: 0.02em;
    color: #111111;
    margin-bottom: 14px;
}
.auth-links {
    display: flex;
    justify-content: space-between;
    font-size: 12px;
    margin-top: 8px;
}
.auth-links a { color: #555555 !important; text-decoration: none; }
#legal-footer {
    max-width: 380px;
    margin: 18px auto 40px auto;
    color: #d5d5d5;
    font-size: 12px;
}
#legal-footer .legal-title {
    font-weight: 700;
    color: #ffffff;
    margin-bottom: 6px;
}
#legal-footer a {
    display: block;
    color: #bdbdbd !important;
    text-decoration: none;
    margin-top: 4px;
}
.status-msg { min-height: 20px; font-size: 13px; }
.status-msg.error { color: #d64545 !important; }
.status-msg.ok { color: #2e8b57 !important; }
#profile-card {
    background: #ffffff !important;
    border-radius: 14px !important;
    padding: 24px !important;
    display: flex;
    align-items: center;
    gap: 16px;
}
#profile-avatar {
    width: 56px;
    height: 56px;
    border-radius: 50%;
    background: #dddddd;
    flex-shrink: 0;
}
.profile-name { font-weight: 700; font-size: 15px; color: #111111; }
.profile-email { font-size: 12px; color: #666666; }
"""

BRAND_HTML = (
    '<div class="brand-row"><span class="brand-icon"></span>NaturSQL</div>'
)

LEGAL_HTML = """
<div id="legal-footer">
  <div class="legal-title">Legal</div>
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

    with gr.Blocks(css=CUSTOM_CSS, title="NaturSQL") as demo:
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
                signin_email = gr.Textbox(label="Email *", placeholder="Value")
                signin_password = gr.Textbox(
                    label="Password *", type="password", placeholder="Value"
                )
                signin_status = gr.HTML()
                signin_button = gr.Button("Sign In", variant="primary")
                with gr.Row(elem_classes=["auth-links"]):
                    forgot_from_signin = gr.Button(
                        "Forgot password?", size="sm", variant="secondary"
                    )
                    go_to_signup = gr.Button(
                        "Create an account", size="sm", variant="secondary"
                    )
            gr.HTML(LEGAL_HTML)

        # ---------------------------------------------------------- Sign Up
        with gr.Column(visible=False, elem_id="auth-shell") as signup_page:
            gr.HTML(BRAND_HTML)
            with gr.Column(elem_classes=["auth-card"]):
                gr.HTML('<div class="auth-title">NaturSQL</div>')
                gr.HTML(
                    '<div style="font-size:11px;color:#888;margin:-6px 0 10px 0;">'
                    "Tous les champs sont obligatoires.</div>"
                )
                signup_first_name = gr.Textbox(label="First Name *", placeholder="Value")
                signup_last_name = gr.Textbox(label="Last Name *", placeholder="Value")
                signup_email = gr.Textbox(label="Email *", placeholder="Value")
                signup_password = gr.Textbox(
                    label="Password *",
                    type="password",
                    placeholder="Value",
                    info="8 caractères min., 1 majuscule, 1 chiffre, 1 caractère spécial.",
                )
                signup_confirm = gr.Textbox(
                    label="Confirm password *", type="password", placeholder="Value"
                )
                signup_rgpd = gr.Checkbox(label="Agree with RGPD *", value=False)
                signup_status = gr.HTML()
                signup_button = gr.Button("Sign Up", variant="primary")
                with gr.Row(elem_classes=["auth-links"]):
                    forgot_from_signup = gr.Button(
                        "Forgot password?", size="sm", variant="secondary"
                    )
                    go_to_signin = gr.Button(
                        "Sign In", size="sm", variant="secondary"
                    )
            gr.HTML(LEGAL_HTML)

        # ---------------------------------------------------------- Profil
        with gr.Column(visible=False, elem_id="auth-shell") as profile_page:
            gr.HTML(BRAND_HTML)
            profile_card = gr.HTML()
            with gr.Column(visible=False) as profile_edit_form:
                edit_first_name = gr.Textbox(label="First Name *")
                edit_last_name = gr.Textbox(label="Last Name *")
                edit_email = gr.Textbox(label="Email *")
            profile_status = gr.HTML()
            with gr.Row():
                edit_profile_button = gr.Button("Edit profile")
                save_profile_button = gr.Button("Save", visible=False, variant="primary")
            disconnect_button = gr.Button("Disconnect", variant="stop")
            gr.HTML(LEGAL_HTML)

        # ------------------------------------------------------- callbacks

        def _profile_card_html(user) -> str:
            email = user.mail_ens or user.nom_util
            return (
                '<div id="profile-card">'
                '<div id="profile-avatar"></div>'
                "<div>"
                f'<div class="profile-name">{user.full_name}</div>'
                f'<div class="profile-email">Email : {email}</div>'
                "</div></div>"
            )

        def do_sign_in(email, password):
            result = auth_service.login(email, password)
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
            inputs=[signin_email, signin_password],
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

        def do_sign_up(first_name, last_name, email, password, confirm, rgpd):
            result = auth_service.register(
                email, password, confirm, first_name, last_name, rgpd
            )
            if not result.ok:
                return gr.update(visible=True), gr.update(visible=False), _status_html(
                    result.message, ok=False
                )
            # US-03: message de confirmation puis redirection vers /login
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
                signup_email,
                signup_password,
                signup_confirm,
                signup_rgpd,
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
                signin_email,
                signin_password,
                profile_edit_form,
                edit_profile_button,
                save_profile_button,
                profile_status,
            ],
        )

        def start_edit(user):
            if user is None:
                return gr.update(), gr.update(), gr.update(), gr.update(visible=False), gr.update(visible=True)
            return (
                user.prenom_ens,
                user.nom_ens,
                user.mail_ens or user.nom_util,
                gr.update(visible=True),
                gr.update(visible=False),
            )

        edit_profile_button.click(
            start_edit,
            inputs=session_user,
            outputs=[
                edit_first_name,
                edit_last_name,
                edit_email,
                profile_edit_form,
                edit_profile_button,
            ],
        ).then(lambda: gr.update(visible=True), outputs=save_profile_button)

        def do_save_profile(user, first_name, last_name, email):
            if user is None:
                return (
                    user,
                    _status_html("Session expirée, merci de vous reconnecter.", ok=False),
                    "",
                    gr.update(visible=False),
                    gr.update(visible=True),
                    gr.update(visible=False),
                )
            result = auth_service.update_profile(user, first_name, last_name, email)
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
            inputs=[session_user, edit_first_name, edit_last_name, edit_email],
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
