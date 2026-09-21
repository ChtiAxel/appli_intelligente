"""Low-level MariaDB connection helper for the `appia` database."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

import pymysql
import pymysql.cursors

from NaturSQL import config


def get_connection() -> pymysql.connections.Connection:
    """Open a new connection to the `appia` database."""
    return pymysql.connect(
        host=config.DB_HOST,
        port=config.DB_PORT,
        user=config.DB_USER,
        password=config.DB_PASSWORD,
        database=config.DB_NAME,
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=False,
    )


@contextmanager
def transaction() -> Iterator[pymysql.cursors.DictCursor]:
    """Yield a cursor inside a committed transaction (rolled back on error)."""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            yield cursor
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
