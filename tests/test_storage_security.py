"""Tests de robustesse et de sécurité pour la couche de stockage SQL NaturSQL.

Vérifie :
1. La création et les permissions de l'utilisateur lecture seule stricte (natursql_readonly).
2. Le rejet immédiat et gracieux des requêtes malveillantes (DROP, DELETE, UPDATE, INSERT, ALTER, etc.).
3. Le blocage des accès aux tables systèmes (mysql, information_schema, performance_schema, sys)
   et sensibles (compte, utilisateurs).
4. Le respect strict des limites de temps (timeout) et de volume (max rows).
5. La classification et le formatage propre des exceptions de base de données sans crash.
6. L'exécution sécurisée contre une instance MariaDB réelle si disponible.
"""

from __future__ import annotations

import socket
from unittest.mock import MagicMock, Mock, patch

import pymysql
import pytest

from NaturSQL import config
from NaturSQL.service import core
from NaturSQL.storage import db
from NaturSQL.storage.db import (
    DatabaseError,
    QueryPermissionError,
    QuerySyntaxError,
    QueryTimeoutError,
    _classify_db_error,
    execute_readonly_query,
    get_readonly_connection,
    safe_execute_readonly_query,
)


# =====================================================================
# 1. Tests de configuration et de connexion
# =====================================================================

def test_readonly_user_configuration():
    """Vérifie que les variables d'environnement de sécurité sont définies avec des valeurs par défaut saines."""
    assert config.DB_READONLY_USER == "natursql_readonly"
    assert config.DB_READONLY_PASSWORD != ""
    assert config.DB_QUERY_TIMEOUT == 3.0
    assert config.DB_MAX_ROWS == 50


@patch("NaturSQL.storage.db.pymysql.connect")
def test_readonly_connection_parameters(mock_connect):
    """Vérifie que get_readonly_connection applique les identifiants en lecture seule et les timeouts."""
    mock_conn = MagicMock()
    mock_connect.return_value = mock_conn

    conn = get_readonly_connection(timeout=3.0)

    mock_connect.assert_called_once_with(
        host=config.DB_HOST,
        port=config.DB_PORT,
        user=config.DB_READONLY_USER,
        password=config.DB_READONLY_PASSWORD,
        database=config.DB_NAME,
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=True,
        read_timeout=3.0,
        write_timeout=3.0,
        connect_timeout=3.0,
    )
    # Vérifie la configuration du timeout MariaDB au niveau de la session
    mock_conn.cursor.return_value.__enter__.return_value.execute.assert_called_with(
        "SET SESSION max_statement_time = 3.0"
    )
    assert conn == mock_conn


# =====================================================================
# 2. Rejet des requêtes malveillantes simulées (DROP, DELETE, etc.)
# =====================================================================

@pytest.mark.parametrize(
    "malicious_sql",
    [
        "DROP TABLE cours",
        "DROP TABLE IF EXISTS enseignants",
        "DELETE FROM cours WHERE 1=1",
        "DELETE FROM enseignants",
        "UPDATE utilisateurs SET mdp = 'hacked'",
        "INSERT INTO cours (id_cours) VALUES ('HACK')",
        "TRUNCATE TABLE seances",
        "ALTER TABLE cours DROP COLUMN intitule_cours",
        "GRANT ALL PRIVILEGES ON *.* TO 'hacker'@'%'",
        "REVOKE SELECT ON *.* FROM 'natursql_readonly'@'%'",
        "CALL secret_admin_procedure()",
        "SET GLOBAL max_connections = 0",
        "SELECT * FROM cours; DROP TABLE enseignants;",
        "SELECT * FROM cours; DELETE FROM cours;",
    ],
)
def test_rejection_of_destructive_sql(malicious_sql):
    """Vérifie que les opérations destructives sont formellement refusées."""
    # 1. Validation de niveau service
    with pytest.raises(ValueError):
        core.validate_read_only_sql(malicious_sql)

    # 2. Exécution sécurisée
    with pytest.raises(QueryPermissionError) as exc_info:
        execute_readonly_query(malicious_sql)
    assert "Opération refusée" in str(exc_info.value)


@pytest.mark.parametrize(
    "system_table_sql",
    [
        "SELECT * FROM mysql.user",
        "SELECT user, authentication_string FROM mysql.global_priv",
        "SELECT * FROM information_schema.user_privileges",
        "SELECT * FROM performance_schema.threads",
        "SELECT * FROM sys.version",
        "SELECT * FROM compte",
        "SELECT nom, prenom, mdp FROM utilisateurs",
        "SELECT * FROM privileges_utilisateurs",
    ],
)
def test_rejection_of_system_and_sensitive_tables(system_table_sql):
    """Vérifie que les requêtes ciblant les tables systèmes ou sensibles sont bloquées."""
    with pytest.raises(ValueError):
        core.validate_read_only_sql(system_table_sql)

    with pytest.raises(QueryPermissionError) as exc_info:
        execute_readonly_query(system_table_sql)
    assert "Opération refusée" in str(exc_info.value)


