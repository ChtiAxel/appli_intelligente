from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
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
        """Create the standalone account table if it does not exist."""
        with db.transaction() as cursor:
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS compte (
                    prenom VARCHAR(100) NOT NULL,
                    nom VARCHAR(100) NOT NULL,
                    mdp VARCHAR(255) NOT NULL,
                    PRIMARY KEY (prenom, nom)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """
            )

    # -- lookups ---------------------------------------------------

    def find_by_name(self, first_name: str, last_name: str) -> Optional[User]:
        with db.transaction() as cursor:
            cursor.execute(
                """
                SELECT prenom, nom, mdp
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
                SELECT prenom, nom, mdp
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

    def create_user(self, password: str, first_name: str, last_name: str) -> User:
        """Create an account containing only first name, last name and hash."""
        password_hash = generate_password_hash(password)
        with db.transaction() as cursor:
            try:
                cursor.execute(
                    """
                    INSERT INTO compte (prenom, nom, mdp)
                    VALUES (%s, %s, %s)
                    """,
                    (first_name, last_name, password_hash),
                )
            except pymysql.err.IntegrityError as exc:
                raise UserAlreadyExistsError(f"{first_name} {last_name}") from exc

        return User(
            mdp=password_hash,
            nom=last_name,
            prenom=first_name,
        )

    # -- profile update ------------------------------------------------

    def update_profile(self, current_first_name: str, current_last_name: str, first_name: str, last_name: str) -> None:
        with db.transaction() as cursor:
            cursor.execute(
                """
                UPDATE compte
                SET nom = %s, prenom = %s
                WHERE prenom = %s AND nom = %s
                """,
                (last_name, first_name, current_first_name, current_last_name),
            )

    @staticmethod
    def _row_to_user(row: dict) -> User:
        return User(
            mdp=row["mdp"],
            nom=row["nom"],
            prenom=row["prenom"]
        )
