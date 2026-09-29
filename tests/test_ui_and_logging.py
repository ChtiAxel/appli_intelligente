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


if __name__ == "__main__":
    unittest.main()