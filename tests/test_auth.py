import unittest
from unittest.mock import patch
from werkzeug.security import check_password_hash

from NaturSQL.service.auth import (
    DEFAULT_ROLE,
    ROLE_LABELS,
    AuthService,
    UserRole,
    _validate_password,
    get_role_label,
    validate_password,
)
from NaturSQL.storage.users import User


class FakeUserStorage:
    def __init__(self, user=None, password="Secret1!"):
        self.user = user
        self.password = password
        self.created = None
        self.created_role = None
        self.updated = None
        self.updated_password = None
        self.deleted = None
        self.updated_avatar = None
        self.should_fail_delete = False

    def ensure_schema(self):
        pass

    def authenticate(self, first_name, last_name, password):
        if self.user and (first_name, last_name) == (self.user.prenom, self.user.nom):
            if password == self.password:
                return self.user
        elif self.user and (first_name, last_name, password) == ("Jean", "Dupont", "Secret1!"):
            return self.user
        return None

    def create_user(self, password, first_name, last_name, role="PROF", rgpd_accepted=True):
        self.created = (password, first_name, last_name)
        self.created_role = role
        self.created_rgpd = rgpd_accepted
        from datetime import datetime
        self.user = User(
            first_name,
            last_name,
            "hash",
            role=role,
            rgpd_accepted_at=datetime.now() if rgpd_accepted else None,
        )
        self.password = password
        return self.user

    def update_profile(self, current_first_name, current_last_name, first_name, last_name):
        self.updated = (current_first_name, current_last_name, first_name, last_name)
        if self.user:
            self.user.prenom = first_name
            self.user.nom = last_name

    def update_password(self, first_name, last_name, new_password_hash):
        self.updated_password = (first_name, last_name, new_password_hash)
        if self.user:
            self.user.mdp = new_password_hash

    def delete_user(self, first_name, last_name, nom_util=None):
        if self.should_fail_delete:
            raise RuntimeError("Database connection error during deletion")
        self.deleted = (first_name, last_name, nom_util)
        self.user = None

    def delete_account(self, first_name, last_name, nom_util=None):
        self.delete_user(first_name, last_name, nom_util)

    def update_avatar(self, first_name, last_name, avatar):
        self.updated_avatar = (first_name, last_name, avatar)
        if self.user:
            self.user.avatar = avatar

    def find_by_name(self, first_name, last_name):
        if self.user and (self.user.prenom, self.user.nom) == (first_name, last_name):
            return self.user
        return User(first_name, last_name, "hash")


