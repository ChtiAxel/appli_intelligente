"""Contrôle de la requête par double génération (A : structure seule, B : avec valeurs réelles).

Ollama et MariaDB sont simulés : aucun serveur n'est nécessaire.
"""

from __future__ import annotations

import asyncio
import json
from contextlib import contextmanager
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from NaturSQL.ollama_client.async_client import AsyncOllamaClient
from NaturSQL.ollama_client.llm import (
    ARBITER_PREVIEW_ROWS,
    ARBITER_SYSTEM_PROMPT,
    SQL_SYSTEM_PROMPT,
    SQL_VALUES_SYSTEM_PROMPT,
    Arbitration,
    LLMClient,
    OllamaResponseError,
    _parse_arbitration,
)
from NaturSQL.service import core
from NaturSQL import ui_gradio

SQL_A = "SELECT SUM(duree_seance) AS h FROM details WHERE nom_ens = 'Buret' AND type_seance LIKE 'TP%'"
SQL_B = "SELECT SUM(s.duree_seance) AS total FROM seances s JOIN enseignants e ON e.id_ens = s.id_ens WHERE e.nom_ens = 'Buret'"
SQL_C = "SELECT SUM(duree_seance) AS h FROM details WHERE nom_ens = 'Buret'"
HINTS = [{"table": "enseignants", "nom_ens": "Buret", "prenom_ens": "Aurélien"}]


# -- Comparaison des résultats ---------------------------------------------------------


def test_results_match_ignores_aliases_column_order_row_order_and_number_format():
    a = [{"h": Decimal("22.50"), "nom": "Buret"}, {"h": 3, "nom": "Benoit"}]
    b = [{"Nom": "BENOIT", "total": 3.0}, {"Nom": "buret", "total": 22.5}]
    assert core.results_match(a, b)


@pytest.mark.parametrize(
    ("a", "b"),
    [
        ([{"h": 22.5}], [{"h": 30}]),                       # valeur différente
        ([{"h": 22.5}], [{"h": 22.5}, {"h": 1}]),          # ligne en plus
        ([{"nom": "Buret"}], [{"nom": "Buret", "p": "A"}]),  # colonne en plus
        ([{"n": None}], [{"n": 0}]),                       # NULL n'est pas 0
    ],
)
def test_results_match_detects_differences(a, b):
    assert not core.results_match(a, b)


def test_results_match_empty_results():
    assert core.results_match([], [])
    assert not core.results_match([], [{"n": 1}])


# -- Recherche des valeurs réelles -----------------------------------------------------


def test_question_terms_keeps_names_and_codes_and_drops_common_words():
    terms = core._question_terms("Combien d'heures de TP fait l'enseignant Buret en Qualité de développement (R5.08) ?")
    assert terms == ["Buret", "Qualité", "développement", "R5.08"]


def _fake_connection(results_per_query):
    cursor = MagicMock()
    cursor.fetchall.side_effect = results_per_query
    connection = MagicMock()
    connection.__enter__.return_value = connection
    connection.cursor.return_value.__enter__.return_value = cursor
    return connection, cursor


def test_value_hints_uses_parameters_and_returns_only_matches():
    connection, cursor = _fake_connection([
        [{"nom_ens": "Buret", "prenom_ens": "Aurélien"}],                                    # enseignants
        [],                                                                                 # codes de cours
        [{"id_cours": "R5.08", "intitule_cours": "Qualité de développement", "score": 2},
         {"id_cours": "R1.01", "intitule_cours": "Initiation au développement", "score": 1}],  # intitulés
    ])
    with patch.object(core, "get_query_connection", return_value=connection) as get_conn:
        hints = core.value_hints("Heures de Buret en Qualité de développement ?")
    get_conn.assert_called_once()  # session en lecture seule (get_query_connection)
    assert hints == [
        {"table": "enseignants", "nom_ens": "Buret", "prenom_ens": "Aurélien"},
        {"table": "cours", "id_cours": "R5.08", "intitule_cours": "Qualité de développement"},
    ]  # seul le cours le plus proche est gardé
    for call in cursor.execute.call_args_list:
        sql, params = call.args
        assert "Buret" not in sql and "%Qualit" not in sql  # jamais de valeur dans le texte SQL
        assert params