# =====================================================================
# 3. Exécution gracieuse sans crash (safe_execute_readonly_query)
# =====================================================================

def test_safe_execute_readonly_query_handles_malicious_sql_gracefully():
    """Vérifie que safe_execute_readonly_query ne fait jamais planter l'application."""
    rows, error = safe_execute_readonly_query("DROP TABLE cours")
    assert rows == []
    assert error is not None
    assert "Opération refusée" in error

    rows, error = safe_execute_readonly_query("SELECT * FROM mysql.user")
    assert rows == []
    assert error is not None
    assert "tables système ou sensibles" in error


def test_safe_execute_readonly_query_success():
    """Vérifie le fonctionnement normal de safe_execute_readonly_query avec mock."""
    mock_conn = MagicMock()
    mock_cursor = mock_conn.cursor.return_value.__enter__.return_value
    mock_cursor.fetchall.return_value = [{"id_cours": "R1.01", "intitule_cours": "Init"}]

    rows, error = safe_execute_readonly_query(
        "SELECT id_cours, intitule_cours FROM cours",
        connection=mock_conn,
    )
    assert error is None
    assert len(rows) == 1
    assert rows[0]["id_cours"] == "R1.01"


# =====================================================================
# 4. Interception et classification des exceptions MariaDB/PyMySQL
# =====================================================================

def test_classify_permission_denied_error():
    """Vérifie que l'erreur 1142 (command denied) est convertie en QueryPermissionError."""
    raw_error = pymysql.err.ProgrammingError(
        1142,
        "DROP command denied to user 'natursql_readonly'@'localhost' for table 'cours'",
    )
    classified = _classify_db_error(raw_error, timeout=3.0)
    assert isinstance(classified, QueryPermissionError)
    assert "Accès refusé" in str(classified)


def test_classify_access_denied_error():
    """Vérifie que l'erreur 1044/1045 (access denied) est convertie en QueryPermissionError."""
    raw_error = pymysql.err.OperationalError(
        1044,
        "Access denied for user 'natursql_readonly'@'localhost' to database 'mysql'",
    )
    classified = _classify_db_error(raw_error, timeout=3.0)
    assert isinstance(classified, QueryPermissionError)
    assert "Accès refusé" in str(classified)


def test_classify_syntax_error():
    """Vérifie que l'erreur 1064 (syntax error) est convertie en QuerySyntaxError."""
    raw_error = pymysql.err.ProgrammingError(
        1064,
        "You have an error in your SQL syntax; check the manual that corresponds to your MariaDB server version",
    )
    classified = _classify_db_error(raw_error, timeout=3.0)
    assert isinstance(classified, QuerySyntaxError)
    assert "Erreur de syntaxe SQL" in str(classified)


def test_classify_unknown_table_error():
    """Vérifie que l'erreur 1146 (table doesn't exist) est convertie en QuerySyntaxError."""
    raw_error = pymysql.err.ProgrammingError(
        1146,
        "Table 'appia.inexistante' doesn't exist",
    )
    classified = _classify_db_error(raw_error, timeout=3.0)
    assert isinstance(classified, QuerySyntaxError)
    assert "Erreur de référence SQL" in str(classified)


def test_classify_timeout_error_mariadb():
    """Vérifie que l'erreur 1969 (max_statement_time exceeded) est convertie en QueryTimeoutError."""
    raw_error = pymysql.err.OperationalError(
        1969,
        "Query execution was interrupted (max_statement_time exceeded)",
    )
    classified = _classify_db_error(raw_error, timeout=3.0)
    assert isinstance(classified, QueryTimeoutError)
    assert "Délai d'exécution dépassé" in str(classified)


def test_classify_timeout_error_socket():
    """Vérifie que socket.timeout ou TimeoutError est converti en QueryTimeoutError."""
    raw_error = socket.timeout("timed out")
    classified = _classify_db_error(raw_error, timeout=3.0)
    assert isinstance(classified, QueryTimeoutError)
    assert "Délai d'exécution dépassé" in str(classified)


def test_classify_generic_database_error():
    """Vérifie que les autres erreurs sont proprement encapsulées dans DatabaseError."""
    raw_error = pymysql.err.InternalError(1815, "Internal error in engine")
    classified = _classify_db_error(raw_error, timeout=3.0)
    assert isinstance(classified, DatabaseError)
    assert "Erreur de base de données" in str(classified)


# =====================================================================
# 5. Respect des limites de temps (Timeout) et de lignes (Max Rows)
# =====================================================================

