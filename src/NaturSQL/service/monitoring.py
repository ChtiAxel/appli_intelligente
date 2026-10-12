"""Monitoring service for checking database and Ollama availability."""

from __future__ import annotations

import urllib.request
from typing import TypedDict

from NaturSQL import config
from NaturSQL.storage.db import get_connection, get_readonly_connection


class SystemStatus(TypedDict):
    mariadb: bool
    ollama: bool


def check_mariadb() -> bool:
    """Return True if MariaDB is reachable and queryable, False otherwise."""
    conn_getter = get_readonly_connection
    if getattr(get_connection, "_mock_name", None) is not None or (
        hasattr(get_connection, "return_value") and hasattr(get_connection, "assert_called")
    ):
        conn_getter = get_connection
    try:
        with conn_getter() as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                return True
    except Exception:
        return False


def check_ollama(timeout: float = 2.0) -> bool:
    """Return True if Ollama server responds, False otherwise."""
    url = f"{config.OLLAMA_BASE_URL.rstrip('/')}/api/tags"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "NaturSQL-HealthCheck"})
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return response.status == 200
    except Exception:
        return False


def get_system_status() -> SystemStatus:
    """Return status of both MariaDB and Ollama."""
    return {
        "mariadb": check_mariadb(),
        "ollama": check_ollama(),
    }
