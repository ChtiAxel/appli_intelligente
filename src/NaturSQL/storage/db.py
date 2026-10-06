"""Low-level MariaDB connection helper for the `appia` database.

Provides administrative and read-only connection factories, transaction management,
safe query execution with timeouts and row limits, and robust exception classification.
"""

from __future__ import annotations

import re
import socket
from contextlib import contextmanager
from typing import Any, Iterator

import pymysql
import pymysql.cursors

from .. import config


class DatabaseError(Exception):
    """Base exception for safe database persistence operations."""


class QueryTimeoutError(DatabaseError, TimeoutError):
    """Raised when a query exceeds the maximum allowed execution time."""


class QueryPermissionError(DatabaseError, ValueError):
    """Raised when an unauthorized SQL operation or table access is attempted."""


class QuerySyntaxError(DatabaseError, ValueError):
    """Raised when a query has invalid SQL syntax or references missing schema elements."""


def get_connection() -> pymysql.connections.Connection:
    """Open a new administrative connection to the `appia` database."""
    return pymysql.connect(
        host=config.DB_HOST,
        port=config.DB_PORT,
        user=config.DB_USER,
        password=config.DB_PASSWORD,
        database=config.DB_NAME,
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=False,
    )


def get_readonly_connection(
    timeout: float | None = None,
) -> pymysql.connections.Connection:
    """Open a dedicated read-only connection to MariaDB with strict timeouts.
    
    Used exclusively for AI-generated query execution.
    """
    effective_timeout = float(timeout if timeout is not None else config.DB_QUERY_TIMEOUT)
    conn = pymysql.connect(
        host=config.DB_HOST,
        port=config.DB_PORT,
        user=config.DB_READONLY_USER,
        password=config.DB_READONLY_PASSWORD,
        database=config.DB_NAME,
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=True,
        read_timeout=effective_timeout,
        write_timeout=effective_timeout,
        connect_timeout=effective_timeout,
    )
    # Attempt to set MariaDB server-side max statement execution time if supported
    try:
        with conn.cursor() as cur:
            cur.execute(f"SET SESSION max_statement_time = {effective_timeout}")
    except Exception:
        # Unsupported by some MariaDB configurations or test mocks; socket timeout remains watchdog
        pass
    return conn


@contextmanager
def transaction() -> Iterator[pymysql.cursors.DictCursor]:
    """Yield a cursor inside a committed transaction (rolled back on error)."""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            yield cursor
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _classify_db_error(exc: Exception, timeout: float) -> DatabaseError:
    """Classify low-level database driver errors into clean domain exceptions."""
    if isinstance(exc, DatabaseError):
        return exc

    cause = getattr(exc, "__cause__", None)
    context = getattr(exc, "__context__", None)

    # Timeouts (native Python or wrapped)
    if (
        isinstance(exc, (TimeoutError, socket.timeout))
        or isinstance(cause, (TimeoutError, socket.timeout))
        or isinstance(context, (TimeoutError, socket.timeout))
    ):
        return QueryTimeoutError(
            f"Délai d'exécution dépassé : la requête a mis plus de {timeout}s à s'exécuter."
        )

    # Built-in network connection errors
    if (
        isinstance(exc, (ConnectionError, BrokenPipeError))
        or isinstance(cause, (ConnectionError, BrokenPipeError))
        or isinstance(context, (ConnectionError, BrokenPipeError))
    ):
        return DatabaseError(f"Erreur de connexion à la base de données : {exc}")

    error_code: int | None = None
    error_msg = str(exc)
    if hasattr(exc, "args") and exc.args:
        if isinstance(exc.args[0], int):
            error_code = exc.args[0]
            if len(exc.args) > 1:
                error_msg = str(exc.args[1])
        else:
            error_msg = str(exc.args[0])

    msg_lower = error_msg.lower()

    # Timeouts (MariaDB/MySQL error codes and messages)
    if (
        error_code in (1317, 1969, 3024, 70100)
        or "max_statement_time" in msg_lower
        or "timed out" in msg_lower
        or "timeout" in msg_lower
        or "interrupted" in msg_lower
    ):
        return QueryTimeoutError(
            f"Délai d'exécution dépassé : la requête a été interrompue (limite de {timeout}s)."
        )

    # Permission denied / unauthorized
    if (
        error_code in (1142, 1143, 1044, 1045, 1227, 1370, 1698)
        or "command denied" in msg_lower
        or "access denied" in msg_lower
        or "permission denied" in msg_lower
    ):
        return QueryPermissionError(
            "Accès refusé : vous n'avez pas les autorisations nécessaires pour exécuter cette opération."
        )

    # Syntax errors
    if error_code == 1064 or "syntax error" in msg_lower or "check the manual" in msg_lower:
        return QuerySyntaxError(
            "Erreur de syntaxe SQL : la requête générée comporte une erreur de syntaxe."
        )

    # Unknown table or column, ambiguous column
    if error_code in (1146, 1054, 1052) or "ambiguous" in msg_lower:
        return QuerySyntaxError(
            f"Erreur de référence SQL : {error_msg}"
        )

    # Connection errors
    if (
        error_code in (2002, 2003, 2005, 2006, 2013)
        or "can't connect" in msg_lower
        or "connection refused" in msg_lower
        or "lost connection" in msg_lower
        or "unknown mysql server host" in msg_lower
    ):
        return DatabaseError(f"Erreur de connexion à la base de données : {error_msg}")

    return DatabaseError(f"Erreur de base de données : {error_msg}")


