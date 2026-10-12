"""Adversarial stress-test harness for NaturSQL V2 Security and Auth Logic.

Covers:
- Password complexity boundary conditions (7 vs 8 chars, missing char types)
- Character encoding, accented characters, unicode, emojis
- SQL injection payloads in passwords, change_password and delete_account
- change_password edge cases (None user, empty/whitespace inputs, confirmation mismatch, old == new, invalid current)
- delete_account edge cases (None user, empty password, wrong password, non-existent user, storage failures)
- Parameterized query verification against SQL injection in UserStorage methods
"""

import hashlib
import unittest
from unittest.mock import patch
from werkzeug.security import check_password_hash, generate_password_hash

from NaturSQL.service.auth import AuthService, validate_password
from NaturSQL.storage.users import User, UserStorage


class InMemoryUserStorage:
    """Accurate in-memory simulation of UserStorage for empirical security testing."""

    def __init__(self, users=None):
        # keyed by (prenom, nom)
        self.users = {}
        if users:
            for u in users:
                self.users[(u.prenom, u.nom)] = u
        self.conversations = {}  # nom_util -> list of conversations
        self.force_exception = None

    def ensure_schema(self):
        pass

    def authenticate(self, first_name, last_name, password):
        user = self.users.get((first_name, last_name))
        if not user:
            return None
        if not self._verify_password(password, user.mdp):
            return None
        return user

    @staticmethod
    def _verify_password(password, stored_hash):
        if len(stored_hash) == 32:
            return hashlib.md5(password.encode("utf-8")).hexdigest() == stored_hash
        return check_password_hash(stored_hash, password)

    def find_by_name(self, first_name, last_name):
        return self.users.get((first_name, last_name))

    def update_password(self, first_name, last_name, new_password_hash):
        if self.force_exception:
            raise self.force_exception
        user = self.users.get((first_name, last_name))
        if user:
            user.mdp = new_password_hash

    def delete_user(self, first_name, last_name, nom_util=None):
        if self.force_exception:
            raise self.force_exception
        self.users.pop((first_name, last_name), None)
        if nom_util:
            self.conversations.pop(nom_util, None)

    def delete_account(self, first_name, last_name, nom_util=None):
        self.delete_user(first_name, last_name, nom_util)

    def update_avatar(self, first_name, last_name, avatar):
        if self.force_exception:
            raise self.force_exception
        user = self.users.get((first_name, last_name))
        if user:
            user.avatar = avatar


