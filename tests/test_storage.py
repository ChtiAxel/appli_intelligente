import unittest
import hashlib
from contextlib import contextmanager
from datetime import datetime
from unittest.mock import patch

from werkzeug.security import generate_password_hash

from NaturSQL.storage.conversations import ConversationStorage
from NaturSQL.storage.users import UserStorage


class FakeCursor:
    def __init__(self, rows=None, lastrowid=1):
        self.rows = rows or []
        self.lastrowid = lastrowid
        self.queries = []

    def execute(self, query, params=None):
        self.queries.append((query, params))

    def fetchone(self):
        return self.rows[0] if self.rows else None

    def fetchall(self):
        return self.rows


def fake_transaction(cursor):
    @contextmanager
    def transaction():
        yield cursor
    return transaction()


class StorageTests(unittest.TestCase):
    def test_user_model_properties_and_hash_verification(self):
        user = UserStorage._row_to_user({"prenom": "Jean", "nom": "Dupont", "mdp": "hash"})
        self.assertEqual(user.full_name, "Jean Dupont")
        self.assertEqual(user.nom_util, "dupont.jean")
        self.assertFalse(UserStorage._verify_password("secret", ""))
        legacy_hash = hashlib.md5(b"secret").hexdigest()
        self.assertTrue(UserStorage._verify_password("secret", legacy_hash))
        self.assertTrue(UserStorage._verify_password("secret", generate_password_hash("secret")))

    @patch("NaturSQL.storage.users.db.transaction")
    def test_user_storage_queries_and_registration(self, transaction):
        cursor = FakeCursor([{"prenom": "Jean", "nom": "Dupont", "mdp": "hash"}])
        transaction.side_effect = lambda: fake_transaction(cursor)
        storage = UserStorage()
        storage.ensure_schema()
        self.assertEqual(storage.find_by_name("Jean", "Dupont").full_name, "Jean Dupont")
        self.assertEqual(storage.authenticate("Jean", "Dupont", "wrong"), None)
        created = storage.create_user("Secret1!", "Alice", "Martin")
        self.assertEqual(created.full_name, "Alice Martin")
        storage.update_profile("Jean", "Dupont", "Jeanne", "Martin")
        self.assertGreaterEqual(len(cursor.queries), 5)

    @patch("NaturSQL.storage.db.get_connection")
    def test_database_transaction_commits_and_rolls_back(self, get_connection):
        class FakeConnection:
            def __init__(self):
                self.cursor_obj = FakeCursor()
                self.committed = False
                self.rolled_back = False
                self.closed = False

            def cursor(self):
                return self

            def __enter__(self):
                return self.cursor_obj

            def __exit__(self, *args):
                return False

            def commit(self):
                self.committed = True

            def rollback(self):
                self.rolled_back = True

            def close(self):
                self.closed = True

        connection = FakeConnection()
        get_connection.return_value = connection
        from NaturSQL.storage import db

        with db.transaction():
            pass
        self.assertTrue(connection.committed)
        self.assertTrue(connection.closed)

        connection.committed = False
        with self.assertRaises(RuntimeError):
            with db.transaction():
                raise RuntimeError("failure")
        self.assertTrue(connection.rolled_back)

    @patch("NaturSQL.storage.conversations.db.transaction")
    def test_conversation_storage_crud(self, transaction):
        now = datetime.now()
        cursor = FakeCursor([{"id": 1, "nom_util": "dupont.jean", "title": "Test", "created_at": now}])
        transaction.side_effect = lambda: fake_transaction(cursor)
        storage = ConversationStorage()
        conversation = storage.create_conversation("dupont.jean", "x" * 300)
        self.assertEqual(len(conversation.title), 255)
        self.assertEqual(storage.list_conversations("dupont.jean")[0].id, 1)

        cursor.rows = [{"id": 2, "conversation_id": 1, "role": "user", "content": "Hello", "sql_generated": None, "created_at": now}]
        message = storage.add_message(1, "user", "Hello")
        self.assertEqual(message.content, "Hello")
        self.assertEqual(storage.get_messages(1)[0].role, "user")

    def test_base_storage_health_check(self):
        from NaturSQL.storage.base import Storage
        self.assertTrue(Storage().health_check())


if __name__ == "__main__":
    unittest.main()