def test_value_hints_returns_empty_list_when_database_fails():
    with patch.object(core, "get_query_connection", side_effect=RuntimeError("base indisponible")):
        assert core.value_hints("Heures de Buret ?") == []


def test_value_hints_without_useful_word_does_not_query():
    with patch.object(core, "get_query_connection") as get_conn:
        assert core.value_hints("Combien de cours ?") == []
    get_conn.assert_not_called()


# -- Orchestration A/B ---------------------------------------------------------------------


@pytest.fixture
def db(monkeypatch):
    """Base simulée : chaque SQL renvoie les lignes prévues ; on note ce qui est exécuté."""
    state = {"rows": {SQL_A: [{"h": 22.5}], SQL_B: [{"total": 22.5}], SQL_C: [{"h": 30}]}, "executed": []}

    def execute(sql):
        state["executed"].append(sql)
        if sql not in state["rows"]:
            raise core.QuerySyntaxError("Unknown column 'x'")
        return state["rows"][sql]

    monkeypatch.setattr(core, "database_schema", lambda: "TABLE details: nom_ens varchar")
    monkeypatch.setattr(core, "value_hints", lambda q: HINTS)
    monkeypatch.setattr(core, "execute_query", execute)
    return state


def fake_llm(sql_a=SQL_A, sql_b=SQL_B, arbitration=None, repaired=None):
    llm = Mock()
    llm.generate_sql = AsyncMock(return_value=sql_a)
    llm.generate_sql_with_values = AsyncMock(return_value=sql_b)
    llm.arbitrate_sql = AsyncMock(return_value=arbitration or Arbitration("A"))
    llm.repair_sql = AsyncMock(return_value=repaired)
    return llm


async def test_matching_results_are_confirmed_without_arbiter(db):
    llm = fake_llm()
    result = await core.ask_database_checked("Heures de TP de Buret ?", llm)
    assert result == core.CheckedQuery(SQL_A, [{"h": 22.5}], core.SQL_CHECK_CONCORDANT)
    llm.arbitrate_sql.assert_not_awaited()
    llm.generate_sql.assert_awaited_once_with("Heures de TP de Buret ?", "TABLE details: nom_ens varchar")
    llm.generate_sql_with_values.assert_awaited_once_with("Heures de TP de Buret ?", "TABLE details: nom_ens varchar", HINTS)


async def test_a_and_b_are_generated_in_parallel(db):
    order = []

    async def slow(label, sql):
        order.append(f"start-{label}")
        await asyncio.sleep(0.05)
        order.append(f"end-{label}")
        return sql

    async def gen_a(question, schema):
        return await slow("A", SQL_A)

    async def gen_b(question, schema, hints):
        return await slow("B", SQL_B)

    llm = fake_llm()
    llm.generate_sql = AsyncMock(side_effect=gen_a)
    llm.generate_sql_with_values = AsyncMock(side_effect=gen_b)
    await core.ask_database_checked("Q ?", llm)
    assert order[:2] == ["start-A", "start-B"]


async def test_disagreement_goes_to_arbiter_which_can_choose_b(db):
    db["rows"][SQL_B] = [{"total": 30}]
    llm = fake_llm(arbitration=Arbitration("B", reason="A oublie les TPB"))
    result = await core.ask_database_checked("Q ?", llm)
    assert (result.sql, result.rows, result.status, result.detail) == (SQL_B, [{"total": 30}], core.SQL_CHECK_ARBITRATED, "A oublie les TPB")
    sql_a_arg, sql_b_arg = llm.arbitrate_sql.call_args.args[3], llm.arbitrate_sql.call_args.args[4]
    assert sql_a_arg == (SQL_A, [{"h": 22.5}]) and sql_b_arg == (SQL_B, [{"total": 30}])


async def test_arbiter_corrected_query_is_validated_and_executed(db):
    db["rows"][SQL_B] = [{"total": 99}]
    llm = fake_llm(arbitration=Arbitration("C", sql=SQL_C, reason="les deux sont incomplètes"))
    result = await core.ask_database_checked("Q ?", llm)
    assert (result.sql, result.rows, result.status) == (SQL_C, [{"h": 30}], core.SQL_CHECK_CORRECTED)


