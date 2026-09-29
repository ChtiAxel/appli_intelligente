import unittest

from NaturSQL.service.auth import AuthService, _validate_password
from NaturSQL.storage.users import User


class FakeUserStorage:
    def __init__(self, user=None):
        self.user = user
        self.created = None
        self.updated = None

    def ensure_schema(self):
        pass

    def authenticate(self, first_name, last_name, password):
        if self.user and (first_name, last_name, password) == ("Jean", "Dupont", "Secret1!"):
            return self.user
        return None

    def create_user(self, password, first_name, last_name):
        self.created = (password, first_name, last_name)
        self.user = User(first_name, last_name, "hash")
        return self.user

    def update_profile(self, current_first_name, current_last_name, first_name, last_name):
        self.updated = (current_first_name, current_last_name, first_name, last_name)

    def find_by_name(self, first_name, last_name):
        return User(first_name, last_name, "hash")


class AuthTests(unittest.TestCase):
    def test_password_validation_rules(self):
        self.assertIsNotNone(_validate_password("short"))
        self.assertIsNotNone(_validate_password("longpassword1!"))
        self.assertIsNotNone(_validate_password("Longpassword!"))
        self.assertIsNotNone(_validate_password("Longpassword1"))
        self.assertIsNone(_validate_password("Longpassword1!"))

    def test_register_validates_and_creates_user(self):
        storage = FakeUserStorage()
        result = AuthService(storage).register("Longpassword1!", "Longpassword1!", " Jean ", " Dupont ")
        self.assertTrue(result.ok)
        self.assertEqual(storage.created, ("Longpassword1!", "Jean", "Dupont"))

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


if __name__ == "__main__":
    unittest.main()