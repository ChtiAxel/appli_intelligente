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

    @patch("NaturSQL.service.core.get_query_connection")
    def test_database_schema_formats_columns(self, get_connection):
        cursor = get_connection.return_value.__enter__.return_value.cursor.return_value.__enter__.return_value
        cursor.fetchall.side_effect = [
            [{"TABLE_NAME": "details", "TABLE_TYPE": "VIEW"}],
            [
                {"TABLE_NAME": "details", "COLUMN_NAME": "nom_ens", "DATA_TYPE": "varchar", "COLUMN_KEY": ""},
                {"TABLE_NAME": "details", "COLUMN_NAME": "type_seance", "DATA_TYPE": "varchar", "COLUMN_KEY": ""},
            ],
            [],
        ]
        schema = core.database_schema()
        self.assertEqual(schema, "VUE details: nom_ens varchar, type_seance varchar")

    @patch("NaturSQL.service.core.get_query_connection")
    def test_database_schema_reads_only_metadata_never_table_rows(self, get_connection):
        cursor = get_connection.return_value.__enter__.return_value.cursor.return_value.__enter__.return_value
        cursor.fetchall.side_effect = [[], [], []]
        core.database_schema()
        queries = [c.args[0] for c in cursor.execute.call_args_list]
        self.assertEqual(len(queries), 3)
        for sql in queries:
            # Seules les vues de métadonnées sont lues, jamais le contenu des tables.
            self.assertRegex(sql, r"FROM information_schema\.(TABLES|COLUMNS|KEY_COLUMN_USAGE) ")
            self.assertNotIn("COLUMN_TYPE", sql)  # exposerait les valeurs ENUM
            self.assertNotIn("COLUMN_DEFAULT", sql)
            self.assertNotIn("COMMENT", sql)

    def test_format_schema_includes_keys_and_relations(self):
        schema = core.format_schema(
            [
                {"TABLE_NAME": "enseignants", "TABLE_TYPE": "BASE TABLE"},
                {"TABLE_NAME": "seances", "TABLE_TYPE": "BASE TABLE"},
            ],
            [
                {"TABLE_NAME": "enseignants", "COLUMN_NAME": "id_ens", "DATA_TYPE": "varchar", "COLUMN_KEY": "PRI"},
                {"TABLE_NAME": "enseignants", "COLUMN_NAME": "nom_ens", "DATA_TYPE": "varchar", "COLUMN_KEY": ""},
                {"TABLE_NAME": "seances", "COLUMN_NAME": "id_ens", "DATA_TYPE": "varchar", "COLUMN_KEY": "PRI"},
                {"TABLE_NAME": "seances", "COLUMN_NAME": "id_cours", "DATA_TYPE": "varchar", "COLUMN_KEY": "PRI"},
            ],
            [
                {"TABLE_NAME": "seances", "COLUMN_NAME": "id_ens", "REFERENCED_TABLE_NAME": "enseignants", "REFERENCED_COLUMN_NAME": "id_ens"},
            ],
        )
        self.assertEqual(
            schema,
            "TABLE enseignants [cle primaire: id_ens]: id_ens varchar, nom_ens varchar\n"
            "TABLE seances [cle primaire: id_ens, id_cours]: id_ens varchar -> enseignants.id_ens, id_cours varchar\n"
            "\n"
            "RELATIONS (cles etrangeres, a utiliser pour les jointures):\n"
            "seances.id_ens -> enseignants.id_ens",
        )

    @patch("NaturSQL.service.core.get_query_connection")
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

    @patch("NaturSQL.service.core.get_query_connection")
    def test_ask_database_correction_uses_context_and_feedback(self, get_connection):
        cursor = get_connection.return_value.__enter__.return_value.cursor.return_value.__enter__.return_value
        cursor.fetchall.return_value = [{"nom": "Dupont"}]
        llm = Mock()
        llm.generate_sql_correction = AsyncMock(return_value="SELECT nom FROM details WHERE annee = 2024")
        with patch.object(core, "database_schema", return_value="TABLE details: nom varchar, annee int"):
            sql, rows = asyncio.run(
                core.ask_database_correction(
                    question="Qui enseigne en 2024 ?",
                    previous_sql="SELECT nom FROM details WHERE annee = 2023",
                    feedback="Tu t'es trompé d'année, prends 2024",
                    llm=llm,
                )
            )
        self.assertEqual(sql, "SELECT nom FROM details WHERE annee = 2024")
        self.assertEqual(rows, [{"nom": "Dupont"}])
        llm.generate_sql_correction.assert_awaited_once_with(
            question="Qui enseigne en 2024 ?",
            previous_sql="SELECT nom FROM details WHERE annee = 2023",
            feedback="Tu t'es trompé d'année, prends 2024",
            schema="TABLE details: nom varchar, annee int",
        )

    def test_ask_database_correction_rejects_empty_feedback(self):
        with self.assertRaises(ValueError):
            asyncio.run(
                core.ask_database_correction(
                    question="Q",
                    previous_sql="SELECT 1",
                    feedback="   ",
                )
            )

    def test_health_check(self):
        self.assertTrue(core.health_check())


if __name__ == "__main__":
    unittest.main()