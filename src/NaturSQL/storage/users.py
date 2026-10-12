from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

import pymysql
from werkzeug.security import check_password_hash, generate_password_hash

from . import db

_LEGACY_MD5_RE = re.compile(r"^[0-9a-f]{32}$")


@dataclass
class User:
    """A row from the standalone `compte` table."""

    prenom: str
    nom: str
    mdp: str
    role: str = "PROF"
    created_at: Optional[datetime] = None
    avatar: Optional[str] = None

    @property
    def nom_util(self) -> str:
        return f"{self.nom}.{self.prenom}".lower()
    @property
    def full_name(self) -> str:
        return f"{self.prenom} {self.nom}".strip()


class UserAlreadyExistsError(Exception):
    """Raised when trying to register an identifiant that is already in use."""


class UserStorage:
    """Read/write access to the standalone `compte` table."""

    def ensure_schema(self) -> None:
        """Create the standalone account table if it does not exist, and ensure columns exist."""
        with db.transaction() as cursor:
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS compte (
                    prenom VARCHAR(100) NOT NULL,
                    nom VARCHAR(100) NOT NULL,
                    mdp VARCHAR(255) NOT NULL,
                    role ENUM('PROF', 'SECRETAIRE', 'ADMIN') NOT NULL DEFAULT 'PROF',
                    avatar VARCHAR(255) DEFAULT NULL,
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (prenom, nom)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """
            )
            try:
                cursor.execute(
                    """
                    ALTER TABLE compte
                    ADD COLUMN IF NOT EXISTS role ENUM('PROF', 'SECRETAIRE', 'ADMIN') NOT NULL DEFAULT 'PROF',
                    ADD COLUMN IF NOT EXISTS avatar VARCHAR(255) DEFAULT NULL,
                    ADD COLUMN IF NOT EXISTS created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                    """
                )
            except Exception:
                pass

    # -- lookups ---------------------------------------------------

    def find_by_name(self, first_name: str, last_name: str) -> Optional[User]:
        with db.transaction() as cursor:
            cursor.execute(
                """
                SELECT prenom, nom, mdp, role, created_at, avatar
                FROM compte
                WHERE prenom = %s AND nom = %s
                """,
                (first_name, last_name),
            )
            row = cursor.fetchone()
        return self._row_to_user(row) if row else None

    # -- authentication ---------------------------------------------

    def authenticate(self, first_name: str, last_name: str, password: str) -> Optional[User]:
        with db.transaction() as cursor:
            cursor.execute(
                """
                SELECT prenom, nom, mdp, role, created_at, avatar
                FROM compte
                WHERE prenom = %s AND nom = %s
                """,
                (first_name, last_name),
            )
            row = cursor.fetchone()
        if row is None:
            return None
        if not self._verify_password(password, row["mdp"]):
            return None
        return self._row_to_user(row)

    @staticmethod
    def _verify_password(password: str, stored_hash: str) -> bool:
        if _LEGACY_MD5_RE.match(stored_hash):
            # Compte historique de la table `utilisateurs` (avant cette
            # fonctionnalité) : le mot de passe y est un simple MD5.
            return hashlib.md5(password.encode("utf-8")).hexdigest() == stored_hash
        return check_password_hash(stored_hash, password)

    # -- registration -------------------------------------------------

    def create_user(self, password: str, first_name: str, last_name: str, role: str = "PROF") -> User:
        """Create an account containing first name, last name, hash, and role."""
        password_hash = generate_password_hash(password)
        with db.transaction() as cursor:
            try:
                cursor.execute(
                    """
                    INSERT INTO compte (prenom, nom, mdp, role)
                    VALUES (%s, %s, %s, %s)
                    """,
                    (first_name, last_name, password_hash, role),
                )
            except pymysql.err.IntegrityError as exc:
                raise UserAlreadyExistsError(f"{first_name} {last_name}") from exc

        return User(
            mdp=password_hash,
            nom=last_name,
            prenom=first_name,
            role=role,
        )

    # -- profile update & management ----------------------------------

    def update_profile(
        self,
        current_first_name: str,
        current_last_name: str,
        first_name: str,
        last_name: str,
    ) -> None:
        """Update profile in compte and cascade changes to conversations atomically."""
        old_nom_util = f"{current_last_name}.{current_first_name}".lower()
        new_nom_util = f"{last_name}.{first_name}".lower()

        with db.transaction() as cursor:
            cursor.execute(
                """
                UPDATE compte
                SET nom = %s, prenom = %s
                WHERE prenom = %s AND nom = %s
                """,
                (last_name, first_name, current_first_name, current_last_name),
            )
            if old_nom_util != new_nom_util:
                cursor.execute(
                    """
                    UPDATE conversations
                    SET nom_util = %s
                    WHERE nom_util = %s
                    """,
                    (new_nom_util, old_nom_util),
                )

    def update_password(self, first_name: str, last_name: str, new_password_hash: str) -> None:
        """Update the password hash for the specified account."""
        with db.transaction() as cursor:
            cursor.execute(
                """
                UPDATE compte
                SET mdp = %s
                WHERE prenom = %s AND nom = %s
                """,
                (new_password_hash, first_name, last_name),
            )

    def delete_user(self, first_name: str, last_name: str, nom_util: Optional[str] = None) -> None:
        """Delete user conversations and the compte row in an atomic transaction."""
        resolved_nom_util = nom_util if nom_util else f"{last_name}.{first_name}".lower()
        with db.transaction() as cursor:
            cursor.execute(
                "DELETE FROM conversations WHERE nom_util = %s",
                (resolved_nom_util,),
            )
            cursor.execute(
                "DELETE FROM compte WHERE prenom = %s AND nom = %s",
                (first_name, last_name),
            )

    def delete_account(self, first_name: str, last_name: str, nom_util: Optional[str] = None) -> None:
        """Alias for delete_user."""
        self.delete_user(first_name, last_name, nom_util)

    def update_avatar(self, first_name: str, last_name: str, avatar: Optional[str]) -> None:
        """Update the avatar for the specified account."""
        with db.transaction() as cursor:
            cursor.execute(
                """
                UPDATE compte
                SET avatar = %s
                WHERE prenom = %s AND nom = %s
                """,
                (avatar, first_name, last_name),
            )

    @staticmethod
    def _row_to_user(row: dict) -> User:
        return User(
            mdp=row["mdp"],
            nom=row["nom"],
            prenom=row["prenom"],
            role=row.get("role") or "PROF",
            created_at=row.get("created_at"),
            avatar=row.get("avatar"),
        )
