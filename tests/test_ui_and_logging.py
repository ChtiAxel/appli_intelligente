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

    def test_v2_home_helpers(self):
        from NaturSQL.ui_gradio import (
            _welcome_banner_html,
            _status_badges_html,
            create_results_csv,
            get_conv_period,
            _format_bot_response,
        )
        from NaturSQL.storage.users import User
        from datetime import datetime, timedelta

        # Welcome banner test (must contain greeting and no emojis)
        user = User(prenom="Alice", nom="Martin", mdp="hash")
        welcome = _welcome_banner_html(user)
        self.assertIn("Bonjour Alice, que souhaitez-vous analyser", welcome)
        self.assertIn("Conseils de formulation", welcome)
        # Ensure no emojis in welcome
        self.assertNotIn("🟢", welcome)
        self.assertNotIn("💡", welcome)

        # Status badges test (must contain MariaDB and Ollama without emojis)
        with patch("NaturSQL.ui_gradio.get_system_status", return_value={"mariadb": True, "ollama": False}):
            badges = _status_badges_html()
            self.assertIn("Base de donnees (MariaDB) : En ligne", badges)
            self.assertIn("Serveur IA (Ollama) : Indisponible", badges)
            self.assertIn("status-dot-online", badges)
            self.assertIn("status-dot-offline", badges)
            self.assertNotIn("🟢", badges)

        # CSV export test
        results = [{"nom_ens": "Dupont", "total_h": 42}]
        csv_path = create_results_csv(results)
        self.assertIsNotNone(csv_path)
        with open(csv_path, "r", encoding="utf-8-sig") as f:
            content = f.read()
        self.assertIn("nom_ens;total_h", content)
        self.assertIn("Dupont;42", content)
        self.assertIsNone(create_results_csv([]))

        # Period classification test
        now = datetime.now()
        self.assertEqual(get_conv_period(now), "Aujourd'hui")
        self.assertEqual(get_conv_period(now - timedelta(days=2)), "7 derniers jours")
        self.assertEqual(get_conv_period(now - timedelta(days=15)), "Plus ancien")

        # Simplified vs Expert mode response formatting
        sql = "SELECT * FROM test"
        resp_expert = _format_bot_response(sql, results, simplified=False)
        self.assertIn("```sql", resp_expert)
        self.assertIn("Dupont", resp_expert)

        resp_simplified = _format_bot_response(sql, results, simplified=True)
        self.assertNotIn("```sql", resp_simplified)
        self.assertIn("Dupont", resp_simplified)


if __name__ == "__main__":
    unittest.main()