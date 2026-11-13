from data.database_manager import DatabaseManager
from datetime import datetime, timezone
import config

from model.chat_message import ChatMessage

MAX_MESSAGE_LENGTH = 500
HISTORY_LIMIT = 200


class ChatError(Exception):
    """An expected chat problem."""


class MessageRepository:
    def __init__(self, db=None):
        self.db = db if db is not None else DatabaseManager.getInstance()


    def create_message(self, session_id, username, text):
        """Store a message in a sessions chat. The text is trimmed. blank
        or too long message is refused."""
        text = (text or "").strip()
        if not text:
            raise ChatError("Type a message first.")
        if len(text) > MAX_MESSAGE_LENGTH:
            raise ChatError(f"Messages can be {MAX_MESSAGE_LENGTH} characters max.")

        #stored as UTC so the order is right even if two machines have diff timezones
        return self.db.insert_one(config.CHAT_MESSAGES_COLLECTION, {
            "session_id": session_id,
            "username": username,
            "text": text,
            "timestamp": datetime.now(timezone.utc),
        })

    def all(self, session_id, limit=HISTORY_LIMIT):
        """The most recent messages of one session, oldest first. if
        times are the same then sort by id"""
        documents = self.db.find_many(
            config.CHAT_MESSAGES_COLLECTION, {"session_id": session_id},
            sort=[("timestamp", -1), ("_id", -1)], limit=limit)
        documents.reverse()
        return [ChatMessage(doc["username"], doc["text"], doc["timestamp"]) for doc in documents]

    def delete_for_session(self, session_id):
        """Remove every message of a session. Returns how many."""
        return self.db.delete_many(config.CHAT_MESSAGES_COLLECTION, {"session_id": session_id})
