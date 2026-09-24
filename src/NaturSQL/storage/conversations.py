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
