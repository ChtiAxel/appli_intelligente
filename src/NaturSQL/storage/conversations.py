"""Persistence adapter for conversation history.

Stores conversation threads and their messages in the ``appia`` database.
Each conversation belongs to a user (``nom_util``) and contains ordered
messages with roles ('user' or 'assistant').
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from NaturSQL.storage import db


@dataclass
class Conversation:
    """A conversation thread."""

    id: int
    nom_util: str
    title: str
    created_at: datetime


@dataclass
class Message:
    """A single message in a conversation."""

    id: int
    conversation_id: int
    role: str
    content: str
    sql_generated: Optional[str]
    created_at: datetime


@dataclass
class Feedback:
    """A user feedback entry for a message or conversation."""

    id: int
    conversation_id: int
    message_id: Optional[int]
    rating: int
    comment: Optional[str]
    created_at: datetime


class ConversationStorage:
    """Read/write access to ``conversations`` and ``messages`` tables."""

    def ensure_schema(self) -> None:
        """Create the conversations and messages tables if they don't exist."""
        with db.transaction() as cursor:
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS conversations (
                    id          INT AUTO_INCREMENT PRIMARY KEY,
                    nom_util    VARCHAR(50)  NOT NULL,
                    title       VARCHAR(255) NOT NULL DEFAULT 'Nouvelle conversation',
                    created_at  TIMESTAMP    DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS messages (
                    id               INT AUTO_INCREMENT PRIMARY KEY,
                    conversation_id  INT          NOT NULL,
                    role             ENUM('user', 'assistant') NOT NULL,
                    content          TEXT         NOT NULL,
                    sql_generated    TEXT,
                    created_at       TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (conversation_id)
                        REFERENCES conversations(id) ON DELETE CASCADE
                )
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS message_feedbacks (
                    id               INT AUTO_INCREMENT PRIMARY KEY,
                    conversation_id  INT          NOT NULL,
                    message_id       INT          NULL,
                    rating           TINYINT      NOT NULL,
                    comment          TEXT         NULL,
                    created_at       TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (conversation_id)
                        REFERENCES conversations(id) ON DELETE CASCADE,
                    FOREIGN KEY (message_id)
                        REFERENCES messages(id) ON DELETE CASCADE
                )
                """
            )
            try:
                cursor.execute(
                    "CREATE INDEX IF NOT EXISTS idx_conversations_nom_util ON conversations (nom_util)"
                )
            except Exception:
                pass
            try:
                cursor.execute(
                    "CREATE INDEX IF NOT EXISTS idx_messages_conversation_created "
                    "ON messages (conversation_id, created_at, id)"
                )
            except Exception:
                pass

    def create_conversation(
        self, nom_util: str, title: str = "Nouvelle conversation"
    ) -> Conversation:
        """Create a new conversation for the given user."""
        with db.transaction() as cursor:
            cursor.execute(
                "INSERT INTO conversations (nom_util, title) VALUES (%s, %s)",
                (nom_util, title[:255]),
            )
            conv_id = cursor.lastrowid
        return Conversation(
            id=conv_id,
            nom_util=nom_util,
            title=title[:255],
            created_at=datetime.now(),
        )

    def list_conversations(self, nom_util: str) -> list[Conversation]:
        """List all conversations for a user, most recent first."""
        with db.transaction() as cursor:
            cursor.execute(
                """
                SELECT id, nom_util, title, created_at
                FROM conversations
                WHERE nom_util = %s
                ORDER BY created_at DESC
                """,
                (nom_util,),
            )
            rows = cursor.fetchall()
        return [Conversation(**row) for row in rows]

    def add_message(
        self,
        conversation_id: int,
        role: str,
        content: str,
        sql_generated: Optional[str] = None,
    ) -> Message:
        """Add a message to a conversation."""
        with db.transaction() as cursor:
            cursor.execute(
                """
                INSERT INTO messages
                    (conversation_id, role, content, sql_generated)
                VALUES (%s, %s, %s, %s)
                """,
                (conversation_id, role, content, sql_generated),
            )
            msg_id = cursor.lastrowid
        return Message(
            id=msg_id,
            conversation_id=conversation_id,
            role=role,
            content=content,
            sql_generated=sql_generated,
            created_at=datetime.now(),
        )

    def get_messages(self, conversation_id: int) -> list[Message]:
        """Get all messages for a conversation, oldest first."""
        with db.transaction() as cursor:
            cursor.execute(
                """
                SELECT id, conversation_id, role, content, sql_generated, created_at
                FROM messages
                WHERE conversation_id = %s
                ORDER BY created_at ASC
                """,
                (conversation_id,),
            )
            rows = cursor.fetchall()
        return [Message(**row) for row in rows]

    def rename_conversation(self, conversation_id: int, new_title: str) -> bool:
        """Rename a conversation."""
        clean_title = (new_title or "").strip()[:255]
        if not clean_title:
            return False
        with db.transaction() as cursor:
            cursor.execute(
                "UPDATE conversations SET title = %s WHERE id = %s",
                (clean_title, conversation_id),
            )
            return cursor.rowcount > 0

    def delete_conversation(self, conversation_id: int) -> bool:
        """Delete a conversation and its cascaded messages."""
        with db.transaction() as cursor:
            cursor.execute("DELETE FROM conversations WHERE id = %s", (conversation_id,))
            return cursor.rowcount > 0

    def delete_all_conversations(self, nom_util: str) -> bool:
        """Delete all conversations and cascaded messages for a user."""
        with db.transaction() as cursor:
            cursor.execute("DELETE FROM conversations WHERE nom_util = %s", (nom_util,))
            return cursor.rowcount > 0

    def add_feedback(
        self,
        conversation_id: int,
        rating: int,
        message_id: Optional[int] = None,
        comment: Optional[str] = None,
    ) -> int:
        """Record user feedback (rating: +1 or -1, optional comment) for a message/conversation."""
        with db.transaction() as cursor:
            cursor.execute(
                """
                INSERT INTO message_feedbacks
                    (conversation_id, message_id, rating, comment)
                VALUES (%s, %s, %s, %s)
                """,
                (conversation_id, message_id, rating, comment),
            )
            return cursor.lastrowid

    def get_feedbacks(self, conversation_id: int) -> list[Feedback]:
        """Get all feedbacks recorded for a conversation."""
        with db.transaction() as cursor:
            cursor.execute(
                """
                SELECT id, conversation_id, message_id, rating, comment, created_at
                FROM message_feedbacks
                WHERE conversation_id = %s
                ORDER BY created_at ASC
                """,
                (conversation_id,),
            )
            rows = cursor.fetchall()
        return [Feedback(**row) for row in rows]

    def get_last_exchange(
        self, conversation_id: int
    ) -> tuple[Optional[Message], Optional[Message]]:
        """Return (original_user_message, last_assistant_message) before any trailing correction."""
        messages = self.get_messages(conversation_id)
        last_assistant: Optional[Message] = None
        assistant_index = -1
        for i in range(len(messages) - 1, -1, -1):
            if messages[i].role == "assistant":
                last_assistant = messages[i]
                assistant_index = i
                break
        if last_assistant is None:
            return None, None
        original_user: Optional[Message] = None
        for i in range(assistant_index - 1, -1, -1):
            if messages[i].role == "user":
                original_user = messages[i]
                break
        return original_user, last_assistant
    def get_user_activity_stats(self, nom_util: str) -> dict[str, int]:
        """Retrieve activity counts (total conversations and total user questions) for a user."""
        with db.transaction() as cursor:
            cursor.execute(
                "SELECT COUNT(*) AS total_conversations FROM conversations WHERE nom_util = %s",
                (nom_util,),
            )
            row_conv = cursor.fetchone()
            conv_count = 0
            if row_conv:
                if isinstance(row_conv, dict):
                    conv_count = row_conv.get("total_conversations") or 0
                elif isinstance(row_conv, (list, tuple)) and len(row_conv) > 0:
                    conv_count = row_conv[0] or 0

            cursor.execute(
                """
                SELECT COUNT(*) AS total_questions
                FROM messages m
                INNER JOIN conversations c ON m.conversation_id = c.id
                WHERE c.nom_util = %s AND m.role = 'user'
                """,
                (nom_util,),
            )
            row_questions = cursor.fetchone()
            question_count = 0
            if row_questions:
                if isinstance(row_questions, dict):
                    question_count = row_questions.get("total_questions") or 0
                elif isinstance(row_questions, (list, tuple)) and len(row_questions) > 0:
                    question_count = row_questions[0] or 0

        return {
            "conversations": int(conv_count or 0),
            "questions": int(question_count or 0),
            "total_conversations": int(conv_count or 0),
            "total_questions": int(question_count or 0),
            "conversations_count": int(conv_count or 0),
            "questions_count": int(question_count or 0),
        }

    get_user_stats = get_user_activity_stats

    def get_full_user_history(self, nom_util: str) -> list[dict]:
        """Retrieve all conversations and their ordered messages for RGPD data export."""
        with db.transaction() as cursor:
            cursor.execute(
                """
                SELECT c.id AS conversation_id, c.title AS conversation_title,
                       c.created_at AS conversation_created_at,
                       m.id AS message_id, m.role, m.content, m.sql_generated,
                       m.created_at AS message_created_at
                FROM conversations c
                LEFT JOIN messages m ON m.conversation_id = c.id
                WHERE c.nom_util = %s
                ORDER BY c.created_at DESC, c.id DESC,
                         m.created_at ASC, m.id ASC
                """,
                (nom_util,),
            )
            rows = cursor.fetchall()

        history_by_id: dict[int, dict] = {}
        for row in rows:
            conversation_id = row["conversation_id"]
            conversation = history_by_id.setdefault(
                conversation_id,
                {
                    "conversation_id": conversation_id,
                    "title": row["conversation_title"],
                    "created_at": (
                        row["conversation_created_at"].isoformat()
                        if row["conversation_created_at"]
                        else None
                    ),
                    "messages": [],
                },
            )
            if row["message_id"] is not None:
                conversation["messages"].append(
                    {
                        "id": row["message_id"],
                        "role": row["role"],
                        "content": row["content"],
                        "sql_generated": row["sql_generated"],
                        "created_at": (
                            row["message_created_at"].isoformat()
                            if row["message_created_at"]
                            else None
                        ),
                    }
                )
        return list(history_by_id.values())
        return list(history_by_id.values())