def test_sql_limit_injection_and_row_capping():
    """Vérifie que la clause LIMIT 50 est ajoutée ou ajustée si nécessaire."""
    mock_conn = MagicMock()
    mock_cursor = mock_conn.cursor.return_value.__enter__.return_value

    # Cas 1 : Requête sans LIMIT -> Ajout de LIMIT 50
    mock_cursor.fetchall.return_value = [{"id": i} for i in range(100)]
    rows = execute_readonly_query("SELECT * FROM details", connection=mock_conn, max_rows=50)
    executed_sql = mock_cursor.execute.call_args[0][0]
    assert "LIMIT 50" in executed_sql
    assert len(rows) == 50

    # Cas 2 : Requête avec LIMIT 200 trop grand -> Réduit à LIMIT 50
    mock_cursor.fetchall.return_value = [{"id": i} for i in range(100)]
    rows = execute_readonly_query("SELECT * FROM details LIMIT 200", connection=mock_conn, max_rows=50)
    executed_sql = mock_cursor.execute.call_args[0][0]
    assert "LIMIT 50" in executed_sql
    assert "LIMIT 200" not in executed_sql
    assert len(rows) == 50

    # Cas 3 : Requête avec LIMIT 10 inférieur à max_rows -> Conservé
    mock_cursor.fetchall.return_value = [{"id": i} for i in range(10)]
    rows = execute_readonly_query("SELECT * FROM details LIMIT 10", connection=mock_conn, max_rows=50)
    executed_sql = mock_cursor.execute.call_args[0][0]
    assert "LIMIT 10" in executed_sql
    assert len(rows) == 10


def test_execution_timeout_raises_query_timeout_error():
    """Vérifie qu'un timeout lors de cursor.execute lève bien QueryTimeoutError."""
    mock_conn = MagicMock()
    mock_cursor = mock_conn.cursor.return_value.__enter__.return_value
    mock_cursor.execute.side_effect = pymysql.err.OperationalError(
        1969, "Query execution was interrupted (max_statement_time exceeded)"
    )

    with pytest.raises(QueryTimeoutError) as exc_info:
        execute_readonly_query("SELECT * FROM cours", connection=mock_conn, timeout=3.0)

    assert "Délai d'exécution dépassé" in str(exc_info.value)


# =====================================================================
# 6. Intégration avec ask_database
# =====================================================================

def test_ask_database_uses_readonly_connection_and_limits():
    """Vérifie que ask_database utilise bien la connexion lecture seule et applique les limites."""
    mock_conn = MagicMock()
    mock_conn.__enter__.return_value = mock_conn
    mock_cursor = mock_conn.cursor.return_value.__enter__.return_value
    mock_cursor.fetchall.return_value = [{"count": 42}]

    llm = Mock()
    llm.generate_sql.return_value = "SELECT COUNT(*) AS count FROM cours"

    with patch.object(core, "database_schema", return_value="TABLE cours: id_cours varchar"):
        with patch("NaturSQL.service.core.get_readonly_connection", return_value=mock_conn):
            sql, rows = core.ask_database("Combien de cours ?", llm=llm)

    assert sql == "SELECT COUNT(*) AS count FROM cours"
    assert rows == [{"count": 42}]
    # La requête finale exécutée sur le curseur comporte bien la limite
    executed_sql = mock_cursor.execute.call_args[0][0]
    assert "LIMIT 50" in executed_sql


def test_ask_database_rejects_malicious_llm_output_cleanly():
    """Vérifie que si l'IA tente de générer une commande malveillante, elle est interceptée."""
    llm = Mock()
    llm.generate_sql.return_value = "DROP TABLE enseignants"

    with patch.object(core, "database_schema", return_value="TABLE enseignants: id_ens varchar"):
        with pytest.raises(ValueError) as exc_info:
            core.ask_database("Supprime les profs", llm=llm)
    assert "SELECT ou WITH" in str(exc_info.value) or "opération SQL interdite" in str(exc_info.value)



# =====================================================================
# 7. Tests d'intégration réels avec le conteneur MariaDB (si actif)
# =====================================================================

def _can_connect_to_live_mariadb() -> bool:
    """Vérifie si le conteneur MariaDB local est accessible."""
    try:
        conn = pymysql.connect(
            host=config.DB_HOST,
            port=config.DB_PORT,
            user=config.DB_READONLY_USER,
            password=config.DB_READONLY_PASSWORD,
            database="appia",
            connect_timeout=2.0,
        )
        conn.close()
        return True
    except Exception:
        return False


MARIADB_AVAILABLE = _can_connect_to_live_mariadb()


