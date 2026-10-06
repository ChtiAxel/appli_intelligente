"""Public business-logic entry points."""

from __future__ import annotations

import asyncio
import re
from typing import Any

from NaturSQL.ollama_client.llm import LLMClient
from NaturSQL.storage.db import get_connection


ALLOWED_TABLES = {
    "enseignants", "cours", "seances", "maquette", "possede", "competences",
    "formations", "formation_groupe", "semaines", "statut", "type_seance",
    "volume_pn", "details",
}

FORBIDDEN_SQL = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|TRUNCATE|REPLACE|GRANT|REVOKE|CALL|SET)\b",
    re.IGNORECASE,
)


def database_schema() -> str:
    """Return the schema exposed to the language model."""
    with get_connection() as connection:
        with connection.cursor() as cursor:
            placeholders = ", ".join("%s" for _ in ALLOWED_TABLES)
            cursor.execute(
                "SELECT TABLE_NAME, COLUMN_NAME, DATA_TYPE "
                "FROM information_schema.COLUMNS "
                "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME IN (" + placeholders + ") "
                "ORDER BY TABLE_NAME, ORDINAL_POSITION",
                tuple(sorted(ALLOWED_TABLES)),
            )
            rows = cursor.fetchall()

    schema: dict[str, list[str]] = {}
    for row in rows:
        schema.setdefault(row["TABLE_NAME"], []).append(
            f"{row['COLUMN_NAME']} {row['DATA_TYPE']}"
        )
    return "\n".join(
        f"TABLE {table}: {', '.join(columns)}" for table, columns in schema.items()
    )


def validate_read_only_sql(sql: str) -> str:
    """Validate and normalize one read-only SQL statement."""
    normalized = sql.strip().strip(";").strip()
    if not normalized or not re.match(r"^(SELECT|WITH)\b", normalized, re.IGNORECASE):
        raise ValueError("La requete generee doit commencer par SELECT ou WITH.")
    if FORBIDDEN_SQL.search(normalized):
        raise ValueError("La requete contient une operation SQL interdite.")
    if ";" in normalized:
        raise ValueError("Une seule requete SQL est autorisee.")
    return normalized


def execute_query(sql: str) -> list[dict[str, Any]]:
    """Execute a validated read-only query (synchronous, pymysql)."""
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(sql)
            return list(cursor.fetchall())


async def text_to_sql(question: str, llm: LLMClient) -> str:
    """Inject the database schema and get a validated read-only query."""
    schema = await asyncio.to_thread(database_schema)
    return validate_read_only_sql(await llm.generate_sql(question, schema))


async def ask_database(question: str, llm: LLMClient | None = None) -> tuple[str, list[dict[str, Any]]]:
    """Translate a question to safe SQL and execute it against MariaDB.

    pymysql is blocking, so DB calls run in a worker thread to keep the
    event loop (and the Gradio UI) responsive.
    """
    if not question or not question.strip():
        raise ValueError("La question ne peut pas etre vide.")
    client = llm or LLMClient()
    sql = await text_to_sql(question.strip(), client)
    rows = await asyncio.to_thread(execute_query, sql)
    return sql, rows


def health_check() -> bool:
    """Return whether the application service is available."""
    return True
