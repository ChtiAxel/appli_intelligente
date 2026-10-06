"""Tests du pipeline asynchrone Text-to-SQL (R2).

Ollama est simulé par le faux serveur de conftest.py ; la base de données
est remplacée par des fonctions factices (monkeypatch).
"""

from __future__ import annotations

import threading

import pytest

from NaturSQL.ollama_client.async_client import AsyncOllamaClient
from NaturSQL.ollama_client.llm import SQL_SYSTEM_PROMPT, LLMClient
from NaturSQL.service import core

SCHEMA = "TABLE details: nom_ens varchar, prenom_ens varchar, type_seance varchar"
QUESTION = "Quels enseignants donnent des TP ?"
GENERATED_SQL = "SELECT DISTINCT nom_ens, prenom_ens FROM details WHERE type_seance LIKE 'TP%'"
ROWS = [{"nom_ens": "Buret", "prenom_ens": "Aurélien"}]


def sql_responder(sql: str = GENERATED_SQL):
    """Répond la requête `sql` au prompt Text-to-SQL."""

    def respond(body: dict) -> tuple[int, dict]:
        if body.get("system") == SQL_SYSTEM_PROMPT:
            return 200, {"response": sql}
        return 400, {"error": "prompt inconnu"}

    return respond


@pytest.fixture
def llm(fake_ollama):
    fake, url = fake_ollama
    fake.responder = sql_responder()
    return LLMClient(AsyncOllamaClient(base_url=url, model="test-model"))


@pytest.fixture
def fake_db(monkeypatch):
    """Remplace l'accès MariaDB et enregistre les requêtes exécutées."""
    state = {"executed": [], "threads": []}

    def fake_schema() -> str:
        state["threads"].append(threading.get_ident())
        return SCHEMA

    def fake_execute(sql: str) -> list[dict]:
        state["threads"].append(threading.get_ident())
        state["executed"].append(sql)
        return ROWS

    monkeypatch.setattr(core, "database_schema", fake_schema)
    monkeypatch.setattr(core, "execute_query", fake_execute)
    return state


# -- Text-to-SQL ---------------------------------------------------


async def test_sql_prompt_contains_schema_and_question(fake_ollama, llm):
    fake, _ = fake_ollama

    sql = await llm.generate_sql(QUESTION, SCHEMA)

    assert sql == GENERATED_SQL
    body = fake.requests[0]
    assert body["system"] == SQL_SYSTEM_PROMPT
    assert SCHEMA in body["prompt"]
    assert QUESTION in body["prompt"]
    assert body["model"] == "test-model"
    assert body["options"] == {"temperature": 0}


async def test_sql_markdown_fence_is_stripped(fake_ollama, llm):
    fake, _ = fake_ollama
    fake.responder = sql_responder(sql=f"```sql\n{GENERATED_SQL}\n```")

    assert await llm.generate_sql(QUESTION, SCHEMA) == GENERATED_SQL


async def test_text_to_sql_injects_db_schema(fake_ollama, llm, fake_db):
    fake, _ = fake_ollama

    sql = await core.text_to_sql(QUESTION, llm)

    assert sql == GENERATED_SQL
    assert SCHEMA in fake.requests[0]["prompt"]


# -- Pipeline complet ---------------------------------------------------------


async def test_pipeline_end_to_end(fake_ollama, llm, fake_db):
    fake, _ = fake_ollama

    sql, rows = await core.ask_database(f"  {QUESTION}  ", llm)

    assert (sql, rows) == (GENERATED_SQL, ROWS)
    assert fake_db["executed"] == [GENERATED_SQL]
    assert len(fake.requests) == 1
    assert QUESTION in fake.requests[0]["prompt"]


async def test_pipeline_runs_db_calls_outside_event_loop_thread(llm, fake_db):
    await core.ask_database(QUESTION, llm)

    loop_thread = threading.get_ident()
    assert fake_db["threads"]
    assert all(t != loop_thread for t in fake_db["threads"])


async def test_pipeline_rejects_unsafe_sql(fake_ollama, llm, fake_db):
    fake, _ = fake_ollama
    fake.responder = sql_responder(sql="DELETE FROM enseignants")

    with pytest.raises(ValueError, match="SELECT ou WITH"):
        await core.ask_database(QUESTION, llm)

    assert fake_db["executed"] == []


async def test_pipeline_rejects_empty_question(llm, fake_db):
    with pytest.raises(ValueError, match="vide"):
        await core.ask_database("   ", llm)
