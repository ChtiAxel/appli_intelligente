"""Database and vector-store access primitives."""


class Storage:
    """Base storage placeholder for the application persistence layer."""

    def health_check(self) -> bool:
        """Return whether the storage backend is available."""
        return True
