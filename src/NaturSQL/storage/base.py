"""Database and vector-store access primitives."""

import pymysql
from ..config import settings

class Storage:
    """Base storage placeholder for the application persistence layer."""
    
    def __init__(self):
        self._get_connection = lambda: pymysql.connect(
            host=settings.db_host,
            port=settings.db_port,
            user=settings.db_user,
            password=settings.db_password,
            database=settings.db_name,
            cursorclass=pymysql.cursors.DictCursor
        )

    def health_check(self) -> bool:
        """Return whether the storage backend is available."""
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("SELECT 1")
            return True
        except Exception:
            return False
            
    def get_user_by_email(self, email: str) -> dict:
        """Fetch a user (enseignant) from DB using email."""
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cursor:
                    sql = "SELECT id_ens, nom_ens, prenom_ens, mail_ens FROM enseignants WHERE mail_ens = %s"
                    cursor.execute(sql, (email,))
                    user = cursor.fetchone()
                    if user:
                        return user
            return None
        except Exception as e:
            print(f"Database error: {e}")
            return None
            
    def get_first_user(self) -> dict:
        """Fetch the first user (enseignant) from DB for profile visualization demo."""
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cursor:
                    sql = "SELECT id_ens, nom_ens, prenom_ens, mail_ens FROM enseignants LIMIT 1"
                    cursor.execute(sql)
                    user = cursor.fetchone()
                    if user:
                        return user
            return None
        except Exception as e:
            print(f"Database error: {e}")
            return None
