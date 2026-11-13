class ChatFeed:
    """The logic of one session's chat, without any window. get the
    history only when it has changed, and send messages. A window asks it for updates and shows them."""

    def __init__(self, message_repository, session_id):
        self.messages = message_repository
        self.session_id = session_id
        self._last = None

    def refresh(self):
        """The messages, if they are different from the last refresh (always the
        first time), otherwise None."""
        messages = self.messages.all(self.session_id)
        snapshot = [(m.timestamp, m.username, m.text) for m in messages]
        if snapshot == self._last:
            return None
        self._last = snapshot
        return messages

    def send(self, username, text):
        if not (text or "").strip():
            return False
        self.messages.create_message(self.session_id, username, text)
        return True