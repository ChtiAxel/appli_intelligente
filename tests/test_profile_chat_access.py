"""Regression tests for profile navigation and equal chat access."""
from unittest.mock import AsyncMock, patch

import pytest

from NaturSQL.storage.users import User
from NaturSQL.ui_gradio import build_app


@pytest.fixture
def application():
    with patch("NaturSQL.ui_gradio.AuthService"), patch("NaturSQL.ui_gradio.ConversationStorage") as storage:
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
    with patch("NaturSQL.ui_gradio.ask_database", new_callable=AsyncMock) as ask:
        ask.return_value = ("SELECT COUNT(*) AS nombre FROM cours", [{"nombre": 2}])
        replies = [reply async for reply in event.fn(user, history, 1, {})]
    ask.assert_awaited_once_with("Combien de cours ?")
    assert replies[-1][0][-1]["role"] == "assistant"
    assert "Erreur" not in replies[-1][0][-1]["content"]
