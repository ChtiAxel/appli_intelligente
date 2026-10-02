"""Fixtures communes : un faux serveur Ollama local (aiohttp) pour les tests.

Aucun serveur IA ni base de données réels ne sont nécessaires.
"""

from __future__ import annotations

import asyncio
import os
from typing import Callable

import pytest
from aiohttp import web
from aiohttp.test_utils import TestServer

# config.py exige ces variables à l'import : valeurs factices pour les tests.
os.environ.setdefault("DB_NAME", "test")
os.environ.setdefault("DB_USER", "test")
os.environ.setdefault("DB_PASSWORD", "test")


class FakeOllama:
    """Faux /api/generate : enregistre les requêtes et renvoie une réponse choisie."""

    def __init__(self) -> None:
        self.requests: list[dict] = []
        # responder(body) -> (status, json_payload)
        self.responder: Callable[[dict], tuple[int, dict]] = lambda body: (200, {"response": "ok"})
        self.delay_s: float = 0.0

    async def handle(self, request: web.Request) -> web.Response:
        body = await request.json()
        self.requests.append(body)
        if self.delay_s:
            await asyncio.sleep(self.delay_s)
        status, payload = self.responder(body)
        return web.json_response(payload, status=status)


@pytest.fixture
async def fake_ollama():
    """Démarre le faux serveur et retourne (fake, base_url)."""
    fake = FakeOllama()
    app = web.Application()
    app.router.add_post("/api/generate", fake.handle)
    server = TestServer(app)
    await server.start_server()
    try:
        yield fake, str(server.make_url("")).rstrip("/")
    finally:
        await server.close()
