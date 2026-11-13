import FreeSimpleGUI as sg

import config
from data.database_manager import DatabaseError
from data.message_repository import ChatError
from model.chat_feed import ChatFeed

OFFLINE_STATUS = "Can't reach the database. Retrying..."
SEND_FAILED = "Your message could not be sent. Please try again."


class ChatController:
    """Runs the chat window for one session. The window is redrawn
    when the messages change, and a database outage shows one status 
    and clears itself when the connection comes back."""

    def __init__(self, username, message_repository, session, view=None):
        self.username = username
        self.session = session
        self.feed = ChatFeed(message_repository, session.id)
        if view is None:
            from view.chat_view import ChatView
            view = ChatView(f"Chat - {session.name}")
        self.view = view
        self.offline = False

    def run(self):
        self._refresh()

        while True:
            event, values = self.view.read(timeout=config.POLL_RATE)

            if event == sg.WIN_CLOSED:
                break
            if event == "__TIMEOUT__":
                self._refresh()
            elif event == "Send":
                self._send(values.get("-CHAT-", ""))

        self.view.close()

    def _refresh(self):
        try:
            messages = self.feed.refresh()
        except DatabaseError:
            if not self.offline:
                self.offline = True
                self.view.show_status(OFFLINE_STATUS)
            return

        if self.offline:
            self.offline = False
            self.view.show_status("")
        if messages is not None:
            self.view.update_messages(messages)

    def _send(self, text):
        try:
            sent = self.feed.send(self.username, text)
        except ChatError as e:
            self.view.show_error(str(e))
            return #the text stays in the box so it can be edited
        except DatabaseError:
            self.view.show_error(SEND_FAILED)
            return

        if sent:
            self.view.clear_input()
            self._refresh()