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
        self.assertIn("Utilisateur Standard", html)

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

        app = build_app()
        # Find accordion block in app components
        accordions = [
            comp for comp in app.blocks.values()
            if isinstance(comp, gr.Accordion)
        ]
        self.assertTrue(len(accordions) >= 1)
        self.assertEqual(accordions[0].label, "Modifier mes informations")

        # Verify textboxes inside profile edit are single-line (lines=1)
        edit_textboxes = [
            comp for comp in app.blocks.values()
            if isinstance(comp, gr.Textbox) and comp.label in ("Prénom *", "Nom *")
        ]
        self.assertTrue(len(edit_textboxes) >= 2)
        for tb in edit_textboxes:
            self.assertEqual(tb.lines, 1)


if __name__ == "__main__":
    unittest.main()