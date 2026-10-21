import unittest
from unittest.mock import patch

from NaturSQL.ui_gradio import _status_html, load_markdown
from shared.logging import get_logger


class UiAndLoggingTests(unittest.TestCase):
    def setUp(self):
        status = patch("NaturSQL.ui_gradio.get_system_status", return_value={"mariadb": True, "ollama": True})
        status.start()
        self.addCleanup(status.stop)

    def test_status_html(self):
        self.assertEqual(_status_html("", True), "")
        self.assertIn("status-msg ok", _status_html("OK", True))
        self.assertIn("status-msg error", _status_html("Erreur", False))

    def test_load_markdown_existing_and_missing_file(self):
        self.assertIn("Mentions", load_markdown("mentions-legales.md"))
        self.assertIn("Registre", load_markdown("registre-traitements.md"))
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
        self.assertNotIn("profile-avatar", html)
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

        # Accents and non-ASCII characters
        user_accents = User(prenom="Éléonore", nom="François", mdp="hash")
        html_accents = _profile_card_html(user_accents)
        self.assertIn("Éléonore François", html_accents)
        self.assertIn("éléonore.françois", html_accents)

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

        # RGPD Consent badge
        from datetime import datetime
        user_rgpd = User(
            prenom="Noa",
            nom="Gaillard",
            mdp="hash",
            rgpd_accepted_at=datetime(2026, 10, 13, 12, 0),
        )
        html_rgpd = _profile_card_html(user_rgpd)
        self.assertIn("profile-rgpd-badge", html_rgpd)
        self.assertIn("Consentement RGPD", html_rgpd)
        self.assertIn("13/10/2026", html_rgpd)

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

    def test_profile_and_header_do_not_render_avatars(self):
        from NaturSQL.ui_gradio import _profile_card_html, _header_user_html
        from NaturSQL.storage.users import User

        for avatar in (None, "https://example.com/avatar.png", '" onerror="alert(1)'):
            user = User(prenom="Arthur", nom="Rimbaud", mdp="hash", avatar=avatar)
            for rendered in (_profile_card_html(user, stats={}), _header_user_html(user)):
                self.assertIn("Arthur Rimbaud", rendered)
                self.assertNotIn("<img", rendered)
                self.assertNotIn("profile-avatar", rendered)
                if avatar:
                    self.assertNotIn(avatar, rendered)

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
        self.assertNotIn(".profile-avatar", custom_css)
        self.assertIn(".danger-zone", custom_css)
        self.assertIn(".danger-zone-title", custom_css)
        self.assertIn(".danger-zone-desc", custom_css)
        self.assertIn(".delete-confirm-box", custom_css)
        self.assertIn(".profile-rgpd-badge", custom_css)

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
        self.assertNotIn("Changer d'avatar", accordion_labels)
        self.assertNotIn("Gestion de mes données personnelles (RGPD - Art. 20)", accordion_labels)

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

        # Personal data export is no longer shown in the profile
        download_buttons = [
            comp for comp in app.blocks.values()
            if isinstance(comp, gr.DownloadButton)
        ]
        self.assertEqual(len(download_buttons), 1)
        self.assertEqual(download_buttons[0].label, "Telecharger en CSV")

        # Verify RGPD Checkbox exists
        rgpd_checkboxes = [
            comp for comp in app.blocks.values()
            if isinstance(comp, gr.Checkbox) and getattr(comp, "elem_id", None) == "signup-rgpd-cb"
        ]
        self.assertTrue(len(rgpd_checkboxes) >= 1)

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

        user = User(prenom="Alice", nom="Martin", mdp="hash")
        welcome = _welcome_banner_html(user)
        self.assertIn("Bonjour Alice, que souhaitez-vous analyser", welcome)
        self.assertIn("Conseils de formulation", welcome)
        self.assertNotIn("🟢", welcome)
        self.assertNotIn("💡", welcome)

        with patch("NaturSQL.ui_gradio.get_system_status", return_value={"mariadb": True, "ollama": False}):
            badges = _status_badges_html()
            self.assertIn("Base de donnees (MariaDB) : En ligne", badges)
            self.assertIn("Serveur IA (Ollama) : Indisponible", badges)
            self.assertIn("status-dot-online", badges)
            self.assertIn("status-dot-offline", badges)
            self.assertNotIn("🟢", badges)

        results = [{"nom_ens": "Dupont", "total_h": 42}]
        csv_path = create_results_csv(results)
        self.assertIsNotNone(csv_path)
        with open(csv_path, "r", encoding="utf-8-sig") as f:
            content = f.read()
        self.assertIn("nom_ens;total_h", content)
        self.assertIn("Dupont;42", content)
        self.assertIsNone(create_results_csv([]))

        now = datetime.now()
        self.assertEqual(get_conv_period(now), "Aujourd'hui")
        self.assertEqual(get_conv_period(now - timedelta(days=2)), "7 derniers jours")
        self.assertEqual(get_conv_period(now - timedelta(days=15)), "Plus ancien")

        sql = "SELECT * FROM test"
        resp_expert = _format_bot_response(sql, results, simplified=False)
        self.assertIn("```sql", resp_expert)
        self.assertIn("Dupont", resp_expert)

        resp_simplified = _format_bot_response(sql, results, simplified=True, summary="Dupont totalise 42 heures.")
        self.assertIn("Dupont totalise 42 heures.", resp_simplified)
        self.assertNotIn("```sql", resp_simplified)
        self.assertIn("Dupont", resp_simplified)


    @patch("NaturSQL.ui_gradio.AuthService")
    @patch("NaturSQL.ui_gradio.ConversationStorage")
    def test_footer_links_are_not_duplicated(self, storage, auth):
        import gradio as gr
        from NaturSQL.ui_gradio import build_app
        app = build_app()
        footers = [component.value for component in app.blocks.values()
                   if isinstance(component, gr.HTML) and isinstance(component.value, str)
                   and "<strong>Aide</strong>" in component.value]
        self.assertEqual(len(footers), 1)
        footer = footers[0]
        self.assertEqual(footer.count("<strong>Aide</strong>"), 1)
        self.assertEqual(footer.count("<strong>Légal</strong>"), 1)
        for target in ("doc", "mentions", "privacy", "cgu", "registry"):
            self.assertEqual(footer.count("getElementById('btn-show-" + target + "')"), 1)
        callbacks = [event.fn.__name__ for event in app.fns.values() if event.fn]
        self.assertGreaterEqual(callbacks.count("_status_badges_html"), 2)

    def test_status_distinguishes_connection_and_query_permissions(self):
        from NaturSQL.ui_gradio import _status_badges_html
        with patch("NaturSQL.ui_gradio.get_system_status", return_value={"mariadb": True, "mariadb_queries": False, "ollama": True}):
            status = _status_badges_html()
        self.assertIn("MariaDB) : En ligne", status)
        self.assertIn("accès aux requêtes à configurer", status)
        self.assertNotIn("Hors ligne", status)


if __name__ == "__main__":
    unittest.main()