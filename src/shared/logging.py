"""Shared logging configuration."""

import logging


def get_logger(name: str) -> logging.Logger:
    """Return a logger using the application-wide naming convention."""
    return logging.getLogger(f"natur_sql.{name}")