class PasswordComplexityAdversarialTests(unittest.TestCase):
    """Stress tests on password complexity boundaries, characters, and SQL injection payloads."""

    def test_boundary_length_7_vs_8(self):
        # 7 chars: must be rejected
        pass_7 = "Aa1!def"
        self.assertEqual(len(pass_7), 7)
        err_7 = validate_password(pass_7)
        self.assertIsNotNone(err_7)
        self.assertIn("au moins 8 caractères", err_7)

        # 8 chars: boundary pass
        pass_8 = "Aa1!defg"
        self.assertEqual(len(pass_8), 8)
        self.assertIsNone(validate_password(pass_8))

        # 9 chars: passes
        pass_9 = "Aa1!defgh"
        self.assertIsNone(validate_password(pass_9))

    def test_boundary_character_classes(self):
        # Missing uppercase
        err_no_upper = validate_password("aa1!defgh")
        self.assertIn("au moins une majuscule", err_no_upper)

        # Missing digit
        err_no_digit = validate_password("Aaa!defgh")
        self.assertIn("au moins un chiffre", err_no_digit)

        # Missing special character
        err_no_spec = validate_password("Aaa1defgh")
        self.assertIn("au moins un caractère spécial", err_no_spec)

    def test_accented_and_international_characters(self):
        # Uppercase accented character counts as uppercase in Python
        pass_accent_upper = "Élégant1!"
        self.assertIsNone(validate_password(pass_accent_upper))

        # Lowercase accented character only (no uppercase) must fail
        pass_accent_lower = "élégant1!"
        err = validate_password(pass_accent_lower)
        self.assertIsNotNone(err)
        self.assertIn("au moins une majuscule", err)

        # Russian / Cyrillic with uppercase and digit and special
        pass_cyrillic = "Пароль123!"
        self.assertIsNone(validate_password(pass_cyrillic))

        # Japanese with uppercase ASCII, digit, special
        pass_japanese = "Tokyo123!日本語"
        self.assertIsNone(validate_password(pass_japanese))

    def test_emoji_and_special_unicode_in_passwords(self):
        # Emojis count as special characters under [^A-Za-z0-9]
        pass_emoji = "SecureP@ss1🔒🚀"
        self.assertIsNone(validate_password(pass_emoji))

        # Werkzeug hashing round-trip with emojis
        hashed = generate_password_hash(pass_emoji)
        self.assertTrue(check_password_hash(hashed, pass_emoji))
        self.assertFalse(check_password_hash(hashed, "SecureP@ss1🔒"))

    def test_sql_injection_payloads_as_passwords(self):
        sqli_payloads = [
            "' OR '1'='1' -- A1!",
            "admin' UNION SELECT * FROM compte; -- A1!",
            "\"; DROP TABLE compte; -- A1!",
            "' OR 1=1 # A1!",
            "')) OR (('1'='1 -- A1!",
            "<script>alert(1)</script>A1!",
            "'; EXEC xp_cmdshell('dir'); -- A1!",
        ]
        for payload in sqli_payloads:
            # Each payload satisfies min length, uppercase 'A', digit '1', special char
            err = validate_password(payload)
            self.assertIsNone(err, f"Payload '{payload}' should satisfy complexity rules")

            # Hashing and verification must not crash or execute
            hashed = generate_password_hash(payload)
            self.assertTrue(check_password_hash(hashed, payload))
            self.assertFalse(check_password_hash(hashed, payload + "extra"))

    def test_extreme_password_lengths(self):
        # Very long password (5,000 chars)
        long_pass = "A1!" + "x" * 5000
        self.assertIsNone(validate_password(long_pass))
        hashed = generate_password_hash(long_pass)
        self.assertTrue(check_password_hash(hashed, long_pass))

    def test_none_and_empty_passwords(self):
        self.assertIsNotNone(validate_password(None))
        self.assertIsNotNone(validate_password(""))
        self.assertIsNotNone(validate_password("   "))


