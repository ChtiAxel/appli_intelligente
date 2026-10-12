import unittest
from unittest.mock import patch

from NaturSQL.ui_gradio import _status_html, load_markdown
from shared.logging import get_logger


class UiAndLoggingTests(unittest.TestCase):
    def test_status_html(self):
        self.assertEqual(_status_html("", True), "")
        self.assertIn("status-msg ok", _status_html("OK", True))
        self.assertIn("status-msg error", _status_html("Erreur", False))

    def test_load_markdown_existing_and_missing_file(self):
        self.assertIn("Mentions", load_markdown("mentions-legales.md"))
        self.assertIn("introuvable", load_markdown("does-not-exist.md"))

    def test_application_logger_namespace(self):
        self.assertEqual(get_logger("tests").name, "natur_sql.tests")

    @patch("NaturSQL.ui_gradio.AuthService")
    @patch("NaturSQL.ui_gradio.ConversationStorage")
    def test_build_app_constructs_gradio_application(self, conversation_storage, auth_service):
        application = __import__("NaturSQL.ui_gradio", fromlist=["build_app"]).build_app()
        self.assertIsNotNone(application)
        conversation_storage.return_value.ensure_schema.assert_called_once_with()
        auth_service.assert_called_once_with()


    def test_profile_card_html(self):
        from NaturSQL.ui_gradio import _profile_card_html
        from NaturSQL.storage.users import User

        # None user
        empty_html = _profile_card_html(None)
        self.assertIn("profile-header", empty_html)
        self.assertIn("Erreur", empty_html)

        # Standard user
        user = User(prenom="Jean", nom="Dupont", mdp="hash")
        html = _profile_card_html(user)
        self.assertIn("profile-header", html)
        self.assertIn("profile-avatar", html)
        self.assertIn("JD", html)
        self.assertIn("profile-name", html)
        self.assertIn("Jean Dupont", html)
        self.assertIn("profile-id", html)
        self.assertIn("jean.dupont", html)
        self.assertIn("profile-role", html)
        self.assertIn("Enseignant", html)
        self.assertIn("badge-prof", html)
        self.assertIn("profile-badge", html)
        self.assertIn("profile-stats-grid", html)

        # Edge cases: stripped spaces, single name fallback
        user_spaces = User(prenom="  Alice  ", nom="  Smith  ", mdp="hash")
        html_spaces = _profile_card_html(user_spaces)
        self.assertIn("Alice Smith", html_spaces)
        self.assertIn("alice.smith", html_spaces)
        self.assertIn("AS", html_spaces)

        # Accents and non-ASCII characters
        user_accents = User(prenom="Éléonore", nom="François", mdp="hash")
        html_accents = _profile_card_html(user_accents)
        self.assertIn("Éléonore François", html_accents)
        self.assertIn("éléonore.françois", html_accents)
        self.assertIn("ÉF", html_accents)

        # Multi-word names with internal spaces
        user_multi = User(prenom="Jean  Paul", nom="De  La  Tour", mdp="hash")
        html_multi = _profile_card_html(user_multi)
        self.assertIn("Jean Paul De La Tour", html_multi)
        self.assertIn("jean-paul.de-la-tour", html_multi)
        self.assertNotIn("jean  paul", html_multi)

        # XSS / HTML escaping
        user_xss = User(prenom="<script>alert(1)</script>", nom="Smith", mdp="hash")
        html_xss = _profile_card_html(user_xss)
        self.assertNotIn("<script>", html_xss)
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", html_xss)

    def test_profile_card_html_roles(self):
        from NaturSQL.ui_gradio import _profile_card_html
        from NaturSQL.storage.users import User

        # PROF role
        user_prof = User(prenom="Marie", nom="Curie", mdp="hash", role="PROF")
        html_prof = _profile_card_html(user_prof)
        self.assertIn("Enseignant", html_prof)
        self.assertIn("badge-prof", html_prof)

        # SECRETAIRE role
        user_sec = User(prenom="Claire", nom="Dubois", mdp="hash", role="SECRETAIRE")
        html_sec = _profile_card_html(user_sec)
        self.assertIn("Secrétaire", html_sec)
        self.assertIn("badge-secretaire", html_sec)

        # ADMIN role
        user_admin = User(prenom="Alain", nom="Turing", mdp="hash", role="ADMIN")
        html_admin = _profile_card_html(user_admin)
        self.assertIn("Administrateur", html_admin)
        self.assertIn("badge-admin", html_admin)

        # Unknown / default role fallback
        user_unknown = User(prenom="Luc", nom="Inconnu", mdp="hash", role="OTHER")
        html_unknown = _profile_card_html(user_unknown)
        self.assertIn("Enseignant", html_unknown)
        self.assertIn("badge-prof", html_unknown)

    def test_profile_card_html_avatar(self):
        from NaturSQL.ui_gradio import _profile_card_html
        from NaturSQL.storage.users import User

        # Avatar is None -> fallback to initials in profile-avatar
        user_no_avatar = User(prenom="Paul", nom="Verlaine", mdp="hash", avatar=None)
        html_no_avatar = _profile_card_html(user_no_avatar)
        self.assertIn("profile-avatar", html_no_avatar)
        self.assertIn("PV", html_no_avatar)
        self.assertNotIn("profile-avatar-img", html_no_avatar)

        # Avatar present -> rendered as img.profile-avatar-img
        avatar_uri = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
        user_avatar = User(prenom="Arthur", nom="Rimbaud", mdp="hash", avatar=avatar_uri)
        html_avatar = _profile_card_html(user_avatar)
        self.assertIn("profile-avatar-img", html_avatar)
        self.assertIn(avatar_uri, html_avatar)

        # URL avatar
        user_url = User(prenom="Victor", nom="Hugo", mdp="hash", avatar="https://example.com/hugo.png")
        html_url = _profile_card_html(user_url)
        self.assertIn("https://example.com/hugo.png", html_url)
        self.assertIn("profile-avatar-img", html_url)

    def test_profile_card_html_activity_stats(self):
        from NaturSQL.ui_gradio import _profile_card_html
        from NaturSQL.storage.users import User
        from datetime import datetime

        user = User(
            prenom="Sophie",
            nom="Germain",
            mdp="hash",
            role="PROF",
            created_at=datetime(2026, 10, 12, 10, 0),
        )
        stats = {"conversations": 7, "questions": 42}
        html_stats = _profile_card_html(user, stats=stats)

        self.assertIn("profile-stats-grid", html_stats)
        self.assertIn("profile-stat-box", html_stats)
        self.assertIn("profile-stat-value", html_stats)
        self.assertIn("7", html_stats)
        self.assertIn("Conversations", html_stats)
        self.assertIn("42", html_stats)
        self.assertIn("Questions posées", html_stats)
        self.assertIn("12 oct. 2026", html_stats)
        self.assertIn("Membre depuis", html_stats)

    @patch("NaturSQL.ui_gradio.AuthService")
    @patch("NaturSQL.ui_gradio.ConversationStorage")
    def test_profile_layout_and_css(self, conversation_storage, auth_service):
        from NaturSQL.ui_gradio import custom_css, build_app
        import gradio as gr

        self.assertIn(".profile-card", custom_css)
        self.assertIn(".profile-header", custom_css)
        self.assertIn(".profile-role", custom_css)
        self.assertIn(".profile-id", custom_css)
        self.assertIn(".profile-accordion", custom_css)
        self.assertIn(".profile-btn-row", custom_css)

        # CSS additions for V2 / Milestone 3
        self.assertNotIn(".toast-wrap { display: none !important; }", custom_css)
        self.assertIn(".profile-badge", custom_css)
        self.assertIn(".badge-prof", custom_css)
        self.assertIn(".badge-secretaire", custom_css)
        self.assertIn(".badge-admin", custom_css)
        self.assertIn(".profile-stats-grid", custom_css)
        self.assertIn(".profile-stat-box", custom_css)
        self.assertIn(".profile-stat-value", custom_css)
        self.assertIn(".profile-stat-label", custom_css)
        self.assertIn(".profile-avatar-img", custom_css)
        self.assertIn(".danger-zone", custom_css)
        self.assertIn(".danger-zone-title", custom_css)
        self.assertIn(".danger-zone-desc", custom_css)
        self.assertIn(".delete-confirm-box", custom_css)

        app = build_app()
        # Find accordion block in app components
        accordions = [
            comp for comp in app.blocks.values()
            if isinstance(comp, gr.Accordion)
        ]
        self.assertTrue(len(accordions) >= 1)
        self.assertEqual(accordions[0].label, "Modifier mes informations")

        # Verify password change accordion and avatar accordion exist
        accordion_labels = [a.label for a in accordions]
        self.assertIn("Changer de mot de passe", accordion_labels)
        self.assertIn("Changer d'avatar", accordion_labels)

        # Verify textboxes inside profile edit are single-line (lines=1)
        edit_textboxes = [
            comp for comp in app.blocks.values()
            if isinstance(comp, gr.Textbox) and comp.label in ("Prénom *", "Nom *")
        ]
        self.assertTrue(len(edit_textboxes) >= 2)
        for tb in edit_textboxes:
            self.assertEqual(tb.lines, 1)

        # Verify password textboxes exist with password type
        pwd_textboxes = [
            comp for comp in app.blocks.values()
            if isinstance(comp, gr.Textbox) and comp.label == "Mot de passe actuel *"
        ]
        self.assertTrue(len(pwd_textboxes) >= 1)
        self.assertEqual(pwd_textboxes[0].type, "password")

        # Verify danger zone buttons exist
        stop_buttons = [
            comp for comp in app.blocks.values()
            if isinstance(comp, gr.Button) and comp.value == "Supprimer mon compte"
        ]
        self.assertTrue(len(stop_buttons) >= 1)


if __name__ == "__main__":
    unittest.main()