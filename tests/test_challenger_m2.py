import html
import unittest
from contextlib import contextmanager
from datetime import datetime
from unittest.mock import MagicMock, patch

from NaturSQL.storage.conversations import ConversationStorage
from NaturSQL.storage.users import User, UserStorage
from NaturSQL.ui_gradio import _header_user_html, _profile_card_html


class FakeCursor:
    def __init__(self, rows=None, lastrowid=1, fetchone_results=None):
        self.rows = rows or []
        self.lastrowid = lastrowid
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


class AdversarialChallenger2Tests(unittest.TestCase):
    """Adversarial stress-testing suite by Challenger 2."""

    # =========================================================================
    # 1. Conversation Rename Propagation & Cascading
    # =========================================================================

    @patch("NaturSQL.storage.users.db.transaction")
    def test_rename_propagation_multiple_conversations(self, transaction):
        """Verify rename updates all conversations belonging to user atomically."""
        cursor = FakeCursor()
        transaction.side_effect = lambda: fake_transaction(cursor)
        storage = UserStorage()

        # Suppose user has 5 existing conversations under 'dupont.jean'
        storage.update_profile(
            current_first_name="Jean",
            current_last_name="Dupont",
            first_name="Jeanne",
            last_name="Martin",
        )

        self.assertEqual(len(cursor.queries), 2)
        # Query 1: update compte
        self.assertIn("UPDATE compte", cursor.queries[0][0])
        self.assertEqual(cursor.queries[0][1], ("Martin", "Jeanne", "Jean", "Dupont"))
        # Query 2: update conversations - mass update for all conversations of dupont.jean
        self.assertIn("UPDATE conversations", cursor.queries[1][0])
        self.assertIn("SET nom_util = %s", cursor.queries[1][0])
        self.assertIn("WHERE nom_util = %s", cursor.queries[1][0])
        self.assertEqual(cursor.queries[1][1], ("martin.jeanne", "dupont.jean"))

        # Verify against in-memory SQLite engine that all 5 conversations are updated
        import sqlite3
        conn = sqlite3.connect(":memory:")
        c = conn.cursor()
        c.execute("CREATE TABLE conversations (id INT, nom_util TEXT, title TEXT)")
        for i in range(1, 6):
            c.execute("INSERT INTO conversations VALUES (?, ?, ?)", (i, "dupont.jean", f"Conv {i}"))
        conn.commit()

        # Translate MySQL query (%s) to SQLite (?) for semantic execution proof
        sqlite_query = cursor.queries[1][0].replace("%s", "?")
        c.execute(sqlite_query, cursor.queries[1][1])
        conn.commit()

        c.execute("SELECT COUNT(*) FROM conversations WHERE nom_util = 'martin.jeanne'")
        self.assertEqual(c.fetchone()[0], 5)
        c.execute("SELECT COUNT(*) FROM conversations WHERE nom_util = 'dupont.jean'")
        self.assertEqual(c.fetchone()[0], 0)

    @patch("NaturSQL.storage.users.db.transaction")
    def test_rename_propagation_identical_name_noop(self, transaction):
        """When old and new names are identical, update_profile must not run unnecessary cascade."""
        cursor = FakeCursor()
        transaction.side_effect = lambda: fake_transaction(cursor)
        storage = UserStorage()

        storage.update_profile(
            current_first_name="Jean",
            current_last_name="Dupont",
            first_name="Jean",
            last_name="Dupont",
        )

        # Compte is touched, but conversations update is skipped as no-op
        self.assertEqual(len(cursor.queries), 1)
        self.assertIn("UPDATE compte", cursor.queries[0][0])
        # Ensure conversations table was NOT touched
        for q, _ in cursor.queries:
            self.assertNotIn("UPDATE conversations", q)

    @patch("NaturSQL.storage.users.db.transaction")
    def test_rename_propagation_special_characters_and_apostrophes(self, transaction):
        """Adversarial test: names with apostrophes, hyphens, and accents (e.g., Jean-François d'Ormesson)."""
        cursor = FakeCursor()
        transaction.side_effect = lambda: fake_transaction(cursor)
        storage = UserStorage()

        current_prenom = "Jean-François"
        current_nom = "d'Ormesson"
        new_prenom = "François-Xavier"
        new_nom = "L'Hôte"

        storage.update_profile(
            current_first_name=current_prenom,
            current_last_name=current_nom,
            first_name=new_prenom,
            last_name=new_nom,
        )

        self.assertEqual(len(cursor.queries), 2)
        # Verify parameterized execution prevents SQL syntax injection / breakage on apostrophes
        compte_sql, compte_params = cursor.queries[0]
        self.assertIn("UPDATE compte", compte_sql)
        self.assertEqual(compte_params, (new_nom, new_prenom, current_prenom, current_nom))

        conv_sql, conv_params = cursor.queries[1]
        self.assertIn("UPDATE conversations", conv_sql)
        expected_old_nom_util = f"{current_nom}.{current_prenom}".lower()
        expected_new_nom_util = f"{new_nom}.{new_prenom}".lower()
        self.assertEqual(conv_params, (expected_new_nom_util, expected_old_nom_util))
        self.assertEqual(conv_params[0], "l'hôte.françois-xavier")
        self.assertEqual(conv_params[1], "d'ormesson.jean-françois")

    # =========================================================================
    # 2. Initials Calculation with Unusual Names
    # =========================================================================

    def test_initials_calculation_unusual_and_adversarial_names(self):
        """Test initials generation under empty, whitespace, single-char, hyphenated, and accented names."""
        test_cases = [
            # (prenom, nom, expected_initials, expected_full_name)
            ("", "", "U", "Utilisateur"),
            ("   ", "   ", "U", "Utilisateur"),
            ("A", "", "A", "A"),
            ("", "B", "B", "B"),
            ("X", "Y", "XY", "X Y"),
            ("  Jean-François  ", "  d'Ormesson  ", "JD", "Jean-François d'Ormesson"),
            ("Éléonore", "François", "ÉF", "Éléonore François"),
            ("élise", "zoé", "ÉZ", "élise zoé"),
            ("saint-just", "le-bon", "SL", "saint-just le-bon"),
            ("O'Connor", "D'Angelo", "OD", "O'Connor D'Angelo"),
            ("-", "-", "--", "- -"),
            ("1", "2", "12", "1 2"),
        ]

        for prenom, nom, exp_init, exp_full in test_cases:
            user = User(prenom=prenom, nom=nom, mdp="hash")
            html_out = _profile_card_html(user)
            self.assertIn("profile-avatar", html_out)
            self.assertIn(f">{html.escape(exp_init)}<", html_out, f"Failed initials for ({prenom!r}, {nom!r})")
            self.assertIn(html.escape(exp_full), html_out, f"Failed full_name for ({prenom!r}, {nom!r})")

    def test_header_user_html_initials_edge_cases(self):
        """Ensure _header_user_html never raises IndexError on empty or single-char names."""
        edge_users = [
            User(prenom="", nom="", mdp="hash"),
            User(prenom="A", nom="", mdp="hash"),
            User(prenom="", nom="B", mdp="hash"),
            User(prenom="Éléonore", nom="C", mdp="hash"),
            None,
        ]

        for u in edge_users:
            rendered = _header_user_html(u)
            if u is None:
                self.assertEqual(rendered, "")
            else:
                self.assertIsInstance(rendered, str)
                self.assertIn("display: flex", rendered)

    # =========================================================================
    # 3. get_user_activity_stats Integrity & Zero Handling
    # =========================================================================

    @patch("NaturSQL.storage.conversations.db.transaction")
    def test_get_user_activity_stats_zero_conversations_and_questions(self, transaction):
        """Verify 0 count queries return clean integers and cause no division/None errors."""
        cursor = FakeCursor(fetchone_results=[{"total_conversations": 0}, {"total_questions": 0}])
        transaction.side_effect = lambda: fake_transaction(cursor)
        storage = ConversationStorage()

        stats = storage.get_user_activity_stats("new_user.empty")
        self.assertIsInstance(stats, dict)
        self.assertEqual(stats["conversations"], 0)
        self.assertEqual(stats["questions"], 0)
        self.assertIsInstance(stats["conversations"], int)
        self.assertIsInstance(stats["questions"], int)

        # Ensure passing into profile card works seamlessly
        user = User(prenom="New", nom="User", mdp="hash")
        card = _profile_card_html(user, stats=stats)
        self.assertIn('<div class="profile-stat-value">0</div>', card)

    @patch("NaturSQL.storage.conversations.db.transaction")
    def test_get_user_activity_stats_database_nulls_and_empty_fetch(self, transaction):
        """Test DB returning NULLs or None rows."""
        # Case A: fetchone returns None for both
        cursor_none = FakeCursor(fetchone_results=[None, None])
        transaction.side_effect = lambda: fake_transaction(cursor_none)
        storage = ConversationStorage()

        stats_none = storage.get_user_activity_stats("ghost.user")
        self.assertEqual(stats_none["conversations"], 0)
        self.assertEqual(stats_none["questions"], 0)
        self.assertIsInstance(stats_none["conversations"], int)
        self.assertIsInstance(stats_none["questions"], int)

        # Case B: fetchone returns dict with None as value
        cursor_null = FakeCursor(fetchone_results=[{"total_conversations": None}, {"total_questions": None}])
        transaction.side_effect = lambda: fake_transaction(cursor_null)
        stats_null = storage.get_user_activity_stats("null.user")
        self.assertEqual(stats_null["conversations"], 0)
        self.assertEqual(stats_null["questions"], 0)
        self.assertIsInstance(stats_null["conversations"], int)
        self.assertIsInstance(stats_null["questions"], int)

    def test_profile_card_html_handles_missing_or_corrupt_stats_safely(self):
        """Ensure _profile_card_html never raises ZeroDivisionError or KeyError on irregular stats."""
        user = User(prenom="Jean", nom="Test", mdp="hash")
        # Empty stats dict
        card1 = _profile_card_html(user, stats={})
        self.assertIn("profile-stats-grid", card1)

        # Non-dict stats (e.g. None or list)
        card2 = _profile_card_html(user, stats=[])
        self.assertIn("profile-stats-grid", card2)

        # Zero stats
        card3 = _profile_card_html(user, stats={"conversations": 0, "questions": 0})
        self.assertIn("profile-stats-grid", card3)

    # =========================================================================
    # 4. HTML Escaping & XSS Payloads in _profile_card_html
    # =========================================================================

    def test_xss_injection_in_name_fields(self):
        """Adversarial XSS injections in prenom and nom must be escaped."""
        xss_payloads = [
            ("<script>alert('XSS')</script>", "Dupont"),
            ("Jean", '"><img src=x onerror=alert(1)>'),
            ("<svg/onload=alert('hello')>", "Test"),
            ("Jean", "';alert(String.fromCharCode(88,83,83))//"),
            ("<iframe src='javascript:alert(1)'>", "Hacker"),
        ]

        for prenom, nom in xss_payloads:
            user = User(prenom=prenom, nom=nom, mdp="hash")
            rendered = _profile_card_html(user)
            self.assertNotIn("<script>", rendered)
            self.assertNotIn("<img src=x onerror", rendered)
            self.assertNotIn("<svg/onload", rendered)
            self.assertNotIn("<iframe", rendered)
            self.assertIn(html.escape(user.full_name), rendered)

    def test_xss_injection_in_role_field(self):
        """Adversarial XSS injection in role attribute must fallback or escape safely."""
        user_xss_role = User(
            prenom="Jean",
            nom="Dupont",
            mdp="hash",
            role='<script>alert("role_xss")</script>',
        )
        rendered = _profile_card_html(user_xss_role)
        self.assertNotIn("<script>alert(\"role_xss\")</script>", rendered)
        # Unknown role triggers default 'PROF' badge safely
        self.assertIn("Enseignant", rendered)
        self.assertIn("badge-prof", rendered)

    def test_xss_injection_in_avatar_field(self):
        """Adversarial XSS injection in avatar URL must not break out of HTML attribute."""
        malicious_avatars = [
            '"><script>alert("avatar_xss")</script><img src="',
            '" onerror="alert(\'pwned\')" src="',
            'javascript:alert(1)',
            'data:text/html;base64,PHNjcmlwdD5hbGVydCgxKTwvc2NyaXB0Pg==',
        ]

        for bad_avatar in malicious_avatars:
            user = User(prenom="Avatar", nom="Tester", mdp="hash", avatar=bad_avatar)
            rendered = _profile_card_html(user)
            # Ensure quotes are escaped and tag cannot break out
            self.assertNotIn('<script>alert("avatar_xss")</script>', rendered)
            self.assertNotIn('" onerror="alert(\'pwned\')"', rendered)
            # Attribute quote integrity: src="..." must contain escaped quotes
            escaped_val = html.escape(bad_avatar)
            self.assertIn(f'src="{escaped_val}"', rendered)

    def test_xss_in_header_user_html(self):
        """Ensure _header_user_html also safely escapes all fields."""
        user = User(
            prenom='<script>alert("head")</script>',
            nom='"><svg onload=alert(1)>',
            mdp="hash",
            avatar='"><script>alert("avatar")</script>',
        )
        header_html = _header_user_html(user)
        self.assertNotIn("<script>", header_html)
        self.assertNotIn("<svg onload", header_html)

    # =========================================================================
    # 5. GDPR Cascade Deletion & Foreign Key Simulation
    # =========================================================================

    @patch("NaturSQL.storage.users.db.transaction")
    def test_delete_user_atomic_execution_and_cascade(self, transaction):
        """Verify delete_user deletes conversations and compte row in one atomic transaction."""
        cursor = FakeCursor()
        transaction.side_effect = lambda: fake_transaction(cursor)
        storage = UserStorage()

        storage.delete_user("Jean", "Dupont", "dupont.jean")

        self.assertEqual(len(cursor.queries), 2)
        conv_del_query, conv_del_params = cursor.queries[0]
        self.assertIn("DELETE FROM conversations WHERE nom_util = %s", conv_del_query)
        self.assertEqual(conv_del_params, ("dupont.jean",))

        compte_del_query, compte_del_params = cursor.queries[1]
        self.assertIn("DELETE FROM compte WHERE prenom = %s AND nom = %s", compte_del_query)
        self.assertEqual(compte_del_params, ("Jean", "Dupont"))

        # In-memory relational engine test simulating ON DELETE CASCADE
        import sqlite3
        conn = sqlite3.connect(":memory:")
        c = conn.cursor()
        c.execute("PRAGMA foreign_keys = ON")
        c.execute("CREATE TABLE conversations (id INT PRIMARY KEY, nom_util TEXT)")
        c.execute(
            """CREATE TABLE messages (
                id INT PRIMARY KEY,
                conversation_id INT,
                content TEXT,
                FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
            )"""
        )
        c.execute("INSERT INTO conversations VALUES (1, 'dupont.jean')")
        c.execute("INSERT INTO messages VALUES (10, 1, 'Hello')")
        c.execute("INSERT INTO messages VALUES (11, 1, 'World')")
        conn.commit()

        # Execute conversation deletion
        c.execute("DELETE FROM conversations WHERE nom_util = ?", ("dupont.jean",))
        conn.commit()

        c.execute("SELECT COUNT(*) FROM conversations WHERE nom_util = 'dupont.jean'")
        self.assertEqual(c.fetchone()[0], 0)
        c.execute("SELECT COUNT(*) FROM messages WHERE conversation_id = 1")
        self.assertEqual(c.fetchone()[0], 0)

    # =========================================================================
    # 6. Created_at Tampering & Irregular Types
    # =========================================================================

    def test_profile_card_created_at_tampering_and_types(self):
        """Ensure non-standard, string, or corrupt created_at formats degrade gracefully."""
        # ISO string format
        user_iso = User(prenom="A", nom="B", mdp="h", created_at="2026-05-15T12:00:00")
        card_iso = _profile_card_html(user_iso)
        self.assertIn("15 mai 2026", card_iso)

        # Standard MySQL datetime string format
        user_mysql = User(prenom="A", nom="B", mdp="h", created_at="2026-01-20 08:30:00")
        card_mysql = _profile_card_html(user_mysql)
        self.assertIn("20 janv. 2026", card_mysql)

        # Completely invalid string date -> degrades gracefully to current date
        user_bad_date = User(prenom="A", nom="B", mdp="h", created_at="<script>alert(1)</script>")
        card_bad = _profile_card_html(user_bad_date)
        self.assertNotIn("<script>", card_bad)
        self.assertIn("Membre depuis", card_bad)


if __name__ == "__main__":
    unittest.main()
