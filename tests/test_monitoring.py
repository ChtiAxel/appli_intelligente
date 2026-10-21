import unittest
from unittest.mock import patch, MagicMock
from NaturSQL.service.monitoring import check_mariadb, check_ollama, get_system_status


class MonitoringTests(unittest.TestCase):
    @patch("NaturSQL.service.monitoring.get_connection")
    def test_check_mariadb_success(self, mock_conn):
        mock_ctx = MagicMock()
        mock_cursor = MagicMock()
        mock_ctx.__enter__.return_value.cursor.return_value.__enter__.return_value = mock_cursor
        mock_conn.return_value = mock_ctx

        self.assertTrue(check_mariadb())
        mock_cursor.execute.assert_called_once_with("SELECT 1")

    @patch("NaturSQL.service.monitoring.get_connection", side_effect=Exception("DB Down"))
    def test_check_mariadb_failure(self, mock_conn):
        self.assertFalse(check_mariadb())

    @patch("urllib.request.urlopen")
    def test_check_ollama_success(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_urlopen.return_value.__enter__.return_value = mock_resp

        self.assertTrue(check_ollama())

    @patch("urllib.request.urlopen", side_effect=Exception("Network error"))
    def test_check_ollama_failure(self, mock_urlopen):
        self.assertFalse(check_ollama())

    @patch("NaturSQL.service.monitoring.check_query_access", return_value=True)
    @patch("NaturSQL.service.monitoring.check_mariadb", return_value=True)
    @patch("NaturSQL.service.monitoring.check_ollama", return_value=False)
    def test_get_system_status(self, mock_ollama, mock_db, mock_queries):
        status = get_system_status()
        self.assertEqual(status, {"mariadb": True, "mariadb_queries": True, "ollama": False})


    @patch("NaturSQL.service.monitoring.check_query_access", return_value=False)
    @patch("NaturSQL.service.monitoring.check_mariadb", return_value=True)
    @patch("NaturSQL.service.monitoring.check_ollama", return_value=True)
    def test_online_database_with_query_credentials_failure(self, ollama, database, queries):
        self.assertEqual(get_system_status(), {"mariadb": True, "mariadb_queries": False, "ollama": True})

    @patch("NaturSQL.service.monitoring.check_query_access")
    @patch("NaturSQL.service.monitoring.check_mariadb", return_value=False)
    @patch("NaturSQL.service.monitoring.check_ollama", return_value=True)
    def test_offline_database_does_not_attempt_query_access(self, ollama, database, queries):
        self.assertEqual(get_system_status(), {"mariadb": False, "mariadb_queries": False, "ollama": True})
        queries.assert_not_called()

    @patch("NaturSQL.service.monitoring.get_readonly_connection")
    def test_query_check_exercises_pedagogical_view(self, connection):
        from NaturSQL.service.monitoring import check_query_access
        self.assertTrue(check_query_access())
        connection.return_value.__enter__.return_value.cursor.return_value.__enter__.return_value.execute.assert_called_once_with("SELECT 1 FROM details LIMIT 0")

    @patch("NaturSQL.service.monitoring.get_readonly_connection", side_effect=Exception("Access denied"))
    def test_query_access_failure_is_reported(self, connection):
        from NaturSQL.service.monitoring import check_query_access
        self.assertFalse(check_query_access())


if __name__ == "__main__":
    unittest.main()