def strip_sql_comments(sql: str) -> str:
    """Remove SQL comments (-- ..., /* ... */, # ...) while preserving string literals and backticks."""
    if not sql or not isinstance(sql, str):
        return ""
    tokens: list[str] = []
    i = 0
    n = len(sql)
    while i < n:
        char = sql[i]
        if char in ("'", '"', "`"):
            quote = char
            start = i
            i += 1
            while i < n:
                if sql[i] == "\\":
                    i += 2
                elif sql[i] == quote:
                    if i + 1 < n and sql[i + 1] == quote:
                        i += 2
                    else:
                        i += 1
                        break
                else:
                    i += 1
            tokens.append(sql[start:min(i, n)])
        elif char == "/" and i + 1 < n and sql[i + 1] == "*":
            i += 2
            while i < n:
                if sql[i] == "*" and i + 1 < n and sql[i + 1] == "/":
                    i += 2
                    break
                i += 1
            tokens.append(" ")
        elif (char == "-" and i + 1 < n and sql[i + 1] == "-") or char == "#":
            while i < n and sql[i] not in ("\r", "\n"):
                i += 1
            tokens.append(" ")
        else:
            tokens.append(char)
            i += 1
    return "".join(tokens)


def mask_string_literals(sql: str) -> str:
    """Mask string literals with spaces to preserve indices for SQL structural validation.
    
    Backtick identifiers are preserved so system/sensitive table checks can inspect them.
    """
    if not sql or not isinstance(sql, str):
        return ""
    res: list[str] = []
    i = 0
    n = len(sql)
    while i < n:
        char = sql[i]
        if char in ("'", '"'):
            quote = char
            start = i
            i += 1
            while i < n:
                if sql[i] == "\\":
                    i += 2
                elif sql[i] == quote:
                    if i + 1 < n and sql[i + 1] == quote:
                        i += 2
                    else:
                        i += 1
                        break
                else:
                    i += 1
            res.append(" " * (min(i, n) - start))
        elif char == "`":
            start = i
            i += 1
            while i < n:
                if sql[i] == "\\":
                    i += 2
                elif sql[i] == "`":
                    if i + 1 < n and sql[i + 1] == "`":
                        i += 2
                    else:
                        i += 1
                        break
                else:
                    i += 1
            res.append(sql[start:min(i, n)])
        else:
            res.append(char)
            i += 1
    return "".join(res)


def mask_strings_and_subqueries(sql: str) -> str:
    """Mask string literals and subqueries inside parentheses so top-level clauses can be matched."""
    if not sql or not isinstance(sql, str):
        return ""
    res = []
    i = 0
    n = len(sql)
    depth = 0
    while i < n:
        char = sql[i]
        if char in ("'", '"'):
            quote = char
            start = i
            i += 1
            while i < n:
                if sql[i] == "\\":
                    i += 2
                elif sql[i] == quote:
                    if i + 1 < n and sql[i + 1] == quote:
                        i += 2
                    else:
                        i += 1
                        break
                else:
                    i += 1
            res.append(" " * (min(i, n) - start))
        elif char == "`":
            start = i
            i += 1
            while i < n:
                if sql[i] == "\\":
                    i += 2
                elif sql[i] == "`":
                    if i + 1 < n and sql[i + 1] == "`":
                        i += 2
                    else:
                        i += 1
                        break
                else:
                    i += 1
            chunk_len = min(i, n) - start
            if depth > 0:
                res.append(" " * chunk_len)
            else:
                res.append(sql[start:min(i, n)])
        elif char == "(":
            depth += 1
            res.append(" ")
            i += 1
        elif char == ")":
            depth = max(0, depth - 1)
            res.append(" ")
            i += 1
        elif depth > 0:
            res.append(" ")
            i += 1
        else:
            res.append(char)
            i += 1
    return "".join(res)


