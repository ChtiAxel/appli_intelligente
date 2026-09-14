"""Vision-language model adapter."""

from .ollama_wrapper_iut import OllamaWrapper


class VLMClient:
    """Application-facing adapter for multimodal Ollama calls."""

    def __init__(self, client: OllamaWrapper | None = None) -> None:
        self.client = client or OllamaWrapper()
