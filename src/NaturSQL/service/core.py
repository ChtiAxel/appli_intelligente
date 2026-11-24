"""Public business-logic entry points."""

from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
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


async def ask_database_correction(
    question: str,
    previous_sql: str,
    feedback: str,
    llm: LLMClient | None = None,
) -> tuple[str, list[dict[str, Any]]]:
    """Correct a previous SQL query using user feedback and execute it safely."""
    if not feedback or not feedback.strip():
        raise ValueError("Le retour utilisateur ne peut pas etre vide.")
    client = llm or LLMClient()
    schema = await asyncio.to_thread(database_schema)
    sql = validate_read_only_sql(
        await client.generate_sql_correction(
            question=question.strip(),
            previous_sql=previous_sql.strip(),
            feedback=feedback.strip(),
            schema=schema,
        )
    )
    rows = await asyncio.to_thread(execute_query, sql)
    return sql, rows


# --- Contrôle de la requête par double génération --------------------------
# A : SQL écrit à partir de la structure seule. B : SQL écrit avec les valeurs
# réelles qui correspondent à la question. Les deux sont validées en lecture seule
# puis exécutées ; le code compare leurs RÉSULTATS. S'ils diffèrent, un arbitre
# choisit, corrige ou déclare la question ambiguë.

logger = logging.getLogger(__name__)

SQL_CHECK_CONCORDANT = "concordante"     # A et B donnent le même résultat
SQL_CHECK_ARBITRATED = "arbitree"        # résultats différents, l'arbitre a choisi A ou B
SQL_CHECK_CORRECTED = "corrigee"         # l'arbitre a fourni une requête corrigée
SQL_CHECK_AMBIGUOUS = "ambigue"          # question ambiguë : précision à demander
SQL_CHECK_SINGLE = "unique"              # une seule des deux requêtes a abouti
SQL_CHECK_UNRESOLVED = "non_resolue"     # désaccord et arbitrage impossible


@dataclass(frozen=True)
class CheckedQuery:
    """Requête retenue, ses résultats et l'issue du contrôle par double génération."""

    sql: str
    rows: list[dict[str, Any]]
    status: str
    detail: str = ""
    clarification: str = ""


# Mots trop fréquents pour identifier un enseignant ou un cours.
_HINT_STOPWORDS = {
    "les", "des", "une", "un", "le", "la", "du", "de", "dans", "pour", "par", "sur", "avec",
    "qui", "que", "quoi", "quel", "quels", "quelle", "quelles", "combien", "est", "sont",
    "fait", "font", "faire", "donne", "donnent", "donner", "enseigne", "enseignent",
    "enseignant", "enseignants", "professeur", "professeurs", "prof", "profs", "cours",
    "heure", "heures", "seance", "seances", "séance", "séances", "total", "liste", "tous",
    "toutes", "année", "annee", "semestre", "nombre", "the", "and", "et", "ou", "au", "aux",
    "en", "il", "elle", "ils", "elles", "son", "ses", "leur", "leurs", "a-t-il", "y",
}
_HINT_MAX_TERMS = 8
_HINT_MAX_PER_KIND = 5


def _question_terms(question: str) -> list[str]:
    """Mots de la question qui pourraient désigner une valeur de la base."""
    terms: list[str] = []
    for word in re.findall(r"[\w'’.-]+", question or ""):
        word = re.sub(r"^[a-zA-Z][’']", "", word).strip(".-'’")  # « l'enseignant » -> « enseignant »
        if len(word) >= 3 and word.lower() not in _HINT_STOPWORDS and word not in terms:
            terms.append(word)
    return terms[:_HINT_MAX_TERMS]


def value_hints(question: str) -> list[dict[str, str]]:
    """Valeurs réelles (enseignants, cours) qui correspondent aux mots de la question.

    Recherche paramétrée, en session lecture seule, limitée à quelques colonnes
    non sensibles : seules les valeurs trouvées sont transmises au modèle (jamais
    d'échantillon de table). La collation de la base ignore la casse et les accents.
    En cas d'erreur, renvoie une liste vide : la requête B se fait alors sans valeurs.
    """
    terms = _question_terms(question)
    if not terms:
        return []
    hints: list[dict[str, str]] = []
    try:
        with get_query_connection(timeout=config.DB_QUERY_TIMEOUT) as connection:
            with connection.cursor() as cursor:
                placeholders = ", ".join("%s" for _ in terms)
                cursor.execute(
                    "SELECT DISTINCT nom_ens, prenom_ens FROM enseignants "
                    f"WHERE nom_ens IN ({placeholders}) OR prenom_ens IN ({placeholders}) "
                    "ORDER BY nom_ens, prenom_ens LIMIT %s",
                    (*terms, *terms, _HINT_MAX_PER_KIND),
                )
                for row in cursor.fetchall():
                    hints.append({"table": "enseignants", "nom_ens": row["nom_ens"], "prenom_ens": row["prenom_ens"]})

                cursor.execute(
                    f"SELECT id_cours, intitule_cours FROM cours WHERE id_cours IN ({placeholders}) "
                    "ORDER BY id_cours LIMIT %s",
                    (*terms, _HINT_MAX_PER_KIND),
                )
                found_courses = {row["id_cours"]: row["intitule_cours"] for row in cursor.fetchall()}

                long_terms = [t for t in terms if len(t) >= 4]
                if long_terms:
                    score = " + ".join("(intitule_cours LIKE %s)" for _ in long_terms)
                    likes = tuple(f"%{t}%" for t in long_terms)
                    cursor.execute(
                        f"SELECT id_cours, intitule_cours, ({score}) AS score FROM cours "
                        f"WHERE ({score}) > 0 ORDER BY score DESC, id_cours LIMIT %s",
                        (*likes, *likes, _HINT_MAX_PER_KIND),
                    )
                    rows = cursor.fetchall()
                    best = max((int(row["score"]) for row in rows), default=0)
                    for row in rows:
                        if int(row["score"]) == best:  # seulement les cours les plus proches
                            found_courses.setdefault(row["id_cours"], row["intitule_cours"])
                for id_cours, intitule in list(found_courses.items())[:_HINT_MAX_PER_KIND]:
                    hints.append({"table": "cours", "id_cours": id_cours, "intitule_cours": intitule})
    except Exception:
        logger.warning("Recherche des valeurs réelles impossible ; requête B sans valeurs.", exc_info=True)
        return []
    return hints


