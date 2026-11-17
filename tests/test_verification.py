"""Contexte limité au schéma et étape de vérification de la réponse."""
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from NaturSQL.ollama_client.async_client import AsyncOllamaClient
from NaturSQL.ollama_client.llm import (
    SQL_FEW_SHOTS,
    SQL_SYSTEM_PROMPT,
    VERIFY_SYSTEM_PROMPT,
    LLMClient,
    Verification,
)
from NaturSQL.ollama_client.ollama_wrapper_iut import OllamaResponseError
from NaturSQL.service import core
from NaturSQL import ui_gradio

QUESTION = "Combien de cours ?"
ROWS = [{"nombre": 2}]


# -- Contexte de génération SQL : structure seule ----------------------


def test_sql_prompt_contains_no_real_data_values():
    # Anciennes valeurs réelles de la base qui figuraient dans le prompt.
    for value in ("Aurélien", "Buret", "Virtualisation avancée", "Qualité de développement", "TPA", "TPE"):
        assert value not in SQL_SYSTEM_PROMPT
        assert value not in SQL_FEW_SHOTS


async def test_generate_sql_sends_only_schema_and_question():
    client = Mock()
    client.generate = AsyncMock(return_value="SELECT 1")
    schema = "TABLE cours [cle primaire: id_cours]: id_cours varchar"
    await LLMClient(client).generate_sql(QUESTION, schema)
    prompt = client.generate.call_args.args[0]
    assert prompt.startswith(f"Schema autorise:\n{schema}\n\n")
    assert prompt.endswith(f"Question:\n{QUESTION}")


# -- Vérificateur ------------------------------------------------------


async def test_verify_answer_sends_question_answer_and_raw_rows(fake_ollama):
    fake, url = fake_ollama
    fake.responder = lambda body: (200, {"response": '{"coherent": true, "probleme": ""}'})
    llm = LLMClient(AsyncOllamaClient(base_url=url, model="test-model"))
    verdict = await llm.verify_answer(QUESTION, "Il y a 2 cours.", ROWS)
    assert verdict == Verification(True, "")
    body = fake.requests[0]
    assert body["system"] == VERIFY_SYSTEM_PROMPT
    assert body["format"] == "json"
    assert body["think"] is False
    payload = json.loads(body["prompt"])
    assert payload["question"] == QUESTION
    assert payload["reponse_a_verifier"] == "Il y a 2 cours."
    assert payload["resultats"] == ROWS


@pytest.mark.parametrize(
    "raw, expected",
    [
        ('{"coherent": false, "probleme": "3 au lieu de 2"}', Verification(False, "3 au lieu de 2")),
        ('```json\n{"coherent": true}\n```', Verification(True, "")),
        ('Verdict : {"coherent": true, "probleme": ""}', Verification(True, "")),
    ],
)
async def test_verify_answer_parses_verdict(raw, expected):
    client = Mock()
    client.generate = AsyncMock(return_value=raw)
    assert await LLMClient(client).verify_answer(QUESTION, "x", ROWS) == expected


@pytest.mark.parametrize("raw", ["", "oui", '{"coherent": "oui"}', "{pas du json}"])
async def test_unreadable_verdict_raises(raw):
    client = Mock()
    client.generate = AsyncMock(return_value=raw)
    with pytest.raises(OllamaResponseError, match="illisible"):
        await LLMClient(client).verify_answer(QUESTION, "x", ROWS)


async def test_correction_is_passed_to_new_summary():
    client = Mock()
    client.generate = AsyncMock(return_value="Il y a 2 cours.")
    await LLMClient(client).summarize_results(QUESTION, ROWS, correction="3 au lieu de 2")
    payload = json.loads(client.generate.call_args.args[0])
    assert "3 au lieu de 2" in payload["correction_demandee"]


# -- Orchestration summarize_and_verify -------------------------------


def _llm(summaries, verdicts):
    llm = Mock()
    llm.summarize_results = AsyncMock(side_effect=summaries)
    llm.verify_answer = AsyncMock(side_effect=verdicts)
    return llm


async def test_coherent_answer_is_kept():
    llm = _llm(["Il y a 2 cours."], [Verification(True)])
    answer = await core.summarize_and_verify(QUESTION, ROWS, llm)
    assert (answer.summary, answer.status) == ("Il y a 2 cours.", core.VERIFICATION_OK)
    llm.verify_answer.assert_awaited_once_with(QUESTION, "Il y a 2 cours.", ROWS)


async def test_incoherent_answer_is_regenerated_once_and_reverified():
    llm = _llm(["Il y a 3 cours.", "Il y a 2 cours."], [Verification(False, "3 au lieu de 2"), Verification(True)])
    answer = await core.summarize_and_verify(QUESTION, ROWS, llm)
    assert answer.summary == "Il y a 2 cours."
    assert answer.status == core.VERIFICATION_CORRECTED
    assert llm.summarize_results.await_args_list[1].kwargs == {"correction": "3 au lieu de 2"}
    assert llm.verify_answer.await_args_list[1].args == (QUESTION, "Il y a 2 cours.", ROWS)


async def test_still_incoherent_answer_is_flagged():
    llm = _llm(["A", "B"], [Verification(False, "p1"), Verification(False, "p2")])
    answer = await core.summarize_and_verify(QUESTION, ROWS, llm)
    assert (answer.summary, answer.status, answer.detail) == ("B", core.VERIFICATION_FAILED, "p2")
    assert llm.summarize_results.await_count == 2  # pas de boucle infinie


async def test_verifier_failure_keeps_summary_as_unverified():
    llm = _llm(["Il y a 2 cours."], OllamaResponseError("illisible"))
    answer = await core.summarize_and_verify(QUESTION, ROWS, llm)
    assert (answer.summary, answer.status) == ("Il y a 2 cours.", core.VERIFICATION_UNAVAILABLE)


async def test_empty_results_skip_verification():
    llm = _llm(["Aucun résultat."], [])
    answer = await core.summarize_and_verify(QUESTION, [], llm)
    assert answer.status is None
    llm.verify_answer.assert_not_awaited()


async def test_summary_failure_propagates():
    llm = _llm(RuntimeError("Ollama indisponible"), [])
    with pytest.raises(RuntimeError):
        await core.summarize_and_verify(QUESTION, ROWS, llm)


# -- Affichage ---------------------------------------------------------


@pytest.mark.parametrize(
    "status, expected",
    [
        (core.VERIFICATION_OK, "Réponse vérifiée"),
        (core.VERIFICATION_CORRECTED, "après correction"),
        (core.VERIFICATION_FAILED, "incohérence possible"),
        (core.VERIFICATION_UNAVAILABLE, "Vérification de la réponse indisponible"),
    ],
)
def test_verification_note_is_displayed(status, expected):
    verification = core.VerifiedAnswer("Synthèse.", status, "<b>détail</b>")
    md = ui_gradio._format_bot_response("SELECT 1", ROWS, summary="Synthèse.", verification=verification)
    assert expected in md
    assert "<b>" not in md  # le détail du vérificateur est échappé


def test_no_note_without_verification():
    md = ui_gradio._format_bot_response("SELECT 1", ROWS, summary="Synthèse.")
    assert "vérifiée" not in md and "Vérification" not in md
