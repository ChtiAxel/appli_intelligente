"""Monitoring service for checking database and Ollama availability."""

from __future__ import annotations

import urllib.request
from typing import TypedDict

from NaturSQL import config
from NaturSQL.storage.db import get_connection, get_query_connection


class SystemStatus(TypedDict):
    mariadb: bool
    mariadb_queries: bool
    ollama: bool


def check_mariadb() -> bool:
    """Return True if MariaDB is reachable and queryable, False otherwise."""
    try:
        with get_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                return True
    except Exception:
        return False


def check_query_access() -> bool:
    """Check the real query account and a pedagogical view, independently of liveness."""
    try:
        with get_query_connection(timeout=config.DB_QUERY_TIMEOUT) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1 FROM details LIMIT 0")
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
    mariadb = check_mariadb()
    return {
        "mariadb": mariadb,
        "mariadb_queries": check_query_access() if mariadb else False,
        "ollama": check_ollama(),
    }
