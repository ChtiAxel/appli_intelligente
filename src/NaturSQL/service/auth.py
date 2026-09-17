"""Business logic for registration, login and profile management.

Wraps `storage.users.UserStorage` with input validation and the
French user-facing error messages used by the UI (see sprint-00 user
stories US-01 to US-09 in docs/monitoring/sprint-00.md).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

from NaturSQL.storage.users import User, UserAlreadyExistsError, UserStorage

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
MIN_PASSWORD_LENGTH = 8


@dataclass
class AuthResult:
    """Outcome of a register/login/update operation for the UI layer."""

    ok: bool
    message: str
    user: Optional[User] = None


class AuthService:
    def __init__(self, storage: Optional[UserStorage] = None) -> None:
        self._storage = storage or UserStorage()
        self._storage.ensure_schema()

    # -- US-04/US-05: connexion -----------------------------------------

    def login(self, email: str, password: str) -> AuthResult:
        email = (email or "").strip().lower()
        if not email or not password:
            return AuthResult(False, "Merci de renseigner votre email et votre mot de passe.")

        user = self._storage.authenticate(email, password)
        if user is None:
            return AuthResult(False, "Email ou mot de passe incorrect.")

        return AuthResult(True, f"Bienvenue, {user.prenom_ens} !", user)

    # -- US-01/US-02/US-03: inscription ----------------------------------

    def register(
        self,
        email: str,
        password: str,
        confirm_password: str,
        first_name: str,
        last_name: str,
        agree_rgpd: bool,
    ) -> AuthResult:
        email = (email or "").strip().lower()
        first_name = (first_name or "").strip()
        last_name = (last_name or "").strip()

        if not all([email, password, confirm_password, first_name, last_name]):
            return AuthResult(False, "Merci de remplir tous les champs.")
        if not _EMAIL_RE.match(email):
            return AuthResult(False, "Adresse email invalide.")
        if len(password) < MIN_PASSWORD_LENGTH:
            return AuthResult(
                False, f"Le mot de passe doit contenir au moins {MIN_PASSWORD_LENGTH} caractères."
            )
        if password != confirm_password:
            return AuthResult(False, "Les mots de passe ne correspondent pas.")
        if not agree_rgpd:
            return AuthResult(False, "Vous devez accepter la politique de confidentialité (RGPD).")

        try:
            user = self._storage.create_user(email, password, first_name, last_name)
        except UserAlreadyExistsError:
            return AuthResult(False, "Un compte existe déjà avec cet email.")

        return AuthResult(True, "Compte créé avec succès. Vous pouvez vous connecter.", user)

    # -- US-08: modification du profil -----------------------------------

    def update_profile(
        self, current_user: User, first_name: str, last_name: str, email: str
    ) -> AuthResult:
        first_name = (first_name or "").strip()
        last_name = (last_name or "").strip()
        email = (email or "").strip().lower()

        if not all([first_name, last_name, email]):
            return AuthResult(False, "Merci de remplir tous les champs.")
        if not _EMAIL_RE.match(email):
            return AuthResult(False, "Adresse email invalide.")

        try:
            self._storage.update_profile(current_user.id_ens, first_name, last_name, email)
        except UserAlreadyExistsError:
            return AuthResult(False, "Un autre compte utilise déjà cet email.")

        updated = self._storage.find_by_email(email)
        return AuthResult(True, "Profil mis à jour.", updated)