@pytest.mark.skipif(not MARIADB_AVAILABLE, reason="MariaDB container is not running on localhost:3307")
class TestLiveMariaDBSecurity:
    """Suite de tests d'intégrité exécutée directement contre l'instance MariaDB réelle."""

    @pytest.fixture(autouse=True)
    def setup_live_db(self, monkeypatch):
        """Assure que les tests en direct ciblent la base appia."""
        monkeypatch.setattr(config, "DB_NAME", "appia")

    def test_live_readonly_user_can_select_pedagogical_tables(self):

        """Vérifie que natursql_readonly peut lire les tables pédagogiques."""
        rows = execute_readonly_query("SELECT id_cours, intitule_cours FROM cours", max_rows=5)
        assert len(rows) > 0
        assert "id_cours" in rows[0]

        rows = execute_readonly_query("SELECT id_ens, nom_ens FROM enseignants", max_rows=5)
        assert len(rows) > 0
        assert "nom_ens" in rows[0]

    def test_live_readonly_user_cannot_drop_or_modify_tables(self):
        """Vérifie que le moteur MariaDB lui-même refuse DROP, DELETE, INSERT pour natursql_readonly."""
        conn = get_readonly_connection()
        try:
            with conn.cursor() as cur:
                with pytest.raises(pymysql.err.OperationalError) as exc_info:
                    cur.execute("DROP TABLE cours")
                assert exc_info.value.args[0] == 1142
                assert "denied to user 'natursql_readonly'" in str(exc_info.value)

                with pytest.raises(pymysql.err.OperationalError) as exc_info:
                    cur.execute("DELETE FROM cours")
                assert exc_info.value.args[0] == 1142
                assert "denied to user 'natursql_readonly'" in str(exc_info.value)

                with pytest.raises(pymysql.err.OperationalError) as exc_info:
                    cur.execute("INSERT INTO cours (id_cours, intitule_cours) VALUES ('TEST', 'Test')")
                assert exc_info.value.args[0] == 1142
                assert "denied to user 'natursql_readonly'" in str(exc_info.value)
        finally:
            conn.close()

    def test_live_readonly_user_cannot_access_sensitive_or_system_tables(self):
        """Vérifie que MariaDB refuse l'accès aux tables mysql.user, compte, utilisateurs."""
        conn = get_readonly_connection()
        try:
            with conn.cursor() as cur:
                with pytest.raises(pymysql.err.OperationalError) as exc_info:
                    cur.execute("SELECT * FROM mysql.user")
                assert exc_info.value.args[0] == 1142
                assert "denied to user 'natursql_readonly'" in str(exc_info.value)

                with pytest.raises(pymysql.err.OperationalError) as exc_info:
                    cur.execute("SELECT * FROM compte")
                assert exc_info.value.args[0] == 1142
                assert "denied to user 'natursql_readonly'" in str(exc_info.value)

                with pytest.raises(pymysql.err.OperationalError) as exc_info:
                    cur.execute("SELECT * FROM utilisateurs")
                assert exc_info.value.args[0] == 1142
                assert "denied to user 'natursql_readonly'" in str(exc_info.value)
        finally:
            conn.close()

    def test_live_query_row_limiting(self):
        """Vérifie que la limite de 50 lignes est respectée sur la vraie base contenant >100 lignes."""
        rows = execute_readonly_query("SELECT * FROM cours")
        assert len(rows) == 50

    def test_live_subquery_limit_enforced(self):
        """Vérifie que les sous-requêtes n'empêchent pas la limitation de la requête principale."""
        rows = execute_readonly_query(
            "SELECT c.id_cours FROM cours c JOIN (SELECT id_cours FROM seances LIMIT 5) s ON c.id_cours = s.id_cours"
        )
        assert len(rows) <= 50

    def test_live_comment_query_limited(self):
        """Vérifie qu'une requête avec commentaires est nettoyée et que la limite s'applique."""
        rows = execute_readonly_query(
            "-- Pre-comment\nSELECT * FROM cours -- Post-comment"
        )
        assert len(rows) == 50

    def test_live_string_literal_with_semicolon_and_keywords(self):
        """Vérifie qu'une recherche avec point-virgule ou mot-clé dans une chaîne s'exécute."""
        rows = execute_readonly_query(
            "SELECT id_cours, intitule_cours FROM cours WHERE intitule_cours != 'Math; UPDATE' LIMIT 5"
        )
        assert len(rows) <= 5

    def test_live_into_outfile_rejected_cleanly(self):
        """Vérifie que SELECT INTO OUTFILE est intercepté et rejeté sans planter."""
        with pytest.raises(QueryPermissionError):
            execute_readonly_query("SELECT * FROM cours INTO OUTFILE '/tmp/malicious.txt'")

    def test_live_fetch_first_syntax_capped(self):
        """Vérifie que la clause standard FETCH FIRST 500 ROWS ONLY est reconnue et plafonnée à 50 sans syntax error."""
        rows = execute_readonly_query("SELECT id_cours FROM cours FETCH FIRST 500 ROWS ONLY")
        assert len(rows) == 50

    def test_live_offset_rows_without_fetch(self):
        """Vérifie que OFFSET n ROWS sans FETCH applique FETCH NEXT max_rows sans erreur 1064 sur MariaDB."""
        rows = execute_readonly_query("SELECT id_cours FROM cours OFFSET 0 ROWS", max_rows=5)
        assert len(rows) <= 5
        assert len(rows) > 0

    def test_live_fetch_first_row_only(self):
        """Vérifie que FETCH FIRST ROW ONLY (sans chiffre) s'exécute sans erreur 1064 sur MariaDB."""
        rows = execute_readonly_query("SELECT id_cours FROM cours FETCH FIRST ROW ONLY")
        assert len(rows) <= 1

    def test_live_parenthesized_query_execution(self):
        """Vérifie que les requêtes avec parenthèses comme (SELECT ...) UNION (SELECT ...) s'exécutent sur MariaDB."""
        rows = execute_readonly_query("(SELECT 1 AS val) UNION (SELECT 2 AS val)", max_rows=50)
        assert len(rows) == 2

    def test_live_backticked_identifier_with_dashes(self):
        """Vérifie que les identifiants backtickés avec tirets s'exécutent sans troncature sur MariaDB."""
        rows = execute_readonly_query("SELECT 1 AS `col--1`")
        assert rows == [{"col--1": 1}]



