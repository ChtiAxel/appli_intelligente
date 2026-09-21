"""Business logic for registration, login and profile management.

Wraps `storage.users.UserStorage` with input validation and the
French user-facing error/success messages used by the UI (see
sprint-00 user stories US-01 to US-09 in
docs/monitoring/sprint-00.md).

Login uses an auto-generated "nom.prenom" identifiant (no email).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

from ..storage.users import User, UserAlreadyExistsError, UserStorage

_SPECIAL_CHARS_RE = re.compile(r"[^A-Za-z0-9]")
MIN_PASSWORD_LENGTH = 8


@dataclass
class AuthResult:
    """Outcome of a register/login/update operation for the UI layer."""

    ok: bool
    message: str
    user: Optional[User] = None


def _validate_password(password: str) -> Optional[str]:
    """Return an error message if `password` is too weak, else None.

    Règle : au moins 8 caractères, une majuscule, un chiffre et un
    caractère spécial.
    """
    if len(password) < MIN_PASSWORD_LENGTH:
        return f"Le mot de passe doit contenir au moins {MIN_PASSWORD_LENGTH} caractères."
    if not any(c.isupper() for c in password):
        return "Le mot de passe doit contenir au moins une majuscule."
    if not any(c.isdigit() for c in password):
        return "Le mot de passe doit contenir au moins un chiffre."
    if not _SPECIAL_CHARS_RE.search(password):
        return "Le mot de passe doit contenir au moins un caractère spécial."
    return None


class AuthService:
    def __init__(self, storage: Optional[UserStorage] = None) -> None:
        self._storage = storage or UserStorage()
        self._storage.ensure_schema()

    # -- US-04/US-05: connexion -----------------------------------------

    def login(self, identifiant: str, password: str) -> AuthResult:
        identifiant = (identifiant or "").strip().lower()
        password = password or ""

        if not identifiant or not password:
            return AuthResult(False, "Tous les champs sont obligatoires.")

        user = self._storage.authenticate(identifiant, password)
        if user is None:
            return AuthResult(False, "Identifiant ou mot de passe incorrect.")

        return AuthResult(True, f"Connexion réussie. Bienvenue, {user.prenom_ens} !", user)

    # -- US-01/US-02/US-03: inscription ----------------------------------

    def register(
        self,
        password: str,
        confirm_password: str,
        first_name: str,
        last_name: str,
    ) -> AuthResult:
        password = password or ""
        confirm_password = confirm_password or ""
        first_name = (first_name or "").strip()
        last_name = (last_name or "").strip()

        if not all([password, confirm_password, first_name, last_name]):
            return AuthResult(False, "Tous les champs sont obligatoires.")

        password_error = _validate_password(password)
        if password_error:
            return AuthResult(False, password_error)
        if password != confirm_password:
            return AuthResult(False, "Les mots de passe ne correspondent pas.")

        try:
            user = self._storage.create_user(password, first_name, last_name)
        except UserAlreadyExistsError:
            return AuthResult(False, "Un compte existe déjà avec ces informations.")

        return AuthResult(
            True,
            f"Compte créé avec succès ! Votre identifiant de connexion est : {user.nom_util}",
            user,
        )

    # -- US-08: modification du profil -----------------------------------

    def update_profile(self, current_user: User, first_name: str, last_name: str) -> AuthResult:
        first_name = (first_name or "").strip()
        last_name = (last_name or "").strip()

        if not all([first_name, last_name]):
            return AuthResult(False, "Tous les champs sont obligatoires.")

        self._storage.update_profile(current_user.id_ens, first_name, last_name)

        updated = self._storage.find_by_username(current_user.nom_util)
        return AuthResult(True, "Profil mis à jour avec succès.", updated)
