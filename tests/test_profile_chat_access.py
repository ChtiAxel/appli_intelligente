"""Regression tests for profile navigation and equal chat access."""
from unittest.mock import AsyncMock, patch

import pytest

from NaturSQL.storage.users import User
from NaturSQL.ui_gradio import build_app


@pytest.fixture(scope="module")
def application():
    with patch("NaturSQL.ui_gradio.AuthService"), patch("NaturSQL.ui_gradio.ConversationStorage") as storage, patch("NaturSQL.ui_gradio.get_system_status", return_value={"mariadb": True, "ollama": True}):
        storage.return_value.list_conversations.return_value = []
        storage.return_value.get_user_activity_stats.return_value = {}
        yield build_app()


def callback(application, name):
    return next(f for f in application.fns.values() if f.fn and f.fn.__name__ == name)


def test_profile_navigation_and_disconnect_output_counts(application):
    for name, args in (
        ("go_to_profile_view", [None]),
        ("go_to_profile_view", [User("Jean", "Dupont", "hash")]),
        ("do_disconnect", []),
    ):
        event = callback(application, name)
        assert len(event.fn(*args)) == len(event.outputs)


@pytest.mark.parametrize("role", ["PROF", "SECRETAIRE", "ADMIN", "OTHER"])
@pytest.mark.parametrize("mode", ["Avec SQL", "Sans SQL"])
async def test_every_authenticated_profile_can_ask_questions(application, role, mode):
    user = User("Jean", "Dupont", "hash", role=role)
    history = [{"role": "user", "content": "Combien de cours ?"}]
    event = callback(application, "bot_respond")
    summary = "La base contient 2 cours."
    with patch("NaturSQL.ui_gradio.ask_database", new_callable=AsyncMock) as ask, patch("NaturSQL.ui_gradio.LLMClient") as llm:
        ask.return_value = ("SELECT COUNT(*) AS nombre FROM cours", [{"nombre": 2}])
        llm.return_value.summarize_results = AsyncMock(return_value=summary)
        replies = [reply async for reply in event.fn(user, history, 1, {}, mode)]
    ask.assert_awaited_once_with("Combien de cours ?")
    llm.return_value.summarize_results.assert_awaited_once_with("Combien de cours ?", [{"nombre": 2}])
    assert replies[-1][0][-1]["role"] == "assistant"
    content = replies[-1][0][-1]["content"]
    assert summary in content
    assert "| Nombre |" in content
    assert ("```sql" in content) == (mode == "Avec SQL")
    assert "Erreur" not in content


async def test_summary_failure_preserves_query_results(application):
    user = User("Jean", "Dupont", "hash")
    history = [{"role": "user", "content": "Combien de cours ?"}]
    event = callback(application, "bot_respond")
    with patch("NaturSQL.ui_gradio.ask_database", new_callable=AsyncMock) as ask, patch("NaturSQL.ui_gradio.LLMClient") as llm:
        ask.return_value = ("SELECT COUNT(*) AS nombre FROM cours", [{"nombre": 2}])
        llm.return_value.summarize_results = AsyncMock(side_effect=RuntimeError("Ollama indisponible"))
        replies = [reply async for reply in event.fn(user, history, 1, {}, "Sans SQL")]
    content = replies[-1][0][-1]["content"]
    assert "synthèse est temporairement indisponible" in content
    assert "| Nombre |" in content
    assert "| 2 |" in content
    ask.assert_awaited_once_with("Combien de cours ?")
