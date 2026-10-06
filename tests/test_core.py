import asyncio
import unittest
from unittest.mock import AsyncMock, Mock, patch

from NaturSQL.service import core


class CoreTests(unittest.TestCase):
    def test_validate_read_only_sql_accepts_select_and_with(self):
        self.assertEqual(core.validate_read_only_sql(" SELECT * FROM details; "), "SELECT * FROM details")
        self.assertEqual(core.validate_read_only_sql("WITH x AS (SELECT 1) SELECT * FROM x"), "WITH x AS (SELECT 1) SELECT * FROM x")

    def test_validate_read_only_sql_rejects_invalid_or_multiple_statements(self):
        for sql in ("", "UPDATE users SET name='x'", "DROP TABLE users", "SELECT 1; SELECT 2"):
            with self.assertRaises(ValueError):
                core.validate_read_only_sql(sql)

    @patch("NaturSQL.service.core.get_connection")
    def test_database_schema_formats_columns(self, get_connection):
        cursor = get_connection.return_value.__enter__.return_value.cursor.return_value.__enter__.return_value
        cursor.fetchall.return_value = [
            {"TABLE_NAME": "details", "COLUMN_NAME": "nom_ens", "DATA_TYPE": "varchar"},
            {"TABLE_NAME": "details", "COLUMN_NAME": "type_seance", "DATA_TYPE": "varchar"},
        ]
        schema = core.database_schema()
        self.assertEqual(schema, "TABLE details: nom_ens varchar, type_seance varchar")

    @patch("NaturSQL.service.core.get_connection")
    def test_ask_database_generates_and_executes_sql(self, get_connection):
        cursor = get_connection.return_value.__enter__.return_value.cursor.return_value.__enter__.return_value
        cursor.fetchall.return_value = [{"count": 2}]
        llm = Mock()
        llm.generate_sql = AsyncMock(return_value="SELECT COUNT(*) AS count FROM details")
        with patch.object(core, "database_schema", return_value="TABLE details: id int"):
            sql, rows = asyncio.run(core.ask_database("Combien ?", llm))
        self.assertEqual(sql, "SELECT COUNT(*) AS count FROM details")
        self.assertEqual(rows, [{"count": 2}])
        llm.generate_sql.assert_awaited_once_with("Combien ?", "TABLE details: id int")

    def test_health_check(self):
        self.assertTrue(core.health_check())


if __name__ == "__main__":
    unittest.main()