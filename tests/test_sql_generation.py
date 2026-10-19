"""Regression tests for empty SQL and unlimited SQL generation."""
from unittest.mock import AsyncMock, Mock

import pytest

from NaturSQL.ollama_client.async_client import AsyncOllamaClient
from NaturSQL.ollama_client.llm import LLMClient
from NaturSQL.ollama_client.ollama_wrapper_iut import OllamaResponseError
from NaturSQL.service import core

QUESTION = "quels sont les professeurs qui s'appelle Rémi ?"
SQL = "SELECT DISTINCT nom_ens, prenom_ens FROM enseignants WHERE prenom_ens = 'Rémi'"


async def test_sql_generation_has_no_token_cap_and_disables_thinking(fake_ollama):
    fake, url = fake_ollama
    fake.responder = lambda body: (200, {"response": SQL})
    llm = LLMClient(AsyncOllamaClient(base_url=url, model="test-model"))
    assert await llm.generate_sql(QUESTION, "TABLE enseignants: nom_ens varchar, prenom_ens varchar") == SQL
    assert fake.requests[0]["options"]["num_predict"] == -1
    assert fake.requests[0]["think"] is False
    assert QUESTION in fake.requests[0]["prompt"]


@pytest.mark.parametrize("empty", ["", "   ", "```sql\n\n```"])
async def test_empty_sql_is_retried_once(empty):
    client = Mock()
    client.generate = AsyncMock(side_effect=[empty, SQL])
    assert await LLMClient(client).generate_sql(QUESTION, "schema") == SQL
    assert client.generate.await_count == 2


async def test_repeated_empty_sql_has_clear_error_and_never_queries_db(monkeypatch):
    client = Mock()
    client.generate = AsyncMock(return_value="")
    schema = Mock(return_value="schema")
    execute = Mock()
    monkeypatch.setattr(core, "database_schema", schema)
    monkeypatch.setattr(core, "execute_query", execute)
    with pytest.raises(OllamaResponseError, match="aucune requête SQL après deux tentatives"):
        await core.ask_database(QUESTION, LLMClient(client))
    assert client.generate.await_count == 2
    execute.assert_not_called()


async def test_truncated_sql_is_not_executed(fake_ollama, monkeypatch):
    fake, url = fake_ollama
    fake.responder = lambda body: (200, {"response": "SELECT DISTINCT", "done_reason": "length"})
    execute = Mock()
    monkeypatch.setattr(core, "database_schema", lambda: "schema")
    monkeypatch.setattr(core, "execute_query", execute)
    llm = LLMClient(AsyncOllamaClient(base_url=url, model="test-model"))
    with pytest.raises(OllamaResponseError, match="interrompue"):
        await core.ask_database(QUESTION, llm)
    execute.assert_not_called()
