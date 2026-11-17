"""Public business-logic entry points."""

from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass
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
    get_query_connection,
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
    r"|\b(comptes?|utilisateurs?|privileges_utilisateurs|conversations|messages)\b",
    re.IGNORECASE,
)


def database_schema() -> str:
    """Return the structure (tables, columns, keys, relations) exposed to the LLM.

    Only ``information_schema`` metadata is read: no row of any business table
    is ever selected, so the prompt never contains the data itself. ``DATA_TYPE``
    is used instead of ``COLUMN_TYPE`` because the latter exposes ENUM/SET
    values; defaults and comments are deliberately left out for the same reason.
    """
    tables = tuple(sorted(ALLOWED_TABLES))
    placeholders = ", ".join("%s" for _ in tables)
    try:
        with get_query_connection(timeout=config.DB_QUERY_TIMEOUT) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT TABLE_NAME, TABLE_TYPE "
                    "FROM information_schema.TABLES "
                    "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME IN (" + placeholders + ")",
                    tables,
                )
                table_rows = cursor.fetchall()
                cursor.execute(
                    "SELECT TABLE_NAME, COLUMN_NAME, DATA_TYPE, COLUMN_KEY "
                    "FROM information_schema.COLUMNS "
                    "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME IN (" + placeholders + ") "
                    "ORDER BY TABLE_NAME, ORDINAL_POSITION",
                    tables,
                )
                column_rows = cursor.fetchall()
                cursor.execute(
                    "SELECT TABLE_NAME, COLUMN_NAME, REFERENCED_TABLE_NAME, REFERENCED_COLUMN_NAME "
                    "FROM information_schema.KEY_COLUMN_USAGE "
                    "WHERE TABLE_SCHEMA = DATABASE() AND REFERENCED_TABLE_NAME IS NOT NULL "
                    "AND TABLE_NAME IN (" + placeholders + ") "
                    "AND REFERENCED_TABLE_NAME IN (" + placeholders + ") "
                    "ORDER BY TABLE_NAME, COLUMN_NAME",
                    tables + tables,
                )
                fk_rows = cursor.fetchall()
    except Exception as exc:
        raise _classify_db_error(exc, config.DB_QUERY_TIMEOUT) from exc

    return format_schema(table_rows, column_rows, fk_rows)


def format_schema(
    table_rows: list[dict[str, Any]],
    column_rows: list[dict[str, Any]],
    fk_rows: list[dict[str, Any]],
) -> str:
    """Render schema metadata as compact text for the SQL prompt."""
    views = {
        row["TABLE_NAME"] for row in table_rows if str(row.get("TABLE_TYPE", "")).upper() == "VIEW"
    }
    foreign_keys = {
        (row["TABLE_NAME"], row["COLUMN_NAME"]): f"{row['REFERENCED_TABLE_NAME']}.{row['REFERENCED_COLUMN_NAME']}"
        for row in fk_rows
    }

    columns: dict[str, list[str]] = {}
    primary_keys: dict[str, list[str]] = {}
    for row in column_rows:
        table, column = row["TABLE_NAME"], row["COLUMN_NAME"]
        description = f"{column} {row['DATA_TYPE']}"
        if row.get("COLUMN_KEY") == "PRI":
            primary_keys.setdefault(table, []).append(column)
        target = foreign_keys.get((table, column))
        if target:
            description += f" -> {target}"
        columns.setdefault(table, []).append(description)

    lines = []
    for table, cols in columns.items():
        kind = "VUE" if table in views else "TABLE"
        pk = primary_keys.get(table)
        pk_text = f" [cle primaire: {', '.join(pk)}]" if pk else ""
        lines.append(f"{kind} {table}{pk_text}: {', '.join(cols)}")

    relations = [
        f"{table}.{column} -> {target}" for (table, column), target in foreign_keys.items()
    ]
    if relations:
        lines.append("")
        lines.append("RELATIONS (cles etrangeres, a utiliser pour les jointures):")
        lines.extend(relations)
    return "\n".join(lines)


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


def execute_query(sql: str) -> list[dict[str, Any]]:
    """Execute a validated query with the application account in a read-only session (synchronous, pymysql)."""
    try:
        with get_query_connection(timeout=config.DB_QUERY_TIMEOUT) as connection:
            return execute_readonly_query(
                sql,
                connection=connection,
                max_rows=config.DB_MAX_ROWS,
                timeout=config.DB_QUERY_TIMEOUT,
            )
    except Exception as exc:
        raise _classify_db_error(exc, config.DB_QUERY_TIMEOUT) from exc


async def text_to_sql(question: str, llm: LLMClient) -> str:
    """Inject the database schema and get a validated read-only query."""
    schema = await asyncio.to_thread(database_schema)
    return validate_read_only_sql(await llm.generate_sql(question, schema))


async def ask_database(question: str, llm: LLMClient | None = None) -> tuple[str, list[dict[str, Any]]]:
    """Translate a question to safe SQL and execute it against MariaDB using the application account in a read-only session.

    pymysql is blocking, so DB calls run in a worker thread to keep the
    event loop (and the Gradio UI) responsive.
    """
    if not question or not question.strip():
        raise ValueError("La question ne peut pas etre vide.")
    client = llm or LLMClient()
    sql = await text_to_sql(question.strip(), client)
    rows = await asyncio.to_thread(execute_query, sql)
    return sql, rows


VERIFICATION_OK = "verifiee"
VERIFICATION_CORRECTED = "corrigee"
VERIFICATION_FAILED = "incoherente"
VERIFICATION_UNAVAILABLE = "indisponible"


@dataclass(frozen=True)
class VerifiedAnswer:
    """French synthesis plus the outcome of the verification step."""

    summary: str
    status: str | None  # None : rien à vérifier (aucun résultat)
    detail: str = ""


async def summarize_and_verify(
    question: str, rows: list[dict[str, Any]], llm: LLMClient
) -> VerifiedAnswer:
    """Synthesize the results, then check the synthesis against the raw data.

    The verifier receives the question, the generated answer and the raw rows.
    If it finds an inconsistency, the synthesis is regenerated once with its
    remark and verified again. A summary failure propagates to the caller; a
    verifier failure only marks the answer as not verified.
    """
    summary = await llm.summarize_results(question, rows)
    if not rows:
        return VerifiedAnswer(summary, None)

    try:
        verdict = await llm.verify_answer(question, summary, rows)
    except Exception:
        return VerifiedAnswer(summary, VERIFICATION_UNAVAILABLE)
    if verdict.coherent:
        return VerifiedAnswer(summary, VERIFICATION_OK)

    try:
        corrected = await llm.summarize_results(question, rows, correction=verdict.probleme)
        second = await llm.verify_answer(question, corrected, rows)
    except Exception:
        return VerifiedAnswer(summary, VERIFICATION_FAILED, verdict.probleme)
    if second.coherent:
        return VerifiedAnswer(corrected, VERIFICATION_CORRECTED, verdict.probleme)
    return VerifiedAnswer(corrected, VERIFICATION_FAILED, second.probleme)


def health_check() -> bool:
    """Return whether the application service is available."""
    return True
