from datetime import datetime

import config
from data.database_manager import DatabaseManager
from model.session import Session

MAX_NAME_LENGTH = 60
NOT_OWNER_MESSAGE = "Only the person who created a session can delete it."


class SessionError(Exception):
    """expected session problem."""

def _to_session(document):
    return Session(str(document["_id"]), document["name"], document["owner"], document.get("public", True), document.get("created"))

class SessionRepository:
    def __init__(self, db=None):
        self.db = db if db is not None else DatabaseManager.getInstance()

    def create(self, name, owner, public=True):
        """Create a session. Names extra spaces is removed and
        must be unique within the owner's own sessions"""
        name = " ".join((name or "").split())
        if not name:
            raise SessionError("Please enter a name for the session.")
        if len(name) > MAX_NAME_LENGTH:
            raise SessionError(f"Session names can be {MAX_NAME_LENGTH} characters at most.")

        owned = self.db.find_many(config.SESSIONS_COLLECTION, {"owner": owner})
        if any(doc["name"].lower() == name.lower() for doc in owned):
            raise SessionError(f"You already have a session called '{name}'.")

        created = datetime.now()
        new_id = self.db.insert_one(config.SESSIONS_COLLECTION, {
            "name": name,
            "owner": owner,
            "public": bool(public),
            "created": created,
        })
        return Session(str(new_id), name, owner, bool(public), created)

    def list_visible(self, username):
        """Every public session plus the users own private ones sorted by name."""
        documents = self.db.find_many(
            config.SESSIONS_COLLECTION,
            {"$or": [{"public": True}, {"owner": username}]})
        sessions = [_to_session(doc) for doc in documents]
        return sorted(sessions, key=lambda s: (s.name.lower(), s.owner.lower()))

    def find(self, session_id):
        """The session with this id or None if it does not exist."""
        document = self.db.find_one_by_id(config.SESSIONS_COLLECTION, session_id)
        return _to_session(document) if document else None

    def delete(self, session_id, username):
        """Delete a session. Only its owner can."""
        deleted = self.db.delete_one_by_id(config.SESSIONS_COLLECTION, session_id, owner=username)
        if deleted:
            self.db.delete_many(config.CHAT_MESSAGES_COLLECTION, {"session_id": session_id})
            return
        if self.find(session_id) is None:
            raise SessionError("That session no longer exists.")
        raise SessionError(NOT_OWNER_MESSAGE)