class ChangePasswordAdversarialTests(unittest.TestCase):
    """Stress tests for AuthService.change_password."""

    def setUp(self):
        self.initial_password = "CurrentPassword1!"
        self.initial_hash = generate_password_hash(self.initial_password)
        self.user = User(prenom="Alice", nom="Wonderland", mdp=self.initial_hash)
        self.storage = InMemoryUserStorage([self.user])
        self.service = AuthService(self.storage)

    def test_change_password_none_user(self):
        res = self.service.change_password(None, "CurrentPassword1!", "NewPass1!", "NewPass1!")
        self.assertFalse(res.ok)
        self.assertIn("Session expirée", res.message)

    def test_change_password_empty_inputs(self):
        # Empty current
        res1 = self.service.change_password(self.user, "", "NewPass1!", "NewPass1!")
        self.assertFalse(res1.ok)
        self.assertEqual(res1.message, "Tous les champs sont obligatoires.")

        # Empty new
        res2 = self.service.change_password(self.user, "CurrentPassword1!", "", "NewPass1!")
        self.assertFalse(res2.ok)
        self.assertEqual(res2.message, "Tous les champs sont obligatoires.")

        # Empty confirm
        res3 = self.service.change_password(self.user, "CurrentPassword1!", "NewPass1!", "")
        self.assertFalse(res3.ok)
        self.assertEqual(res3.message, "Tous les champs sont obligatoires.")

        # None inputs
        res4 = self.service.change_password(self.user, None, "NewPass1!", "NewPass1!")
        self.assertFalse(res4.ok)
        self.assertEqual(res4.message, "Tous les champs sont obligatoires.")

    def test_change_password_wrong_current_password(self):
        res = self.service.change_password(self.user, "WrongPassword99!", "NewPass1!", "NewPass1!")
        self.assertFalse(res.ok)
        self.assertEqual(res.message, "L'ancien mot de passe est incorrect.")

    def test_change_password_case_sensitive_current_password(self):
        # Case variation on old password should fail authentication
        res = self.service.change_password(self.user, "currentpassword1!", "NewPass1!", "NewPass1!")
        self.assertFalse(res.ok)
        self.assertEqual(res.message, "L'ancien mot de passe est incorrect.")

    def test_change_password_mismatched_confirmation(self):
        res = self.service.change_password(
            self.user, "CurrentPassword1!", "NewPass1!", "DifferentPass2!"
        )
        self.assertFalse(res.ok)
        self.assertEqual(res.message, "Les nouveaux mots de passe ne correspondent pas.")

    def test_change_password_trailing_whitespace_mismatch(self):
        res = self.service.change_password(
            self.user, "CurrentPassword1!", "NewPass1!", "NewPass1! "
        )
        self.assertFalse(res.ok)
        self.assertEqual(res.message, "Les nouveaux mots de passe ne correspondent pas.")

    def test_change_password_identical_to_old(self):
        res = self.service.change_password(
            self.user, "CurrentPassword1!", "CurrentPassword1!", "CurrentPassword1!"
        )
        self.assertFalse(res.ok)
        self.assertEqual(res.message, "Le nouveau mot de passe doit être différent de l'ancien.")

    def test_change_password_weak_new_password_scenarios(self):
        weak_candidates = [
            ("Short1!", "au moins 8 caractères"),
            ("nouppercase1!", "au moins une majuscule"),
            ("NoDigitsHere!", "au moins un chiffre"),
            ("NoSpecialChars1", "au moins un caractère spécial"),
        ]
        for weak_pass, expected_substr in weak_candidates:
            res = self.service.change_password(
                self.user, "CurrentPassword1!", weak_pass, weak_pass
            )
            self.assertFalse(res.ok)
            self.assertIn(expected_substr, res.message)

    def test_change_password_successful_with_sqli_payload(self):
        sqli_pass = "' OR '1'='1' -- A1!"
        res = self.service.change_password(
            self.user, "CurrentPassword1!", sqli_pass, sqli_pass
        )
        self.assertTrue(res.ok)
        self.assertEqual(res.message, "Mot de passe modifié avec succès !")

        # Verify old password no longer authenticates
        self.assertIsNone(self.storage.authenticate("Alice", "Wonderland", "CurrentPassword1!"))

        # Verify new SQLi password authenticates cleanly
        auth_new = self.storage.authenticate("Alice", "Wonderland", sqli_pass)
        self.assertIsNotNone(auth_new)
        self.assertEqual(auth_new.prenom, "Alice")

    def test_change_password_successful_with_emojis(self):
        emoji_pass = "NouveauCode123🔒🔑!"
        res = self.service.change_password(
            self.user, "CurrentPassword1!", emoji_pass, emoji_pass
        )
        self.assertTrue(res.ok)

        # Re-authenticate with emoji pass
        auth_new = self.storage.authenticate("Alice", "Wonderland", emoji_pass)
        self.assertIsNotNone(auth_new)


