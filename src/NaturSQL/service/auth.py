"""Business logic for registration, login and profile management.

Wraps `storage.users.UserStorage` with input validation and the
French user-facing error/success messages used by the UI (see
sprint-00 user stories US-01 to US-09 in
docs/monitoring/sprint-00.md).

Login uses the first name, last name and password stored in `compte`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Optional

from werkzeug.security import generate_password_hash

from ..storage.users import User, UserAlreadyExistsError, UserStorage

_SPECIAL_CHARS_RE = re.compile(r"[^A-Za-z0-9]")
MIN_PASSWORD_LENGTH = 8


class UserRole(str, Enum):
    PROF = "PROF"
    SECRETAIRE = "SECRETAIRE"
    ADMIN = "ADMIN"


DEFAULT_ROLE = UserRole.PROF.value

ROLE_LABELS = {
    UserRole.PROF.value: "Enseignant",
    UserRole.SECRETAIRE.value: "Secrétaire",
    UserRole.ADMIN.value: "Administrateur",
}


def get_role_label(role: str) -> str:
    """Return the French display label for a role."""
    return ROLE_LABELS.get(role, role)


@dataclass
class AuthResult:
    """Outcome of a register/login/update operation for the UI layer."""

    ok: bool
    message: str
    user: Optional[User] = None


def validate_password(password: Optional[str]) -> Optional[str]:
    """Return an error message if `password` is too weak, else None.

    Règle : au moins 8 caractères, une majuscule, un chiffre et un
    caractère spécial.
    """
    password = password or ""
    if len(password) < MIN_PASSWORD_LENGTH:
        return f"Le mot de passe doit contenir au moins {MIN_PASSWORD_LENGTH} caractères."
    if not any(c.isupper() for c in password):
        return "Le mot de passe doit contenir au moins une majuscule."
    if not any(c.isdigit() for c in password):
        return "Le mot de passe doit contenir au moins un chiffre."
    if not _SPECIAL_CHARS_RE.search(password):
        return "Le mot de passe doit contenir au moins un caractère spécial."
    return None


_validate_password = validate_password


class AuthService:
    def __init__(self, storage: Optional[UserStorage] = None) -> None:
        self._storage = storage or UserStorage()
        self._storage.ensure_schema()

    # -- US-04/US-05: connexion -----------------------------------------

    def login(self, first_name: str, last_name: str, password: str) -> AuthResult:
        first_name = (first_name or "").strip()
        last_name = (last_name or "").strip()
        password = password or ""

        if not first_name or not last_name or not password:
            return AuthResult(False, "Tous les champs sont obligatoires.")

        user = self._storage.authenticate(first_name, last_name, password)
        if user is None:
            return AuthResult(False, "Prénom, nom ou mot de passe incorrect.")

        return AuthResult(True, f"Connexion réussie. Bienvenue, {user.prenom} !", user)

    # -- US-01/US-02/US-03: inscription ----------------------------------

    def register(
        self,
        password: str,
        confirm_password: str,
        first_name: str,
        last_name: str,
        role: str = DEFAULT_ROLE,
    ) -> AuthResult:
        password = password or ""
        confirm_password = confirm_password or ""
        first_name = (first_name or "").strip()
        last_name = (last_name or "").strip()

        if not all([password, confirm_password, first_name, last_name]):
            return AuthResult(False, "Tous les champs sont obligatoires.")

        password_error = validate_password(password)
        if password_error:
            return AuthResult(False, password_error)
        if password != confirm_password:
            return AuthResult(False, "Les mots de passe ne correspondent pas.")

        try:
            try:
                user = self._storage.create_user(password, first_name, last_name, role=role)
            except TypeError:
                user = self._storage.create_user(password, first_name, last_name)
        except UserAlreadyExistsError:
            return AuthResult(False, "Un compte existe déjà avec ces informations.")

        return AuthResult(
            True,
            "Compte créé avec succès ! Vous pouvez maintenant vous connecter.",
            user,
        )

    # -- US-08: modification du profil -----------------------------------

    def update_profile(self, current_user: Optional[User], first_name: str, last_name: str) -> AuthResult:
        if current_user is None:
            return AuthResult(False, "Session expirée, veuillez vous reconnecter.")

        first_name = (first_name or "").strip()
        last_name = (last_name or "").strip()

        if not all([first_name, last_name]):
            return AuthResult(False, "Tous les champs sont obligatoires.")

        self._storage.update_profile(current_user.prenom, current_user.nom, first_name, last_name)

        updated = self._storage.find_by_name(first_name, last_name)
        return AuthResult(True, "Profil mis à jour avec succès.", updated)

    # -- V2 R2: changement de mot de passe ------------------------------

    def change_password(
        self,
        user: Optional[User],
        current_password: str,
        new_password: str,
        confirm_password: str,
    ) -> AuthResult:
        """Validate, verify old password, hash new password and update storage."""
        if user is None:
            return AuthResult(False, "Session expirée, veuillez vous reconnecter.")

        current_password = current_password or ""
        new_password = new_password or ""
        confirm_password = confirm_password or ""

        if not current_password or not new_password or not confirm_password:
            return AuthResult(False, "Tous les champs sont obligatoires.")

        authenticated_user = self._storage.authenticate(user.prenom, user.nom, current_password)
        if authenticated_user is None:
            return AuthResult(False, "L'ancien mot de passe est incorrect.")

        if new_password != confirm_password:
            return AuthResult(False, "Les nouveaux mots de passe ne correspondent pas.")

        if new_password == current_password:
            return AuthResult(False, "Le nouveau mot de passe doit être différent de l'ancien.")

        password_error = validate_password(new_password)
        if password_error:
            return AuthResult(False, password_error)

        new_hash = generate_password_hash(new_password)
        self._storage.update_password(user.prenom, user.nom, new_hash)

        updated_user = self._storage.find_by_name(user.prenom, user.nom) or user
        return AuthResult(True, "Mot de passe modifié avec succès !", updated_user)

    # -- V2 R6: suppression de compte (RGPD) ---------------------------

    def delete_account(self, user: Optional[User], password: str) -> AuthResult:
        """Permanently delete user account and associated data in compliance with GDPR."""
        if user is None:
            return AuthResult(False, "Session expirée ou invalide.")

        password = password or ""
        if not password:
            return AuthResult(False, "Le mot de passe est obligatoire pour confirmer la suppression.")

        authenticated_user = self._storage.authenticate(user.prenom, user.nom, password)
        if authenticated_user is None:
            return AuthResult(False, "Mot de passe incorrect. La suppression a été annulée.")

        try:
            self._storage.delete_user(user.prenom, user.nom, user.nom_util)
        except Exception as exc:
            return AuthResult(False, f"Erreur lors de la suppression du compte : {exc}")

        return AuthResult(True, "Compte et données supprimés avec succès.")

    # -- V2 R5: mise à jour de l'avatar ---------------------------------

    def update_avatar(self, user: Optional[User], avatar: Optional[str]) -> AuthResult:
        """Update user avatar in storage."""
        if user is None:
            return AuthResult(False, "Session expirée ou invalide.")

        self._storage.update_avatar(user.prenom, user.nom, avatar)
        updated_user = self._storage.find_by_name(user.prenom, user.nom) or user
        return AuthResult(True, "Avatar mis à jour avec succès !", updated_user)
