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
            try:
                cursor.execute(
                    "CREATE INDEX IF NOT EXISTS idx_conversations_nom_util ON conversations (nom_util)"
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
        convs = self.list_conversations(nom_util)
        history = []
        for c in convs:
            msgs = self.get_messages(c.id)
            history.append({
                "conversation_id": c.id,
                "title": c.title,
                "created_at": c.created_at.isoformat() if c.created_at else None,
                "messages": [
                    {
                        "id": m.id,
                        "role": m.role,
                        "content": m.content,
                        "sql_generated": m.sql_generated,
                        "created_at": m.created_at.isoformat() if m.created_at else None,
                    }
                    for m in msgs
                ],
            })
        return history