class DeleteAccountAdversarialTests(unittest.TestCase):
    """Stress tests for AuthService.delete_account."""

    def setUp(self):
        self.password = "ValidSecret1!"
        self.user = User(
            prenom="Bob", nom="Marley", mdp=generate_password_hash(self.password)
        )
        self.storage = InMemoryUserStorage([self.user])
        self.storage.conversations["marley.bob"] = [1, 2, 3]
        self.service = AuthService(self.storage)

    def test_delete_account_none_user(self):
        res = self.service.delete_account(None, self.password)
        self.assertFalse(res.ok)
        self.assertIn("Session expirée ou invalide.", res.message)

    def test_delete_account_empty_or_none_password(self):
        res_empty = self.service.delete_account(self.user, "")
        self.assertFalse(res_empty.ok)
        self.assertIn("obligatoire", res_empty.message)

        res_none = self.service.delete_account(self.user, None)
        self.assertFalse(res_none.ok)
        self.assertIn("obligatoire", res_none.message)

    def test_delete_account_wrong_password(self):
        res = self.service.delete_account(self.user, "WrongPass123!")
        self.assertFalse(res.ok)
        self.assertIn("Mot de passe incorrect", res.message)
        # Account still exists
        self.assertIsNotNone(self.storage.find_by_name("Bob", "Marley"))

    def test_delete_account_sqli_password_attempt(self):
        res = self.service.delete_account(self.user, "' OR '1'='1' -- A1!")
        self.assertFalse(res.ok)
        self.assertIn("Mot de passe incorrect", res.message)
        self.assertIsNotNone(self.storage.find_by_name("Bob", "Marley"))

    def test_delete_account_nonexistent_user(self):
        ghost_user = User(
            prenom="Ghost", nom="User", mdp=generate_password_hash("Secret1!")
        )
        res = self.service.delete_account(ghost_user, "Secret1!")
        self.assertFalse(res.ok)
        self.assertIn("Mot de passe incorrect", res.message)

    def test_delete_account_database_exception_resilience(self):
        self.storage.force_exception = RuntimeError("MySQL deadlock simulation")
        res = self.service.delete_account(self.user, self.password)
        self.assertFalse(res.ok)
        self.assertIn("Erreur lors de la suppression du compte", res.message)
        self.assertIn("MySQL deadlock simulation", res.message)

    def test_delete_account_success_purges_user_and_conversations(self):
        res = self.service.delete_account(self.user, self.password)
        self.assertTrue(res.ok)
        self.assertEqual(res.message, "Compte et données supprimés avec succès.")
        # User is gone
        self.assertIsNone(self.storage.find_by_name("Bob", "Marley"))
        # Conversations purged
        self.assertNotIn("marley.bob", self.storage.conversations)


class UserStorageSQLInjectionSafetyTests(unittest.TestCase):
    """Verify that UserStorage queries strictly use SQL parameterization."""

    class MockCursor:
        def __init__(self):
            self.executed = []

        def execute(self, query, params=None):
            self.executed.append((query, params))

        def fetchone(self):
            return None

    @patch("NaturSQL.storage.users.db.transaction")
    def test_update_password_is_parameterized(self, transaction_mock):
        cursor = self.MockCursor()
        from contextlib import contextmanager

        @contextmanager
        def fake_tx():
            yield cursor

        transaction_mock.side_effect = fake_tx
        storage = UserStorage()

        sqli_hash = "'; DROP TABLE compte; --"
        storage.update_password("Jean", "Dupont", sqli_hash)

        self.assertEqual(len(cursor.executed), 1)
        query, params = cursor.executed[0]
        self.assertIn("%s", query)
        self.assertNotIn("DROP TABLE", query)
        self.assertEqual(params, (sqli_hash, "Jean", "Dupont"))

    @patch("NaturSQL.storage.users.db.transaction")
    def test_delete_user_is_parameterized(self, transaction_mock):
        cursor = self.MockCursor()
        from contextlib import contextmanager

        @contextmanager
        def fake_tx():
            yield cursor

        transaction_mock.side_effect = fake_tx
        storage = UserStorage()

        sqli_name = "admin' OR '1'='1"
        storage.delete_user(sqli_name, sqli_name, sqli_name)

        self.assertEqual(len(cursor.executed), 2)
        q1, p1 = cursor.executed[0]
        q2, p2 = cursor.executed[1]

        self.assertIn("%s", q1)
        self.assertEqual(p1, (sqli_name,))
        self.assertIn("%s", q2)
        self.assertEqual(p2, (sqli_name, sqli_name))


if __name__ == "__main__":
    unittest.main()
