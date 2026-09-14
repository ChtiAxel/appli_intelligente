"""Large language model adapter."""

from .ollama_wrapper_iut import OllamaWrapper


class LLMClient:
    """Small application-facing adapter around the Ollama wrapper."""

    def __init__(self, client: OllamaWrapper | None = None) -> None:
        self.client = client or OllamaWrapper()