# =====================================================================
# 8. Tests adversariaux supplémentaires (contournements avancés)
# =====================================================================

@pytest.mark.parametrize(
    "evasive_sql",
    [
        "SELECT * FROM `information_schema`.`tables`",
        "SELECT * FROM `information_schema`.tables",
        "SELECT * FROM information_schema . tables",
        "SELECT * FROM information_schema/*comment*/.tables",
        "SELECT * FROM `mysql`.`user`",
        "SELECT * FROM mysql . user",
        "SELECT * FROM `sys`.`version`",
        "SELECT * FROM sys . version",
        "SELECT * FROM `compte`",
        "SELECT * FROM appia.compte",
        "SELECT * FROM appia . `compte`",
        "SELECT * FROM `utilisateurs`",
        "SELECT * FROM appia.`utilisateurs`",
        "SELECT * FROM `privileges_utilisateurs`",
    ],
)
def test_evasive_system_and_sensitive_table_access_blocked(evasive_sql):
    """Vérifie que les contournements par backticks, espaces ou commentaires sont bloqués."""
    with pytest.raises(ValueError):
        core.validate_read_only_sql(evasive_sql)

    with pytest.raises(QueryPermissionError):
        execute_readonly_query(evasive_sql)


@pytest.mark.parametrize(
    "dangerous_sql",
    [
        "SELECT * FROM cours INTO OUTFILE '/tmp/hack.txt'",
        "SELECT * FROM cours INTO DUMPFILE '/tmp/hack.bin'",
        "SELECT LOAD_FILE('/etc/passwd')",
        "LOAD DATA INFILE '/etc/passwd' INTO TABLE cours",
        "SELECT * FROM cours WHERE 1=1 INFILE '/tmp/x'",
        "RENAME TABLE cours TO hacked",
        "LOCK TABLES cours WRITE",
        "UNLOCK TABLES",
        "FLUSH PRIVILEGES",
        "KILL 123",
        "SHUTDOWN",
    ],
)
def test_dangerous_file_and_admin_commands_blocked(dangerous_sql):
    """Vérifie que les commandes d'écriture de fichier et d'administration sont bloquées."""
    with pytest.raises(ValueError):
        core.validate_read_only_sql(dangerous_sql)

    with pytest.raises(QueryPermissionError):
        execute_readonly_query(dangerous_sql)


def test_subquery_limit_enforcement_and_offset():
    """Vérifie que le limiteur traite correctement les sous-requêtes et les syntaxes OFFSET."""
    mock_conn = MagicMock()
    mock_cursor = mock_conn.cursor.return_value.__enter__.return_value
    mock_cursor.fetchall.return_value = [{"id": i} for i in range(100)]

    # Sous-requête avec son propre LIMIT : la requête englobante doit recevoir LIMIT 50
    sql = "SELECT id_cours FROM cours WHERE id_cours IN (SELECT id_cours FROM seances LIMIT 5)"
    rows = execute_readonly_query(sql, connection=mock_conn, max_rows=50)
    executed_sql = mock_cursor.execute.call_args[0][0]
    assert executed_sql.endswith("LIMIT 50")
    assert "LIMIT 5" in executed_sql

    # Requête avec LIMIT offset, count
    sql_offset = "SELECT * FROM cours LIMIT 10, 200"
    rows = execute_readonly_query(sql_offset, connection=mock_conn, max_rows=50)
    executed_sql = mock_cursor.execute.call_args[0][0]
    assert "LIMIT 10, 50" in executed_sql

    # Requête avec LIMIT count OFFSET offset
    sql_offset2 = "SELECT * FROM cours LIMIT 200 OFFSET 10"
    rows = execute_readonly_query(sql_offset2, connection=mock_conn, max_rows=50)
    executed_sql = mock_cursor.execute.call_args[0][0]
    assert "LIMIT 50 OFFSET 10" in executed_sql

    # Requête avec chaîne contenant 'LIMIT 200'
    sql_str = "SELECT * FROM cours WHERE intitule_cours = 'LIMIT 200'"
    rows = execute_readonly_query(sql_str, connection=mock_conn, max_rows=50)
    executed_sql = mock_cursor.execute.call_args[0][0]
    assert "intitule_cours = 'LIMIT 200'" in executed_sql
    assert executed_sql.endswith("LIMIT 50")