async def test_arbiter_corrected_query_cannot_write(db):
    """Lecture seule : une requête d'écriture proposée par l'arbitre n'est jamais exécutée."""
    db["rows"][SQL_B] = [{"total": 99}]
    llm = fake_llm(arbitration=Arbitration("C", sql="UPDATE seances SET duree_seance = 0"))
    result = await core.ask_database_checked("Q ?", llm)
    assert result.status == core.SQL_CHECK_AMBIGUOUS
    assert not any("UPDATE" in sql for sql in db["executed"])


async def test_ambiguous_question_asks_for_clarification(db):
    db["rows"][SQL_B] = [{"total": 30}]
    llm = fake_llm(arbitration=Arbitration("ambigu", reason="TP seuls ou TP + SAÉ ?", clarification="Voulez-vous seulement les TP, ou aussi les SAÉ ?"))
    result = await core.ask_database_checked("Q ?", llm)
    assert result.status == core.SQL_CHECK_AMBIGUOUS
    assert result.clarification == "Voulez-vous seulement les TP, ou aussi les SAÉ ?"
    assert result.sql == SQL_A  # on montre quand même une interprétation


async def test_arbiter_failure_keeps_a_with_warning(db):
    db["rows"][SQL_B] = [{"total": 30}]
    llm = fake_llm()
    llm.arbitrate_sql = AsyncMock(side_effect=OllamaResponseError("illisible"))
    result = await core.ask_database_checked("Q ?", llm)
    assert (result.sql, result.status) == (SQL_A, core.SQL_CHECK_UNRESOLVED)


async def test_failed_query_is_repaired_with_the_error_message(db):
    llm = fake_llm(sql_b="SELECT x FROM details", repaired=SQL_B)
    result = await core.ask_database_checked("Q ?", llm)
    assert result.status == core.SQL_CHECK_CONCORDANT
    question, schema, failed_sql, error = llm.repair_sql.call_args.args
    assert failed_sql == "SELECT x FROM details" and "Unknown column" in error


async def test_write_query_is_never_executed_and_gets_repaired(db):
    llm = fake_llm(sql_b="DELETE FROM seances", repaired=SQL_B)
    result = await core.ask_database_checked("Q ?", llm)
    assert result.status == core.SQL_CHECK_CONCORDANT
    assert "DELETE FROM seances" not in db["executed"]
    assert "SELECT ou WITH" in llm.repair_sql.call_args.args[3]


async def test_only_one_valid_query_is_returned_as_not_checked(db):
    llm = fake_llm(sql_b="DROP TABLE cours", repaired="DROP TABLE cours")
    result = await core.ask_database_checked("Q ?", llm)
    assert (result.sql, result.status) == (SQL_A, core.SQL_CHECK_SINGLE)
    assert not any("DROP" in sql for sql in db["executed"])


async def test_both_queries_failing_raises(db):
    llm = fake_llm(sql_a="DROP TABLE cours", sql_b="DROP TABLE cours", repaired="DROP TABLE cours")
    with pytest.raises(ValueError):
        await core.ask_database_checked("Q ?", llm)
    assert db["executed"] == []


async def test_empty_question_is_rejected():
    with pytest.raises(ValueError):
        await core.ask_database_checked("   ", fake_llm())


# -- Prompts envoyés à Ollama --------------------------------------------------------------


@pytest.fixture
def client(fake_ollama):
    fake, url = fake_ollama
    fake.responder = lambda body: (200, {"response": "SELECT 1"})
    return fake, LLMClient(AsyncOllamaClient(base_url=url, model="test-model"))


def test_query_b_uses_a_different_system_prompt():
    assert SQL_VALUES_SYSTEM_PROMPT != SQL_SYSTEM_PROMPT
    assert "valeurs reelles" in SQL_VALUES_SYSTEM_PROMPT
    assert "jamais son contenu" not in SQL_VALUES_SYSTEM_PROMPT
    assert "INSERT, UPDATE, DELETE" in SQL_VALUES_SYSTEM_PROMPT  # les interdits restent


