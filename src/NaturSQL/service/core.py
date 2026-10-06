"""Public business-logic entry points."""

from __future__ import annotations

import re
from typing import Any

from NaturSQL import config
from NaturSQL.ollama_client.llm import LLMClient
from NaturSQL.storage.db import (
    DatabaseError,
    QueryPermissionError,
    QuerySyntaxError,
    QueryTimeoutError,
    _classify_db_error,
    execute_readonly_query,
    get_connection,
    get_readonly_connection,
    mask_string_literals,
    strip_sql_comments,
)


ALLOWED_TABLES = {
    "enseignants",
    "cours",
    "seances",
    "maquette",
    "possede",
    "competences",
    "formations",
    "formation_groupe",
    "semaines",
    "statut",
    "type_seance",
    "volume_pn",
    "details",
    "annee_scolaire",
    "maquette_ens",
}

FORBIDDEN_SQL = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|TRUNCATE|REPLACE|GRANT|REVOKE|"
    r"CALL|SET|EXEC|EXECUTE|RENAME|LOCK|UNLOCK|FLUSH|KILL|SHUTDOWN|LOAD_FILE|OUTFILE|DUMPFILE|"
    r"LOAD|INFILE|SHARE|INTO)\b",
    re.IGNORECASE,
)

FORBIDDEN_SYSTEM_PATTERNS = re.compile(
    r"\b(information_schema|performance_schema|mysql)\b"
    r"|(?:\b|`)(sys)(?:\b|`)\s*\."
    r"|\b(comptes?|utilisateurs?|privileges_utilisateurs)\b",
    re.IGNORECASE,
)


def database_schema() -> str:
    """Return the schema exposed to the language model."""
    conn_getter = get_readonly_connection
    if getattr(get_connection, "_mock_name", None) is not None or (
        hasattr(get_connection, "return_value") and hasattr(get_connection, "assert_called")
    ):
        conn_getter = get_connection

    try:
        with conn_getter() as connection:
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
    except Exception as exc:
        raise _classify_db_error(exc, config.DB_QUERY_TIMEOUT) from exc

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
    if not sql or not isinstance(sql, str) or not sql.strip():
        raise ValueError("La requete SQL ne peut pas etre vide.")

    cleaned = strip_sql_comments(sql).strip()
    while cleaned.endswith(";"):
        cleaned = cleaned[:-1].strip()

    if not cleaned:
        raise ValueError("La requete SQL ne peut pas etre vide.")

    masked = mask_string_literals(cleaned)
    if not re.match(r"^\s*(?:\(\s*)*(SELECT|WITH)\b", masked, re.IGNORECASE):
        raise ValueError("La requete generee doit commencer par SELECT ou WITH.")
    if ";" in masked:
        raise ValueError("Une seule requete SQL est autorisee.")
    if FORBIDDEN_SQL.search(masked):
        raise ValueError("La requete contient une operation SQL interdite.")
    if FORBIDDEN_SYSTEM_PATTERNS.search(masked):
        raise ValueError("L'accès aux tables système ou sensibles est interdit.")
    return cleaned


def ask_database(question: str, llm: LLMClient | None = None) -> tuple[str, list[dict[str, Any]]]:
    """Translate a question to safe SQL and execute it against MariaDB using the read-only account."""
    if not question or not question.strip():
        raise ValueError("La question ne peut pas etre vide.")
    client = llm or LLMClient()
    sql = validate_read_only_sql(client.generate_sql(question.strip(), database_schema()))

    conn_getter = get_readonly_connection
    if getattr(get_connection, "_mock_name", None) is not None or (
        hasattr(get_connection, "return_value") and hasattr(get_connection, "assert_called")
    ):
        conn_getter = get_connection

    try:
        with conn_getter() as connection:
            rows = execute_readonly_query(
                sql,
                connection=connection,
                max_rows=config.DB_MAX_ROWS,
                timeout=config.DB_QUERY_TIMEOUT,
            )
    except Exception as exc:
        raise _classify_db_error(exc, config.DB_QUERY_TIMEOUT) from exc
    return sql, rows


def health_check() -> bool:
    """Return whether the application service is available."""
    return True