def test_sql_comments_cleaning():
    """Vérifie que les commentaires ne masquent pas ou ne court-circuitent pas la limitation SQL."""
    mock_conn = MagicMock()
    mock_cursor = mock_conn.cursor.return_value.__enter__.return_value
    mock_cursor.fetchall.return_value = [{"id": 1}]

    # Commentaire de début
    execute_readonly_query("-- comment\nSELECT * FROM cours", connection=mock_conn, max_rows=50)
    executed_sql = mock_cursor.execute.call_args[0][0]
    assert "LIMIT 50" in executed_sql

    # Commentaire de fin : ne doit pas commenter la clause LIMIT
    execute_readonly_query("SELECT * FROM cours -- end comment", connection=mock_conn, max_rows=50)
    executed_sql = mock_cursor.execute.call_args[0][0]
    assert "LIMIT 50" in executed_sql


def test_string_literal_with_semicolon_and_keywords_accepted():
    """Vérifie que les points-virgules et mots-clés dans des chaînes littérales ne sont pas faussement rejetés."""
    # Point-virgule dans une chaîne littérale
    sql1 = "SELECT * FROM cours WHERE intitule_cours = 'Math; Stats'"
    assert core.validate_read_only_sql(sql1) == sql1

    # Mot-clé SQL dans une chaîne littérale
    sql2 = "SELECT * FROM cours WHERE intitule_cours = 'UPDATE'"
    assert core.validate_read_only_sql(sql2) == sql2

    sql3 = "SELECT * FROM cours WHERE intitule_cours = 'DROP'"
    assert core.validate_read_only_sql(sql3) == sql3


def test_database_connection_failure_classification():
    """Vérifie que les erreurs de connexion à la base sont classifiées en DatabaseError sans crash."""
    with patch("NaturSQL.storage.db.get_readonly_connection", side_effect=pymysql.err.OperationalError(2003, "Can't connect to MySQL")):
        with pytest.raises(DatabaseError) as exc_info:
            execute_readonly_query("SELECT 1")
        assert "connexion" in str(exc_info.value).lower()


def test_enforce_sql_limit_with_trailing_and_inner_comments():
    """Vérifie que enforce_sql_limit ne commente jamais sa clause LIMIT et ignore les faux LIMIT en commentaire."""
    # Commentaire à la fin : LIMIT 50 doit être exécutable et non commenté
    res = db.enforce_sql_limit("SELECT * FROM cours -- end comment", 50)
    assert res.endswith("LIMIT 50")
    assert "-- end comment" not in res

    # Faux LIMIT dans un commentaire
    res2 = db.enforce_sql_limit("SELECT * FROM cours -- LIMIT 1000", 50)
    assert res2.endswith("LIMIT 50")
    assert "LIMIT 1000" not in res2


def test_enforce_sql_limit_fetch_first_support():
    """Vérifie que la syntaxe standard FETCH FIRST / NEXT est plafonnée sans ajouter de LIMIT redondant."""
    res = db.enforce_sql_limit("SELECT * FROM cours FETCH FIRST 500 ROWS ONLY", 50)
    assert res == "SELECT * FROM cours FETCH FIRST 50 ROWS ONLY"

    res_next = db.enforce_sql_limit("SELECT * FROM cours OFFSET 10 ROWS FETCH NEXT 500 ROWS ONLY", 50)
    assert res_next == "SELECT * FROM cours OFFSET 10 ROWS FETCH NEXT 50 ROWS ONLY"

    res_keep = db.enforce_sql_limit("SELECT * FROM cours FETCH FIRST 10 ROWS ONLY", 50)
    assert res_keep == "SELECT * FROM cours FETCH FIRST 10 ROWS ONLY"


def test_validate_read_only_sql_invalid_and_empty_inputs():
    """Vérifie que les entrées vides, None ou non-string sont rejetées proprement par ValueError."""
    for invalid in (None, "", "   ", "\n\t", 123, []):
        with pytest.raises(ValueError) as exc_info:
            core.validate_read_only_sql(invalid)  # type: ignore
        assert "ne peut pas etre vide" in str(exc_info.value)

    # safe_execute_readonly_query gère gracieusement sans TypeError
    rows, err = safe_execute_readonly_query(None)
    assert rows == []
    assert err is not None
    assert "ne peut pas etre vide" in err


