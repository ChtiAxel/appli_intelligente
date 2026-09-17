"""Persistence adapter for authentication and profile data.

Reuses the existing `appia` schema instead of creating a parallel one:

- `utilisateurs` (nom_util, mdp, id_ens, admin, vacataire, budget)
  is the login table: `nom_util` stores the user's email, `mdp` the
  hashed password, `id_ens` is a foreign key to `enseignants`.
- `enseignants` (id_ens, nom_ens, prenom_ens, mail_ens, ...) holds the
  profile fields shown on the "Profil" page (first name, last name,
  email).

The original 54 seeded accounts have a raw MD5 password hash
(32 hex chars, from before this feature existed). New accounts are
hashed with Werkzeug's salted PBKDF2. `authenticate()` accepts both so
the existing rows keep working.
"""

from __future__ import annotations

import hashlib
import re
import string
import unicodedata
from dataclasses import dataclass
from random import choices
from typing import Optional

import pymysql
from werkzeug.security import check_password_hash, generate_password_hash

from NaturSQL.storage import db

_LEGACY_MD5_RE = re.compile(r"^[0-9a-f]{32}$")


@dataclass
class User:
    """A row from `utilisateurs` joined with its `enseignants` profile."""

    nom_util: str  # email, used as login
    id_ens: str
    admin: bool
    vacataire: bool
    budget: bool
    nom_ens: str
    prenom_ens: str
    mail_ens: Optional[str]

    @property
    def full_name(self) -> str:
        return f"{self.prenom_ens} {self.nom_ens}".strip()


class UserAlreadyExistsError(Exception):
    """Raised when trying to register an email that is already in use."""


class UserStorage:
    """Read/write access to `utilisateurs` and `enseignants`."""

    def ensure_schema(self) -> None:
        """Widen `mdp` if it still has its historical MD5-only size.

        Non-destructive: existing rows and their values are untouched,
        only the column's maximum length changes.
        """
        with db.transaction() as cursor:
            cursor.execute(
                """
                SELECT CHARACTER_MAXIMUM_LENGTH
                FROM information_schema.COLUMNS
                WHERE TABLE_SCHEMA = DATABASE()
                  AND TABLE_NAME = 'utilisateurs'
                  AND COLUMN_NAME = 'mdp'
                """
            )
            row = cursor.fetchone()
            if row and row["CHARACTER_MAXIMUM_LENGTH"] < 255:
                cursor.execute(
                    "ALTER TABLE `utilisateurs` MODIFY `mdp` VARCHAR(255) NOT NULL"
                )

    # -- lookups ---------------------------------------------------

    def find_by_email(self, email: str) -> Optional[User]:
        with db.transaction() as cursor:
            cursor.execute(
                """
                SELECT u.nom_util, u.mdp, u.id_ens, u.admin, u.vacataire, u.budget,
                       e.nom_ens, e.prenom_ens, e.mail_ens
                FROM utilisateurs u
                JOIN enseignants e ON e.id_ens = u.id_ens
                WHERE u.nom_util = %s
                """,
                (email,),
            )
            row = cursor.fetchone()
        return self._row_to_user(row) if row else None

    # -- authentication ---------------------------------------------

    def authenticate(self, email: str, password: str) -> Optional[User]:
        with db.transaction() as cursor:
            cursor.execute(
                """
                SELECT u.nom_util, u.mdp, u.id_ens, u.admin, u.vacataire, u.budget,
                       e.nom_ens, e.prenom_ens, e.mail_ens
                FROM utilisateurs u
                JOIN enseignants e ON e.id_ens = u.id_ens
                WHERE u.nom_util = %s
                """,
                (email,),
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

    def create_user(
        self, email: str, password: str, first_name: str, last_name: str
    ) -> User:
        password_hash = generate_password_hash(password)
        with db.transaction() as cursor:
            cursor.execute(
                "SELECT 1 FROM utilisateurs WHERE nom_util = %s", (email,)
            )
            if cursor.fetchone():
                raise UserAlreadyExistsError(email)

            id_ens = self._generate_id_ens(cursor, first_name, last_name)

            cursor.execute(
                """
                INSERT INTO enseignants
                    (id_ens, titulaire_ens, nom_ens, prenom_ens, mail_ens)
                VALUES (%s, 0, %s, %s, %s)
                """,
                (id_ens, last_name, first_name, email),
            )
            try:
                cursor.execute(
                    """
                    INSERT INTO utilisateurs
                        (nom_util, mdp, id_ens, admin, vacataire, budget)
                    VALUES (%s, %s, %s, 0, 0, 0)
                    """,
                    (email, password_hash, id_ens),
                )
            except pymysql.err.IntegrityError as exc:
                raise UserAlreadyExistsError(email) from exc

        return User(
            nom_util=email,
            id_ens=id_ens,
            admin=False,
            vacataire=False,
            budget=False,
            nom_ens=last_name,
            prenom_ens=first_name,
            mail_ens=email,
        )

    @staticmethod
    def _generate_id_ens(cursor, first_name: str, last_name: str) -> str:
        """Pick a free 4-char `id_ens` code, e.g. 'Raphael Deroo' -> 'RDEO'."""

        def strip_accents(value: str) -> str:
            normalized = unicodedata.normalize("NFKD", value)
            return "".join(c for c in normalized if not unicodedata.combining(c))

        first = strip_accents(first_name).upper()
        last = strip_accents(last_name).upper()
        base = (first[:1] + last[:3]) or "USR"
        base = "".join(c for c in base if c in string.ascii_uppercase) or "USR"
        base = base[:4]

        for candidate in [base] + [f"{base[:3]}{i}" for i in range(1, 10)]:
            cursor.execute(
                "SELECT 1 FROM enseignants WHERE id_ens = %s", (candidate,)
            )
            if not cursor.fetchone():
                return candidate

        # Extremely unlikely fallback: random 4-char alphanumeric code.
        while True:
            candidate = "".join(choices(string.ascii_uppercase + string.digits, k=4))
            cursor.execute(
                "SELECT 1 FROM enseignants WHERE id_ens = %s", (candidate,)
            )
            if not cursor.fetchone():
                return candidate

    # -- profile update ------------------------------------------------

    def update_profile(
        self, id_ens: str, first_name: str, last_name: str, email: str
    ) -> None:
        with db.transaction() as cursor:
            cursor.execute(
                "SELECT nom_util FROM utilisateurs WHERE id_ens = %s", (id_ens,)
            )
            row = cursor.fetchone()
            current_login = row["nom_util"] if row else None

            if email != current_login:
                cursor.execute(
                    "SELECT 1 FROM utilisateurs WHERE nom_util = %s", (email,)
                )
                if cursor.fetchone():
                    raise UserAlreadyExistsError(email)

            cursor.execute(
                """
                UPDATE enseignants
                SET nom_ens = %s, prenom_ens = %s, mail_ens = %s
                WHERE id_ens = %s
                """,
                (last_name, first_name, email, id_ens),
            )
            cursor.execute(
                "UPDATE utilisateurs SET nom_util = %s WHERE id_ens = %s",
                (email, id_ens),
            )

    @staticmethod
    def _row_to_user(row: dict) -> User:
        return User(
            nom_util=row["nom_util"],
            id_ens=row["id_ens"],
            admin=bool(row["admin"]),
            vacataire=bool(row["vacataire"]),
            budget=bool(row["budget"]),
            nom_ens=row["nom_ens"],
            prenom_ens=row["prenom_ens"],
            mail_ens=row["mail_ens"],
        )