class AuthTests(unittest.TestCase):
    def test_password_validation_rules(self):
        # Backwards compatibility check
        self.assertIs(_validate_password, validate_password)
        # Edge cases
        self.assertIsNotNone(validate_password(None))
        self.assertIsNotNone(validate_password(""))
        self.assertIsNotNone(validate_password("short"))
        self.assertIsNotNone(validate_password("longpassword1!"))
        self.assertIsNotNone(validate_password("Longpassword!"))
        self.assertIsNotNone(validate_password("Longpassword1"))
        self.assertIsNone(validate_password("Longpassword1!"))

    def test_role_definitions_and_labels(self):
        self.assertEqual(UserRole.PROF.value, "PROF")
        self.assertEqual(UserRole.SECRETAIRE.value, "SECRETAIRE")
        self.assertEqual(UserRole.ADMIN.value, "ADMIN")
        self.assertEqual(DEFAULT_ROLE, "PROF")

        self.assertEqual(ROLE_LABELS["PROF"], "Enseignant")
        self.assertEqual(ROLE_LABELS["SECRETAIRE"], "Secrétaire")
        self.assertEqual(ROLE_LABELS["ADMIN"], "Administrateur")

        self.assertEqual(get_role_label("PROF"), "Enseignant")
        self.assertEqual(get_role_label("SECRETAIRE"), "Secrétaire")
        self.assertEqual(get_role_label("ADMIN"), "Administrateur")
        self.assertEqual(get_role_label("AUTRE"), "AUTRE")

    def test_register_validates_and_creates_user(self):
        storage = FakeUserStorage()
        result = AuthService(storage).register("Longpassword1!", "Longpassword1!", " Jean ", " Dupont ")
        self.assertTrue(result.ok)
        self.assertEqual(storage.created, ("Longpassword1!", "Jean", "Dupont"))
        self.assertEqual(storage.created_role, "PROF")

    def test_register_with_custom_role(self):
        storage = FakeUserStorage()
        result = AuthService(storage).register(
            "Longpassword1!", "Longpassword1!", "Claire", "Martin", role="SECRETAIRE"
        )
        self.assertTrue(result.ok)
        self.assertEqual(storage.created_role, "SECRETAIRE")
        self.assertEqual(result.user.role, "SECRETAIRE")

    def test_register_rejects_empty_mismatch_and_weak_password(self):
        service = AuthService(FakeUserStorage())
        self.assertFalse(service.register("", "", "", "").ok)
        self.assertFalse(service.register("Longpassword1!", "Different1!", "Jean", "Dupont").ok)
        self.assertFalse(service.register("weak", "weak", "Jean", "Dupont").ok)

    def test_login_and_profile_update(self):
        user = User("Jean", "Dupont", "hash")
        storage = FakeUserStorage(user)
        service = AuthService(storage)
        self.assertTrue(service.login(" Jean ", "Dupont", "Secret1!").ok)
        self.assertFalse(service.login("Jean", "Dupont", "wrong").ok)
        result = service.update_profile(user, " Jeanne ", " Martin ")
        self.assertTrue(result.ok)
        self.assertEqual(storage.updated, ("Jean", "Dupont", "Jeanne", "Martin"))

    def test_update_profile_without_user(self):
        service = AuthService(FakeUserStorage())
        result = service.update_profile(None, "Jeanne", "Martin")
        self.assertFalse(result.ok)
        self.assertIn("Session expirée", result.message)

    # -- change_password tests -----------------------------------------

    def test_change_password_requires_logged_in_user(self):
        service = AuthService(FakeUserStorage())
        result = service.change_password(None, "Secret1!", "NewSecret2!", "NewSecret2!")
        self.assertFalse(result.ok)
        self.assertIn("Session expirée", result.message)

    def test_change_password_requires_all_fields(self):
        user = User("Jean", "Dupont", "hash")
        service = AuthService(FakeUserStorage(user))

        res1 = service.change_password(user, "", "NewSecret2!", "NewSecret2!")
        self.assertFalse(res1.ok)
        self.assertEqual(res1.message, "Tous les champs sont obligatoires.")

        res2 = service.change_password(user, "Secret1!", "", "NewSecret2!")
        self.assertFalse(res2.ok)
        self.assertEqual(res2.message, "Tous les champs sont obligatoires.")

        res3 = service.change_password(user, "Secret1!", "NewSecret2!", "")
        self.assertFalse(res3.ok)
        self.assertEqual(res3.message, "Tous les champs sont obligatoires.")

    def test_change_password_rejects_wrong_old_password(self):
        user = User("Jean", "Dupont", "hash")
        service = AuthService(FakeUserStorage(user))
        result = service.change_password(user, "WrongSecret0!", "NewSecret2!", "NewSecret2!")
        self.assertFalse(result.ok)
        self.assertEqual(result.message, "L'ancien mot de passe est incorrect.")

    def test_change_password_rejects_mismatched_confirmation(self):
        user = User("Jean", "Dupont", "hash")
        service = AuthService(FakeUserStorage(user))
        result = service.change_password(user, "Secret1!", "NewSecret2!", "DifferentSecret3!")
        self.assertFalse(result.ok)
        self.assertEqual(result.message, "Les nouveaux mots de passe ne correspondent pas.")

    def test_change_password_rejects_identical_new_password(self):
        user = User("Jean", "Dupont", "hash")
        service = AuthService(FakeUserStorage(user))
        result = service.change_password(user, "Secret1!", "Secret1!", "Secret1!")
        self.assertFalse(result.ok)
        self.assertEqual(result.message, "Le nouveau mot de passe doit être différent de l'ancien.")

    def test_change_password_rejects_weak_passwords(self):
        user = User("Jean", "Dupont", "hash")
        service = AuthService(FakeUserStorage(user))

        # Too short
        res_short = service.change_password(user, "Secret1!", "Sh1!", "Sh1!")
        self.assertFalse(res_short.ok)
        self.assertIn("au moins 8 caractères", res_short.message)

        # No uppercase
        res_no_upper = service.change_password(user, "Secret1!", "newpass1!", "newpass1!")
        self.assertFalse(res_no_upper.ok)
        self.assertIn("au moins une majuscule", res_no_upper.message)

        # No digit
        res_no_digit = service.change_password(user, "Secret1!", "Newpassword!", "Newpassword!")
        self.assertFalse(res_no_digit.ok)
        self.assertIn("au moins un chiffre", res_no_digit.message)

        # No special character
        res_no_spec = service.change_password(user, "Secret1!", "Newpassword1", "Newpassword1")
        self.assertFalse(res_no_spec.ok)
        self.assertIn("au moins un caractère spécial", res_no_spec.message)

    def test_change_password_success(self):
        user = User("Jean", "Dupont", "old_hash")
        storage = FakeUserStorage(user)
        service = AuthService(storage)

        result = service.change_password(user, "Secret1!", "NewSecret2!", "NewSecret2!")
        self.assertTrue(result.ok)
        self.assertEqual(result.message, "Mot de passe modifié avec succès !")
        self.assertIsNotNone(storage.updated_password)
        first, last, new_hash = storage.updated_password
        self.assertEqual(first, "Jean")
        self.assertEqual(last, "Dupont")
        # Verify genuine Werkzeug hash
        self.assertTrue(check_password_hash(new_hash, "NewSecret2!"))
        self.assertFalse(check_password_hash(new_hash, "Secret1!"))
        self.assertIsNotNone(result.user)

    # -- delete_account tests ------------------------------------------

    def test_delete_account_requires_logged_in_user(self):
        service = AuthService(FakeUserStorage())
        result = service.delete_account(None, "Secret1!")
        self.assertFalse(result.ok)
        self.assertIn("Session expirée ou invalide.", result.message)

    def test_delete_account_requires_password(self):
        user = User("Jean", "Dupont", "hash")
        service = AuthService(FakeUserStorage(user))
        result = service.delete_account(user, "")
        self.assertFalse(result.ok)
        self.assertIn("obligatoire", result.message)

    def test_delete_account_rejects_wrong_password(self):
        user = User("Jean", "Dupont", "hash")
        service = AuthService(FakeUserStorage(user))
        result = service.delete_account(user, "WrongPassword1!")
        self.assertFalse(result.ok)
        self.assertIn("Mot de passe incorrect", result.message)

    def test_delete_account_success(self):
        user = User("Jean", "Dupont", "hash")
        storage = FakeUserStorage(user)
        service = AuthService(storage)

        result = service.delete_account(user, "Secret1!")
        self.assertTrue(result.ok)
        self.assertEqual(result.message, "Compte et données supprimés avec succès.")
        self.assertEqual(storage.deleted, ("Jean", "Dupont", "dupont.jean"))
        self.assertIsNone(storage.user)

    def test_delete_account_storage_error(self):
        user = User("Jean", "Dupont", "hash")
        storage = FakeUserStorage(user)
        storage.should_fail_delete = True
        service = AuthService(storage)

        result = service.delete_account(user, "Secret1!")
        self.assertFalse(result.ok)
        self.assertIn("Erreur lors de la suppression du compte", result.message)

    # -- update_avatar tests -------------------------------------------

    def test_update_avatar_requires_logged_in_user(self):
        service = AuthService(FakeUserStorage())
        result = service.update_avatar(None, "avatar.png")
        self.assertFalse(result.ok)
        self.assertIn("Session expirée ou invalide.", result.message)

    def test_update_avatar_success(self):
        user = User("Jean", "Dupont", "hash")
        storage = FakeUserStorage(user)
        service = AuthService(storage)

        result = service.update_avatar(user, "/path/to/custom_avatar.png")
        self.assertTrue(result.ok)
        self.assertEqual(result.message, "Avatar mis à jour avec succès !")
        self.assertEqual(storage.updated_avatar, ("Jean", "Dupont", "/path/to/custom_avatar.png"))
        self.assertEqual(result.user.avatar, "/path/to/custom_avatar.png")

    def test_update_avatar_reset_to_none(self):
        user = User("Jean", "Dupont", "hash", avatar="/old/avatar.png")
        storage = FakeUserStorage(user)
        service = AuthService(storage)

        result = service.update_avatar(user, None)
        self.assertTrue(result.ok)
        self.assertEqual(storage.updated_avatar, ("Jean", "Dupont", None))
        self.assertIsNone(result.user.avatar)

    def test_register_requires_rgpd_consent(self):
        storage = FakeUserStorage()
        service = AuthService(storage)

        # Consent rejected
        result_fail = service.register(
            "Longpassword1!", "Longpassword1!", "Jean", "Dupont", rgpd_consent=False
        )
        self.assertFalse(result_fail.ok)
        self.assertIn("Vous devez accepter la politique de confidentialité", result_fail.message)
        self.assertIsNone(storage.created)

        # Consent granted
        result_ok = service.register(
            "Longpassword1!", "Longpassword1!", "Jean", "Dupont", rgpd_consent=True
        )
        self.assertTrue(result_ok.ok)
        self.assertIsNotNone(storage.created)
        self.assertIsNotNone(result_ok.user.rgpd_accepted_at)

    @patch("NaturSQL.service.auth.ConversationStorage")
    def test_export_user_data_art_20(self, mock_conv_storage):
        service = AuthService(FakeUserStorage())
        # None user
        self.assertEqual(service.export_user_data(None), {})

        # Valid user
        from datetime import datetime
        mock_instance = mock_conv_storage.return_value
        mock_instance.get_full_user_history.return_value = [
            {
                "id": 1,
                "title": "Test Chat",
                "created_at": "2026-10-12T10:00:00",
                "messages": [
                    {"id": 10, "query": "SELECT 1;", "is_user": True, "created_at": "2026-10-12T10:01:00"}
                ]
            }
        ]

        user = User(
            prenom="Jean",
            nom="Dupont",
            mdp="hash",
            role="PROF",
            created_at=datetime(2026, 10, 12, 9, 0),
            rgpd_accepted_at=datetime(2026, 10, 12, 9, 0),
        )
        export = service.export_user_data(user)
        self.assertEqual(export["format"], "NaturSQL RGPD Data Export")
        self.assertEqual(export["version"], "2.0")
        self.assertEqual(export["user"]["prenom"], "Jean")
        self.assertEqual(export["user"]["nom"], "Dupont")
        self.assertEqual(export["user"]["nom_util"], "dupont.jean")
        self.assertEqual(export["user"]["role"], "PROF")
        self.assertEqual(export["user"]["created_at"], "2026-10-12T09:00:00")
        self.assertEqual(export["user"]["rgpd_accepted_at"], "2026-10-12T09:00:00")
        self.assertEqual(export["conversations_count"], 1)
        self.assertEqual(len(export["conversations"]), 1)
        self.assertEqual(export["conversations"][0]["title"], "Test Chat")


if __name__ == "__main__":
    unittest.main()
