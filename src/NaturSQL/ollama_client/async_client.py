"""Client Ollama asynchrone (aiohttp).

Les appels à /api/generate ne bloquent pas la boucle d'événements :
Gradio peut continuer à servir l'interface pendant que le LLM répond.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any, Mapping, Optional

import aiohttp

from NaturSQL import config

from .ollama_wrapper_iut import OllamaConnectionError, OllamaResponseError


class AsyncOllamaClient:
    """Adaptateur asynchrone minimal autour de POST /api/generate."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        timeout_s: Optional[float] = None,
    ) -> None:
        self.base_url = (base_url or config.OLLAMA_BASE_URL).rstrip("/")
        self.model = model or config.OLLAMA_MODEL
        self.timeout_s = timeout_s if timeout_s is not None else config.OLLAMA_TIMEOUT_SECONDS

    async def generate(
        self,
        prompt: str,
        *,
        system: Optional[str] = None,
        options: Optional[Mapping[str, Any]] = None,
    ) -> str:
        """Envoie un prompt (stream=false) et retourne le texte généré."""
        body: dict[str, Any] = {"model": self.model, "prompt": prompt, "stream": False}
        if system is not None:
            body["system"] = system
        if options is not None:
            body["options"] = dict(options)

        url = f"{self.base_url}/api/generate"
        timeout = aiohttp.ClientTimeout(total=self.timeout_s)
        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(url, json=body) as response:
                    status = response.status
                    raw = await response.text()
        except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
            raise OllamaConnectionError(f"Impossible de joindre Ollama à {url} : {exc}") from exc

        if status != 200:
            raise OllamaResponseError(f"Ollama a répondu {status} sur {url} : {raw[:200]!r}")
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise OllamaResponseError(f"Réponse non-JSON depuis {url} : {raw[:200]!r}") from exc

        text = payload.get("response") if isinstance(payload, dict) else None
        if not isinstance(text, str):
            raise OllamaResponseError(f"Réponse /api/generate inattendue : {payload!r}")
        return text
