"""Common client protocol for language-model adapters."""

from typing import Protocol


class ModelClient(Protocol):
    """Minimal interface exposed to the service layer."""

    def generate(self, prompt: str) -> str:
        """Generate text from a prompt."""
        ...