def test_execute_readonly_query_sanitizes_negative_limits_and_timeouts():
    """Vérifie que des paramètres aberrants (négatifs ou nuls) pour timeout et max_rows sont assainis."""
    mock_conn = MagicMock()
    mock_cursor = mock_conn.cursor.return_value.__enter__.return_value
    mock_cursor.fetchall.return_value = [{"id": 1}]

    # max_rows négatif -> assaini à config.DB_MAX_ROWS (50)
    rows = execute_readonly_query("SELECT 1", connection=mock_conn, max_rows=-10, timeout=-5.0)
    executed_sql = mock_cursor.execute.call_args[0][0]
    assert "LIMIT 50" in executed_sql
    assert len(rows) == 1


def test_classify_db_error_unknown_host_and_connection_reset():
    """Vérifie que les erreurs d'hôte inconnu (code 2005) et de réinitialisation réseau sont classifiées."""
    # Code 2005 CR_UNKNOWN_HOST
    err_2005 = pymysql.err.OperationalError(2005, "Unknown MySQL server host 'invalid-host' (11001)")
    classified = _classify_db_error(err_2005, timeout=3.0)
    assert isinstance(classified, DatabaseError)
    assert "connexion" in str(classified).lower()

    # ConnectionResetError natif
    conn_reset = ConnectionResetError("Connection reset by peer")
    classified_reset = _classify_db_error(conn_reset, timeout=3.0)
    assert isinstance(classified_reset, DatabaseError)
    assert "connexion" in str(classified_reset).lower()


def test_classify_db_error_context_timeout():
    """Vérifie qu'un timeout imbriqué dans __context__ est bien détecté."""
    raw_error = pymysql.err.OperationalError(2013, "Lost connection to server")
    raw_error.__context__ = socket.timeout("timed out")
    classified = _classify_db_error(raw_error, timeout=3.0)
    assert isinstance(classified, QueryTimeoutError)
    assert "Délai d'exécution dépassé" in str(classified)


def test_enforce_sql_limit_offset_rows_without_fetch():
    """Vérifie que OFFSET n ROWS sans FETCH applique FETCH NEXT max_rows ROWS ONLY sans casser la syntaxe MariaDB."""
    # Plafonnement standard SQL FETCH NEXT après OFFSET
    res_rows = db.enforce_sql_limit("SELECT * FROM cours OFFSET 10 ROWS", 50)
    assert res_rows == "SELECT * FROM cours OFFSET 10 ROWS FETCH NEXT 50 ROWS ONLY"

    res_row = db.enforce_sql_limit("SELECT * FROM cours OFFSET 10 ROW", 50)
    assert res_row == "SELECT * FROM cours OFFSET 10 ROW FETCH NEXT 50 ROWS ONLY"

    mock_conn = MagicMock()
    mock_cursor = mock_conn.cursor.return_value.__enter__.return_value
    mock_cursor.fetchall.return_value = [{"id": 1}]
    execute_readonly_query("SELECT id_cours FROM cours OFFSET 0 ROWS", connection=mock_conn, max_rows=5)
    executed = mock_cursor.execute.call_args[0][0]
    assert "FETCH NEXT 5 ROWS ONLY" in executed


def test_enforce_sql_limit_fetch_row_without_count():
    """Vérifie que FETCH FIRST ROW ONLY (sans nombre explicite, implicitement 1) est préservé sans ajouter de LIMIT invalide."""
    res_first = db.enforce_sql_limit("SELECT * FROM cours FETCH FIRST ROW ONLY", 50)
    assert res_first == "SELECT * FROM cours FETCH FIRST ROW ONLY"

    res_next = db.enforce_sql_limit("SELECT * FROM cours FETCH NEXT ROW ONLY", 50)
    assert res_next == "SELECT * FROM cours FETCH NEXT ROW ONLY"

    mock_conn = MagicMock()
    mock_cursor = mock_conn.cursor.return_value.__enter__.return_value
    mock_cursor.fetchall.return_value = [{"id": 1}]
    execute_readonly_query("SELECT id_cours FROM cours FETCH FIRST ROW ONLY", connection=mock_conn)
    executed = mock_cursor.execute.call_args[0][0]
    assert executed == "SELECT id_cours FROM cours FETCH FIRST ROW ONLY"
    assert "LIMIT" not in executed


