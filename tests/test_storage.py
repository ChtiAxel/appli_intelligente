import unittest
import hashlib
from contextlib import contextmanager
from datetime import datetime
from unittest.mock import patch

from werkzeug.security import generate_password_hash

from NaturSQL.storage.conversations import ConversationStorage
from NaturSQL.storage.users import User, UserStorage


class FakeCursor:
    def __init__(self, rows=None, lastrowid=1, rowcount=1, fetchone_results=None):
        self.rows = rows or []
        self.lastrowid = lastrowid
        self.rowcount = rowcount
        self.queries = []
        self.fetchone_results = list(fetchone_results) if fetchone_results is not None else None

    def execute(self, query, params=None):
        self.queries.append((query, params))

    def fetchone(self):
        if self.fetchone_results is not None:
            return self.fetchone_results.pop(0) if self.fetchone_results else None
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

        self.assertTrue(storage.rename_conversation(1, "Nouveau Titre"))
        self.assertFalse(storage.rename_conversation(1, "   "))
        self.assertTrue(storage.delete_conversation(1))
        self.assertTrue(storage.delete_all_conversations("dupont.jean"))

    @patch("NaturSQL.storage.conversations.db.transaction")
    def test_get_full_user_history_uses_one_query(self, transaction):
        now = datetime.now()
        cursor = FakeCursor(
            [
                {
                    "conversation_id": 2,
                    "conversation_title": "Recent",
                    "conversation_created_at": now,
                    "message_id": 3,
                    "role": "user",
                    "content": "Bonjour",
                    "sql_generated": None,
                    "message_created_at": now,
                },
                {
                    "conversation_id": 2,
                    "conversation_title": "Recent",
                    "conversation_created_at": now,
                    "message_id": 4,
                    "role": "assistant",
                    "content": "Bonjour !",
                    "sql_generated": "SELECT 1",
                    "message_created_at": now,
                },
                {
                    "conversation_id": 1,
                    "conversation_title": "Empty",
                    "conversation_created_at": now,
                    "message_id": None,
                    "role": None,
                    "content": None,
                    "sql_generated": None,
                    "message_created_at": None,
                },
            ]
        )
        transaction.side_effect = lambda: fake_transaction(cursor)

        history = ConversationStorage().get_full_user_history("dupont.jean")

        self.assertEqual(len(cursor.queries), 1)
        self.assertIn("LEFT JOIN messages", cursor.queries[0][0])
        self.assertEqual([item["conversation_id"] for item in history], [2, 1])
        self.assertEqual(len(history[0]["messages"]), 2)
        self.assertEqual(history[1]["messages"], [])

    def test_base_storage_health_check(self):
        from NaturSQL.storage.base import Storage
        self.assertTrue(Storage().health_check())

    def test_user_dataclass_and_row_to_user_defaults_and_custom(self):
        # Default values check
        u_default = User("Alice", "Martin", "secret_hash")
        self.assertEqual(u_default.prenom, "Alice")
        self.assertEqual(u_default.nom, "Martin")
        self.assertEqual(u_default.mdp, "secret_hash")
        self.assertEqual(u_default.role, "PROF")
        self.assertIsNone(u_default.avatar)
        self.assertIsNone(u_default.created_at)
        self.assertEqual(u_default.nom_util, "martin.alice")
        self.assertEqual(u_default.full_name, "Alice Martin")

        # Custom values check
        dt = datetime(2026, 10, 12, 14, 30)
        u_custom = User("Bob", "Dylan", "hash", role="ADMIN", avatar="bob.jpg", created_at=dt)
        self.assertEqual(u_custom.role, "ADMIN")
        self.assertEqual(u_custom.avatar, "bob.jpg")
        self.assertEqual(u_custom.created_at, dt)

        # _row_to_user default fallback
        row_min = {"prenom": "Claire", "nom": "Dupuis", "mdp": "h"}
        u_from_row = UserStorage._row_to_user(row_min)
        self.assertEqual(u_from_row.role, "PROF")
        self.assertIsNone(u_from_row.avatar)
        self.assertIsNone(u_from_row.created_at)

        # _row_to_user with None role fallback
        row_none = {"prenom": "Claire", "nom": "Dupuis", "mdp": "h", "role": None}
        self.assertEqual(UserStorage._row_to_user(row_none).role, "PROF")

        # _row_to_user custom values
        row_full = {
            "prenom": "Diana",
            "nom": "Prince",
            "mdp": "h_full",
            "role": "SECRETAIRE",
            "avatar": "diana.png",
            "created_at": dt,
        }
        u_full = UserStorage._row_to_user(row_full)
        self.assertEqual(u_full.role, "SECRETAIRE")
        self.assertEqual(u_full.avatar, "diana.png")
        self.assertEqual(u_full.created_at, dt)

    @patch("NaturSQL.storage.users.db.transaction")
    def test_update_profile_propagates_to_conversations_atomically(self, transaction):
        cursor = FakeCursor()
        transaction.side_effect = lambda: fake_transaction(cursor)
        storage = UserStorage()

        # When name changes, updates both compte and conversations
        storage.update_profile("Jean", "Dupont", "Jeanne", "Martin")
        self.assertEqual(len(cursor.queries), 2)
        self.assertIn("UPDATE compte", cursor.queries[0][0])
        self.assertEqual(cursor.queries[0][1], ("Martin", "Jeanne", "Jean", "Dupont"))
        self.assertIn("UPDATE conversations", cursor.queries[1][0])
        self.assertEqual(cursor.queries[1][1], ("martin.jeanne", "dupont.jean"))

        # When name stays the same, conversations table is not updated
        cursor.queries.clear()
        storage.update_profile("Jean", "Dupont", "Jean", "Dupont")
        self.assertEqual(len(cursor.queries), 1)
        self.assertIn("UPDATE compte", cursor.queries[0][0])

    @patch("NaturSQL.storage.users.db.transaction")
    def test_update_password(self, transaction):
        cursor = FakeCursor()
        transaction.side_effect = lambda: fake_transaction(cursor)
        storage = UserStorage()
        storage.update_password("Jean", "Dupont", "argon2_new_hash")
        self.assertEqual(len(cursor.queries), 1)
        self.assertIn("UPDATE compte", cursor.queries[0][0])
        self.assertIn("mdp = %s", cursor.queries[0][0])
        self.assertEqual(cursor.queries[0][1], ("argon2_new_hash", "Jean", "Dupont"))

    @patch("NaturSQL.storage.users.db.transaction")
    def test_delete_user_cascades_conversations_and_compte(self, transaction):
        cursor = FakeCursor()
        transaction.side_effect = lambda: fake_transaction(cursor)
        storage = UserStorage()

        # Explicit nom_util
        storage.delete_user("Jean", "Dupont", "dupont.jean")
        self.assertEqual(len(cursor.queries), 2)
        self.assertIn("DELETE FROM conversations", cursor.queries[0][0])
        self.assertEqual(cursor.queries[0][1], ("dupont.jean",))
        self.assertIn("DELETE FROM compte", cursor.queries[1][0])
        self.assertEqual(cursor.queries[1][1], ("Jean", "Dupont"))

        # Automatic nom_util derivation and delete_account alias
        cursor.queries.clear()
        storage.delete_account("Alice", "Smith")
        self.assertEqual(len(cursor.queries), 2)
        self.assertEqual(cursor.queries[0][1], ("smith.alice",))
        self.assertEqual(cursor.queries[1][1], ("Alice", "Smith"))

    @patch("NaturSQL.storage.users.db.transaction")
    def test_update_avatar(self, transaction):
        cursor = FakeCursor()
        transaction.side_effect = lambda: fake_transaction(cursor)
        storage = UserStorage()
        storage.update_avatar("Jean", "Dupont", "avatar_123.png")
        self.assertEqual(len(cursor.queries), 1)
        self.assertIn("UPDATE compte", cursor.queries[0][0])
        self.assertIn("avatar = %s", cursor.queries[0][0])
        self.assertEqual(cursor.queries[0][1], ("avatar_123.png", "Jean", "Dupont"))

    @patch("NaturSQL.storage.conversations.db.transaction")
    def test_get_user_activity_stats(self, transaction):
        cursor = FakeCursor(fetchone_results=[{"total_conversations": 4}, {"total_questions": 15}])
        transaction.side_effect = lambda: fake_transaction(cursor)
        storage = ConversationStorage()

        stats = storage.get_user_activity_stats("dupont.jean")
        self.assertEqual(stats["conversations"], 4)
        self.assertEqual(stats["questions"], 15)
        self.assertEqual(stats["total_conversations"], 4)
        self.assertEqual(stats["total_questions"], 15)
        self.assertEqual(stats["conversations_count"], 4)
        self.assertEqual(stats["questions_count"], 15)

        self.assertEqual(len(cursor.queries), 2)
        self.assertIn("FROM conversations WHERE nom_util = %s", cursor.queries[0][0])
        self.assertEqual(cursor.queries[0][1], ("dupont.jean",))
        self.assertIn("FROM messages m", cursor.queries[1][0])
        self.assertIn("m.role = 'user'", cursor.queries[1][0])
        self.assertEqual(cursor.queries[1][1], ("dupont.jean",))

        # Test empty result handling
        cursor_empty = FakeCursor(fetchone_results=[None, None])
        transaction.side_effect = lambda: fake_transaction(cursor_empty)
        stats_empty = storage.get_user_activity_stats("nobody")
        self.assertEqual(stats_empty["conversations"], 0)
        self.assertEqual(stats_empty["questions"], 0)

        # Test tuple rows handling
        cursor_tuple = FakeCursor(fetchone_results=[(7,), (21,)])
        transaction.side_effect = lambda: fake_transaction(cursor_tuple)
        stats_tuple = storage.get_user_activity_stats("tuple.user")
        self.assertEqual(stats_tuple["conversations"], 7)
        self.assertEqual(stats_tuple["questions"], 21)


if __name__ == "__main__":
    unittest.main()