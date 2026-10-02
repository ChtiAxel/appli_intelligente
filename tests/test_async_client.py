"""Tests du client Ollama asynchrone (R1)."""

from __future__ import annotations

import asyncio
import socket
import time

import pytest

from NaturSQL import config
from NaturSQL.ollama_client.async_client import AsyncOllamaClient
from NaturSQL.ollama_client.ollama_wrapper_iut import (
    OllamaConnectionError,
    OllamaResponseError,
)


def test_client_reads_settings_from_config(monkeypatch):
    monkeypatch.setattr(config, "OLLAMA_BASE_URL", "http://ollama.example:1234/")
    monkeypatch.setattr(config, "OLLAMA_MODEL", "mistral")
    monkeypatch.setattr(config, "OLLAMA_TIMEOUT_SECONDS", 12.0)

    client = AsyncOllamaClient()

    assert client.base_url == "http://ollama.example:1234"
    assert client.model == "mistral"
    assert client.timeout_s == 12.0


async def test_generate_posts_expected_payload(fake_ollama):
    fake, url = fake_ollama
    fake.responder = lambda body: (200, {"response": "Bonjour"})
    client = AsyncOllamaClient(base_url=url, model="llama3.2")

    text = await client.generate("Salut", system="sys", options={"temperature": 0})

    assert text == "Bonjour"
    assert fake.requests == [
        {
            "model": "llama3.2",
            "prompt": "Salut",
            "stream": False,
            "system": "sys",
            "options": {"temperature": 0},
        }
    ]


async def test_generate_raises_on_http_error(fake_ollama):
    fake, url = fake_ollama
    fake.responder = lambda body: (500, {"error": "model not found"})

    with pytest.raises(OllamaResponseError, match="500"):
        await AsyncOllamaClient(base_url=url).generate("x")


async def test_generate_raises_on_unexpected_payload(fake_ollama):
    fake, url = fake_ollama
    fake.responder = lambda body: (200, {"pas_de_response": True})

    with pytest.raises(OllamaResponseError):
        await AsyncOllamaClient(base_url=url).generate("x")


async def test_generate_raises_connection_error_when_server_down():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    # Le port est libéré : plus rien n'écoute dessus.
    client = AsyncOllamaClient(base_url=f"http://127.0.0.1:{port}", timeout_s=2)

    with pytest.raises(OllamaConnectionError):
        await client.generate("x")


async def test_calls_do_not_block_each_other(fake_ollama):
    """Deux appels concurrents de 0.5 s doivent se chevaucher (non bloquant)."""
    fake, url = fake_ollama
    fake.delay_s = 0.5
    client = AsyncOllamaClient(base_url=url)

    start = time.perf_counter()
    results = await asyncio.gather(client.generate("a"), client.generate("b"))
    elapsed = time.perf_counter() - start

    assert results == ["ok", "ok"]
    assert elapsed < 0.9
