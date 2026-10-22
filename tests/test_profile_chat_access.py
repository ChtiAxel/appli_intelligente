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
async def test_every_authenticated_profile_can_ask_questions(application, role):
    user = User("Jean", "Dupont", "hash", role=role)
    history = [{"role": "user", "content": "Combien de cours ?"}]
    event = callback(application, "bot_respond")
    summary = "La base contient 2 cours."
    with patch("NaturSQL.ui_gradio.ask_database", new_callable=AsyncMock) as ask, patch("NaturSQL.ui_gradio.LLMClient") as llm:
        ask.return_value = ("SELECT COUNT(*) AS nombre FROM cours", [{"nombre": 2}])
        llm.return_value.summarize_results = AsyncMock(return_value=summary)
        replies = [reply async for reply in event.fn(user, history, 1)]
    ask.assert_awaited_once_with("Combien de cours ?")
    llm.return_value.summarize_results.assert_awaited_once_with("Combien de cours ?", [{"nombre": 2}])
    assert replies[-1][0][-1]["role"] == "assistant"
    content = replies[-1][0][-1]["content"]
    assert summary in content
    assert "| Nombre |" in content
    # Le SQL est toujours enregistré : le mode « Sans SQL » le masque à l'affichage (CSS).
    assert "```sql" in content
    assert "Erreur" not in content


async def test_summary_failure_preserves_query_results(application):
    user = User("Jean", "Dupont", "hash")
    history = [{"role": "user", "content": "Combien de cours ?"}]
    event = callback(application, "bot_respond")
    with patch("NaturSQL.ui_gradio.ask_database", new_callable=AsyncMock) as ask, patch("NaturSQL.ui_gradio.LLMClient") as llm:
        ask.return_value = ("SELECT COUNT(*) AS nombre FROM cours", [{"nombre": 2}])
        llm.return_value.summarize_results = AsyncMock(side_effect=RuntimeError("Ollama indisponible"))
        replies = [reply async for reply in event.fn(user, history, 1)]
    content = replies[-1][0][-1]["content"]
    assert "synthèse est temporairement indisponible" in content
    assert "| Nombre |" in content
    assert "| 2 |" in content
    ask.assert_awaited_once_with("Combien de cours ?")


# --- Correctif visuel et historique (discussion, historique, bascule SQL) ---

import json
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import MagicMock

import gradio as gr

from NaturSQL import ui_gradio


@pytest.fixture
def app_and_storage():
    with patch("NaturSQL.ui_gradio.AuthService"), patch("NaturSQL.ui_gradio.ConversationStorage") as storage_cls, patch("NaturSQL.ui_gradio.get_system_status", return_value={"mariadb": True, "ollama": True}):
        storage = storage_cls.return_value
        storage.list_conversations.return_value = []
        storage.get_user_activity_stats.return_value = {}
        yield build_app(), storage


def _conv(cid, title):
    return SimpleNamespace(id=cid, title=title, created_at=datetime.now())


def test_conv_list_html_escapes_titles_and_marks_active():
    html_out = ui_gradio._conv_list_html([_conv(1, "<script>alert(1)</script>"), _conv(2, "Cours")], active_cid=2)
    assert "<script>" not in html_out
    assert "&lt;script&gt;" in html_out
    assert 'class="conv-item active" data-cid="2"' in html_out
    assert "Aucune discussion" in ui_gradio._conv_list_html([])


def test_add_user_msg_blocks_second_question_while_answer_pending(application):
    event = callback(application, "add_user_msg")
    _, history = event.fn("Première question", [])
    assert ui_gradio._is_typing(history[-1])
    with pytest.raises(gr.Error):
        event.fn("Deuxième question", history)
    with pytest.raises(gr.Error):
        event.fn("   ", [])


async def test_late_answer_does_not_overwrite_new_conversation(app_and_storage):
    """Bug « + » : la réponse d'une ancienne discussion ne doit pas écraser l'écran."""
    app, storage = app_and_storage
    request = SimpleNamespace(session_hash="test-late-answer")
    ui_gradio._set_view(request, 1)
    user = User("Jean", "Dupont", "hash")
    history = [{"role": "user", "content": "Ancienne question"}, {"role": "assistant", "content": ui_gradio.TYPING_HTML}]

    async def answer_after_new_conversation(question):
        ui_gradio._set_view(request, None)  # l'utilisateur clique sur « Nouvelle conversation »
        return "SELECT 1", [{"n": 1}]

    event = callback(app, "bot_respond")
    with patch("NaturSQL.ui_gradio.ask_database", side_effect=answer_after_new_conversation), patch("NaturSQL.ui_gradio.LLMClient") as llm:
        llm.return_value.summarize_results = AsyncMock(return_value="Synthèse.")
        replies = [reply async for reply in event.fn(user, history, 1, request)]
    chatbot_update, conv_id_update = replies[-1][0], replies[-1][1]
    assert isinstance(chatbot_update, dict)  # gr.update() : discussion affichée inchangée
    assert isinstance(conv_id_update, dict)
    # La réponse est tout de même enregistrée dans sa conversation d'origine.
    saved = [c.args for c in storage.add_message.call_args_list if c.args[:2] == (1, "assistant")]
    assert saved and saved[-1][3] == "SELECT 1"
    ui_gradio._forget_view(request)


def test_conv_action_refuses_conversation_of_another_user(app_and_storage):
    app, storage = app_and_storage
    storage.list_conversations.return_value = [_conv(7, "À moi")]
    event = callback(app, "do_conv_action")
    user = User("Jean", "Dupont", "hash")
    with patch("NaturSQL.ui_gradio.gr.Warning"):
        event.fn(json.dumps({"action": "delete", "cid": 99}), user, None)
        event.fn(json.dumps({"action": "rename", "cid": 99, "title": "Piratage"}), user, None)
    storage.delete_conversation.assert_not_called()
    storage.rename_conversation.assert_not_called()


def test_conv_action_select_loads_history_with_sql(app_and_storage):
    app, storage = app_and_storage
    storage.list_conversations.return_value = [_conv(7, "Cours")]
    storage.get_messages.return_value = [
        SimpleNamespace(role="user", content="Combien ?", sql_generated=None),
        SimpleNamespace(role="assistant", content="Il y a 2 cours.", sql_generated="SELECT 2"),
    ]
    event = callback(app, "do_conv_action")
    history, cid, list_html, _ = event.fn(json.dumps({"action": "select", "cid": 7}), User("Jean", "Dupont", "hash"), None)
    assert cid == 7
    assert "```sql" in history[1]["content"]  # anciens messages « Sans SQL » : SQL réintégré
    assert 'conv-item active" data-cid="7"' in list_html