def enforce_sql_limit(sql: str, max_rows: int) -> str:
    """Ensure the top-level query enforces a LIMIT or FETCH FIRST <= max_rows."""
    cleaned = strip_sql_comments(sql).strip()
    while cleaned.endswith(";"):
        cleaned = cleaned[:-1].strip()
    if not cleaned:
        return cleaned

    effective_limit = max(1, int(max_rows))
    masked = mask_strings_and_subqueries(cleaned)

    # Pattern 0: Standard SQL FETCH (FIRST|NEXT) [count] ROWS? ONLY (supported by MariaDB 11)
    m_fetch = re.search(
        r"\bFETCH\s+(?:FIRST|NEXT)(?:\s+(\d+))?\s+ROWS?\s+ONLY\b",
        masked,
        re.IGNORECASE,
    )
    if m_fetch:
        raw_count = m_fetch.group(1)
        if raw_count is None:
            # Count omitted -> defaults to 1 row in standard SQL (<= effective_limit)
            return cleaned
        count = int(raw_count)
        if count > effective_limit:
            return cleaned[: m_fetch.start(1)] + str(effective_limit) + cleaned[m_fetch.end(1) :]
        return cleaned

    # Pattern 1: LIMIT \s* (\d+) \s* , \s* (\d+)  (MySQL LIMIT offset, count)
    m1 = re.search(r"\bLIMIT\s+(\d+)\s*,\s*(\d+)\b", masked, re.IGNORECASE)
    if m1:
        count = int(m1.group(2))
        if count > effective_limit:
            return cleaned[: m1.start(2)] + str(effective_limit) + cleaned[m1.end(2) :]
        return cleaned

    # Pattern 2: LIMIT \s* (\d+) \s+ OFFSET \s+ (\d+)
    m2 = re.search(r"\bLIMIT\s+(\d+)\s+OFFSET\s+(\d+)\b", masked, re.IGNORECASE)
    if m2:
        count = int(m2.group(1))
        if count > effective_limit:
            return cleaned[: m2.start(1)] + str(effective_limit) + cleaned[m2.end(1) :]
        return cleaned

    # Pattern 3: LIMIT \s* (\d+)
    m3 = re.search(r"\bLIMIT\s+(\d+)\b", masked, re.IGNORECASE)
    if m3:
        count = int(m3.group(1))
        if count > effective_limit:
            return cleaned[: m3.start(1)] + str(effective_limit) + cleaned[m3.end(1) :]
        return cleaned

    # Pattern 4: Standard SQL OFFSET count ROWS? alone without FETCH or LIMIT
    m_offset_rows = re.search(r"\bOFFSET\s+(\d+)\s+ROWS?\b", masked, re.IGNORECASE)
    if m_offset_rows:
        return f"{cleaned} FETCH NEXT {effective_limit} ROWS ONLY"

    return f"{cleaned} LIMIT {effective_limit}"


def execute_readonly_query(
    sql: str,
    params: tuple | list | None = None,
    max_rows: int | None = None,
    timeout: float | None = None,
    connection: pymysql.connections.Connection | None = None,
) -> list[dict[str, Any]]:
    """Execute a query safely against MariaDB using the read-only account.
    
    Enforces read-only validation, execution timeout, and maximum returned row count.
    Never lets low-level database exceptions crash the application.
    """
    raw_timeout = timeout if timeout is not None else config.DB_QUERY_TIMEOUT
    try:
        effective_timeout = float(raw_timeout) if float(raw_timeout) > 0 else float(config.DB_QUERY_TIMEOUT)
    except (ValueError, TypeError):
        effective_timeout = float(config.DB_QUERY_TIMEOUT)

    raw_max_rows = max_rows if max_rows is not None else config.DB_MAX_ROWS
    try:
        effective_max_rows = int(raw_max_rows) if int(raw_max_rows) > 0 else int(config.DB_MAX_ROWS)
    except (ValueError, TypeError):
        effective_max_rows = int(config.DB_MAX_ROWS)

    # Validate read-only safety
    from NaturSQL.service.core import validate_read_only_sql

    try:
        validated_sql = validate_read_only_sql(sql)
    except ValueError as val_err:
        raise QueryPermissionError(f"Opération refusée : {val_err}") from val_err

    validated_sql = enforce_sql_limit(validated_sql, effective_max_rows)

    conn = None
    should_close = connection is None

    try:
        conn = connection or get_readonly_connection(timeout=effective_timeout)
        with conn.cursor() as cursor:
            cursor.execute(validated_sql, params)
            # Retrieve rows
            raw_rows = (
                cursor.fetchall()
                if hasattr(cursor, "fetchall")
                else cursor.fetchmany(effective_max_rows)
            )
            if isinstance(raw_rows, (list, tuple)):
                results = [
                    dict(r) if isinstance(r, dict) else r
                    for r in raw_rows[:effective_max_rows]
                ]
            else:
                results = raw_rows
        return results
    except Exception as exc:
        raise _classify_db_error(exc, effective_timeout) from exc
    finally:
        if should_close and conn is not None:
            try:
                conn.close()
            except Exception:
                pass


def safe_execute_readonly_query(
    sql: str,
    params: tuple | list | None = None,
    max_rows: int | None = None,
    timeout: float | None = None,
    connection: pymysql.connections.Connection | None = None,
) -> tuple[list[dict[str, Any]], str | None]:
    """Execute a read-only query and return (results, error_message) without raising."""
    try:
        rows = execute_readonly_query(
            sql=sql,
            params=params,
            max_rows=max_rows,
            timeout=timeout,
            connection=connection,
        )
        return rows, None
    except DatabaseError as err:
        return [], str(err)
    except Exception as exc:
        return [], f"Erreur inattendue : {exc}"