async def test_query_a_prompt_has_no_real_values(client):
    fake, llm = client
    await llm.generate_sql("Heures de Buret ?", "TABLE details: nom_ens varchar")
    body = fake.requests[0]
    assert body["system"] == SQL_SYSTEM_PROMPT and "Aurélien" not in body["prompt"]


async def test_query_b_prompt_contains_the_matched_values(client):
    fake, llm = client
    await llm.generate_sql_with_values("Heures de Buret ?", "TABLE details: nom_ens varchar", HINTS)
    body = fake.requests[0]
    assert body["system"] == SQL_VALUES_SYSTEM_PROMPT
    assert json.dumps(HINTS, ensure_ascii=False) in body["prompt"]
    assert body["options"]["temperature"] > 0  # diversité par rapport à A
    assert body["prompt"].endswith("Question:\nHeures de Buret ?")


async def test_query_b_prompt_without_values(client):
    fake, llm = client
    await llm.generate_sql_with_values("Combien de cours ?", "schema", [])
    assert "Aucune valeur reelle correspondante" in fake.requests[0]["prompt"]


async def test_repair_prompt_contains_failed_sql_and_error(client):
    fake, llm = client
    await llm.repair_sql("Q ?", "schema", "SELECT x FROM t", "Unknown column 'x'")
    prompt = fake.requests[0]["prompt"]
    assert "SELECT x FROM t" in prompt and "Unknown column 'x'" in prompt


async def test_arbiter_receives_both_queries_with_a_limited_preview(client):
    fake, llm = client
    fake.responder = lambda body: (200, {"response": '{"choix": "B", "sql": "", "raison": "ok", "question_precision": ""}'})
    rows_b = [{"n": i} for i in range(25)]
    verdict = await llm.arbitrate_sql("Q ?", "schema", HINTS, (SQL_A, [{"h": 1}]), (SQL_B, rows_b))
    assert verdict == Arbitration("B", reason="ok")
    body = fake.requests[0]
    assert body["system"] == ARBITER_SYSTEM_PROMPT and body["format"] == "json"
    data = json.loads(body["prompt"].split("Donnees (JSON):\n", 1)[1])
    assert data["requete_A_structure_seule"]["sql"] == SQL_A
    assert data["requete_B_avec_valeurs"]["nombre_de_lignes"] == 25
    assert len(data["requete_B_avec_valeurs"]["apercu_des_resultats"]) == ARBITER_PREVIEW_ROWS


@pytest.mark.parametrize("text", ["pas du json", '{"choix": "D"}', '{"raison": "x"}', ""])
def test_unreadable_arbitration_raises(text):
    with pytest.raises(OllamaResponseError):
        _parse_arbitration(text)


def test_arbitration_strips_markdown_from_corrected_sql():
    verdict = _parse_arbitration('{"choix": "C", "sql": "```sql\\nSELECT 1\\n```", "raison": "r"}')
    assert verdict == Arbitration("C", sql="SELECT 1", reason="r")


# -- Affichage ---------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        (core.SQL_CHECK_CONCORDANT, "deux requêtes écrites indépendamment donnent le même résultat"),
        (core.SQL_CHECK_ARBITRATED, "la plus juste a été retenue"),
        (core.SQL_CHECK_CORRECTED, "Requête corrigée"),
        (core.SQL_CHECK_SINGLE, "Requête non contrôlée"),
        (core.SQL_CHECK_UNRESOLVED, "le contrôle n'a pas pu trancher"),
    ],
)
def test_check_note_per_status(status, expected):
    assert expected in ui_gradio._sql_check_note(core.CheckedQuery("SELECT 1", [], status))


def test_ambiguous_note_comes_before_the_summary_and_is_escaped():
    check = core.CheckedQuery("SELECT 1", [{"n": 1}], core.SQL_CHECK_AMBIGUOUS, clarification="TP <b>seuls</b> ?")
    md = ui_gradio._format_bot_response("SELECT 1", [{"n": 1}], summary="La synthèse.", sql_check=check)
    assert md.index("plusieurs façons") < md.index("La synthèse.")
    assert "&lt;b&gt;seuls&lt;/b&gt;" in md and "<b>seuls</b>" not in md


def test_no_note_without_check():
    assert ui_gradio._sql_check_note(None) is None