def test_validate_read_only_sql_parenthesized_queries():
    """Vérifie que les requêtes SELECT et WITH entre parenthèses sont autorisées, mais que les commandes destructives restent bloquées."""
    # Requêtes légitimes avec parenthèses
    assert core.validate_read_only_sql("(SELECT * FROM cours)") == "(SELECT * FROM cours)"
    assert core.validate_read_only_sql("((SELECT * FROM cours))") == "((SELECT * FROM cours))"
    assert core.validate_read_only_sql("(WITH x AS (SELECT 1) SELECT * FROM x)") == "(WITH x AS (SELECT 1) SELECT * FROM x)"
    assert core.validate_read_only_sql("(SELECT 1) UNION (SELECT 2)") == "(SELECT 1) UNION (SELECT 2)"

    # Tentatives malveillantes emballées dans des parenthèses
    for evil in ("(DROP TABLE cours)", "((DROP TABLE cours))", "(UPDATE cours SET intitule_cours='x')", "(DELETE FROM cours)"):
        with pytest.raises(ValueError):
            core.validate_read_only_sql(evil)

    mock_conn = MagicMock()
    mock_cursor = mock_conn.cursor.return_value.__enter__.return_value
    mock_cursor.fetchall.return_value = [{"val": 1}, {"val": 2}]
    rows = execute_readonly_query("(SELECT 1 AS val) UNION (SELECT 2 AS val)", connection=mock_conn, max_rows=50)
    assert len(rows) == 2
    executed = mock_cursor.execute.call_args[0][0]
    assert executed.endswith("LIMIT 50")


def test_backticked_identifiers_with_comments_and_parentheses():
    """Vérifie que les identifiants MariaDB entre backticks contenant des tirets ou parenthèses ne sont pas corrompus."""
    # Tirets dans un identifiant backtické ne doivent pas être traités comme des commentaires SQL
    cleaned = db.strip_sql_comments("SELECT 1 AS `col--1` FROM cours")
    assert "`col--1`" in cleaned
    assert "FROM cours" in cleaned

    # Parenthèses dans un identifiant backtické ne doivent pas altérer la profondeur des sous-requêtes
    masked = db.mask_strings_and_subqueries("SELECT 1 AS `count(total)` LIMIT 10")
    assert "LIMIT 10" in masked

    mock_conn = MagicMock()
    mock_cursor = mock_conn.cursor.return_value.__enter__.return_value
    mock_cursor.fetchall.return_value = [{"col--1": 1}]
    rows = execute_readonly_query("SELECT 1 AS `col--1`", connection=mock_conn)
    assert rows == [{"col--1": 1}]
    executed = mock_cursor.execute.call_args[0][0]
    assert "`col--1`" in executed


def test_mask_strings_and_subqueries_invalid_and_none_input():
    """Vérifie que mask_strings_and_subqueries résiste à None et aux entrées non-chaînes sans TypeError."""
    for invalid in (None, 123, [], {}):
        assert db.mask_strings_and_subqueries(invalid) == ""  # type: ignore


def test_trailing_backslash_length_preservation():
    """Vérifie que la longueur de masquage est strictement préservée même en cas d'antislash final dans une chaîne non terminée."""
    raw = "SELECT 'hello" + chr(92)
    assert len(db.mask_string_literals(raw)) == len(raw)
    assert len(db.mask_strings_and_subqueries(raw)) == len(raw)


def test_error_classification_interrupted_column_denied_and_ambiguous():
    """Vérifie la classification de ER_QUERY_INTERRUPTED (1317), ER_COLUMNACCESS_DENIED (1143) et colonnes ambiguës (1052)."""
    # 1317 Interrupted -> QueryTimeoutError
    err_1317 = pymysql.err.OperationalError(1317, "Query execution was interrupted")
    assert isinstance(_classify_db_error(err_1317, timeout=3.0), QueryTimeoutError)

    # 1143 Column access denied -> QueryPermissionError
    err_1143 = pymysql.err.OperationalError(1143, "SELECT command denied to user 'natursql_readonly'@'localhost' for column 'mdp' in table 'utilisateurs'")
    assert isinstance(_classify_db_error(err_1143, timeout=3.0), QueryPermissionError)

    # 1052 Ambiguous column in field list -> QuerySyntaxError
    err_1052 = pymysql.err.OperationalError(1052, "Column 'id_cours' in field list is ambiguous")
    assert isinstance(_classify_db_error(err_1052, timeout=3.0), QuerySyntaxError)


def test_forbidden_sql_blocks_for_share_and_into():
    """Vérifie que les clauses de verrouillage FOR SHARE et d'injection INTO sont rejetées."""
    for evil in (
        "SELECT * FROM cours FOR SHARE",
        "SELECT * FROM cours LOCK IN SHARE MODE",
        "SELECT * INTO @var FROM cours",
        "SELECT * INTO OUTFILE '/tmp/dump.txt' FROM cours",
    ):
        with pytest.raises(ValueError) as exc_info:
            core.validate_read_only_sql(evil)
        assert "interdite" in str(exc_info.value)


