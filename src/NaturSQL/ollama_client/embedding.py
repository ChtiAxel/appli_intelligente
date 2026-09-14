"""Embedding model adapter."""

from .ollama_wrapper_iut import OllamaWrapper


class EmbeddingClient:
    """Application-facing adapter for embeddings."""

    def __init__(self, client: OllamaWrapper | None = None) -> None:
        self.client = client or OllamaWrapper()