def _normalized_value(value: Any) -> str:
    if value is None:
        return "∅"
    if isinstance(value, bool):
        value = int(value)
    if isinstance(value, (int, float, Decimal)):
        number = round(float(value), 4)
        return f"{number:.4f}".rstrip("0").rstrip(".")
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, (bytes, bytearray)):
        value = value.decode("utf-8", errors="replace")
    return " ".join(str(value).split()).casefold()


def results_match(rows_a: list[dict[str, Any]], rows_b: list[dict[str, Any]]) -> bool:
    """Vrai si deux résultats contiennent les mêmes données.

    Les noms de colonnes (alias), l'ordre des colonnes et l'ordre des lignes sont
    ignorés ; les nombres sont comparés arrondis (12 = 12.0 = Decimal('12.00')).
    """
    def canonical(rows: list[dict[str, Any]]) -> list[tuple[str, ...]]:
        return sorted(tuple(sorted(_normalized_value(v) for v in row.values())) for row in rows)

    return canonical(rows_a) == canonical(rows_b)


async def _run_candidate(question, schema, llm, generate) -> tuple[str, list[dict[str, Any]]]:
    """Génère, valide en lecture seule et exécute une requête ; une correction en cas d'erreur.

    Si la requête est refusée par la validation ou échoue à l'exécution, le message
    d'erreur est renvoyé au modèle pour UNE correction, elle-même revalidée.
    """
    sql = await generate()
    try:
        sql = validate_read_only_sql(sql)
        return sql, await asyncio.to_thread(execute_query, sql)
    except (ValueError, DatabaseError) as exc:
        repaired = validate_read_only_sql(await llm.repair_sql(question, schema, sql, str(exc)))
        return repaired, await asyncio.to_thread(execute_query, repaired)


async def ask_database_checked(question: str, llm: LLMClient | None = None) -> CheckedQuery:
    """Pipeline principal : deux requêtes indépendantes, comparaison des résultats, arbitrage.

    Toutes les requêtes (A, B, corrections et requête de l'arbitre) passent par
    ``validate_read_only_sql`` puis par une session MariaDB en lecture seule.
    """
    if not question or not question.strip():
        raise ValueError("La question ne peut pas etre vide.")
    question = question.strip()
    client = llm or LLMClient()

    schema, hints = await asyncio.gather(
        asyncio.to_thread(database_schema),
        asyncio.to_thread(value_hints, question),
    )

    # A et B sont générées et exécutées en parallèle.
    result_a, result_b = await asyncio.gather(
        _run_candidate(question, schema, client, lambda: client.generate_sql(question, schema)),
        _run_candidate(question, schema, client, lambda: client.generate_sql_with_values(question, schema, hints)),
        return_exceptions=True,
    )
    ok_a, ok_b = not isinstance(result_a, BaseException), not isinstance(result_b, BaseException)
    if not ok_a and not ok_b:
        raise result_a
    if not (ok_a and ok_b):
        sql, rows = result_a if ok_a else result_b
        failed = result_b if ok_a else result_a
        logger.warning("Une des deux requêtes a échoué : %s", failed)
        return CheckedQuery(sql, rows, SQL_CHECK_SINGLE, "la requête de contrôle n'a pas pu être exécutée")

    sql_a, rows_a = result_a
    sql_b, rows_b = result_b
    if results_match(rows_a, rows_b):
        return CheckedQuery(sql_a, rows_a, SQL_CHECK_CONCORDANT)

    try:
        verdict = await client.arbitrate_sql(question, schema, hints, (sql_a, rows_a), (sql_b, rows_b))
    except Exception:
        logger.warning("Arbitrage impossible", exc_info=True)
        return CheckedQuery(sql_a, rows_a, SQL_CHECK_UNRESOLVED)

    if verdict.choice == "A":
        return CheckedQuery(sql_a, rows_a, SQL_CHECK_ARBITRATED, verdict.reason)
    if verdict.choice == "B":
        return CheckedQuery(sql_b, rows_b, SQL_CHECK_ARBITRATED, verdict.reason)
    if verdict.choice == "C" and verdict.sql:
        try:
            sql_c = validate_read_only_sql(verdict.sql)
            return CheckedQuery(
                sql_c, await asyncio.to_thread(execute_query, sql_c), SQL_CHECK_CORRECTED, verdict.reason
            )
        except (ValueError, DatabaseError):
            logger.warning("Requête corrigée par l'arbitre refusée ou en erreur", exc_info=True)
    clarification = verdict.clarification or "Pouvez-vous préciser votre question ?"
    return CheckedQuery(sql_a, rows_a, SQL_CHECK_AMBIGUOUS, verdict.reason, clarification)


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
