import FreeSimpleGUI as sg

from data.database_manager import DatabaseError
from data.session_repository import NOT_OWNER_MESSAGE, SessionError

DATABASE_UNREACHABLE = "Could not reach the database. Please try again later."
NOTHING_SELECTED = "Select a session first."

class SessionController:
    """Runs the session management screen for a logged in user. can browse,
    create, join and delete sessions"""

    def __init__(self, user, session_repository, on_join, view=None):
        self.user = user
        self.session_repository = session_repository
        self.on_join = on_join
        if view is None:
            from view.session_view import SessionView
            view = SessionView(user.name)
        self.view = view
        self.sessions = []#the sessions currently shown, in row order

    def run(self):
        """Run until the user logs out or closes the window"""
        self._attempt(self._refresh)

        while True:
            event, values = self.view.read()

            if event == sg.WIN_CLOSED:
                result = "closed"
                break
            if event == "-LOGOUT-":
                result = "logout"
                break

            self.handle(event, values)

        self.view.close()
        return result

    def handle(self, event, values):
        if event == "-TABLE-":
            self._update_buttons(values)
        elif event == "-REFRESH-":
            self._attempt(self._refresh)
        elif event == "-CREATE-":
            self._attempt(self._create, values)
        elif event == "-JOIN-":
            self._attempt(self._join, values)
        elif event == "-DELETE-":
            self._attempt(self._delete, values)

    def _attempt(self, action, *args):
        """Run an action, showing a message instead of crashing."""
        try:
            action(*args)
        except SessionError as e:
            self.view.show_error(str(e))
        except DatabaseError:
            self.view.show_error(DATABASE_UNREACHABLE)

    def _refresh(self):
        self.sessions = self.session_repository.list_visible(self.user.name)
        rows = [[s.name,
                 s.owner + (" (you)" if s.is_owned_by(self.user.name) else ""),
                 "Public" if s.public else "Private"]
                for s in self.sessions]
        self.view.show_sessions(rows)
        self.view.set_buttons(False, False)

    def _selected(self, values):
        """The session whose row is selected, or None."""
        chosen = values.get("-TABLE-") or []
        if chosen and 0 <= chosen[0] < len(self.sessions):
            return self.sessions[chosen[0]]
        return None

    def _update_buttons(self, values):
        selected = self._selected(values)
        self.view.set_buttons(
            selected is not None,
            selected is not None and selected.is_owned_by(self.user.name))

    def _create(self, values):
        session = self.session_repository.create(
            values.get("-NEW_NAME-", ""), self.user.name,
            public=not values.get("-PRIVATE-", False))
        self.view.clear_new_name()
        self.view.show_status(f"Created '{session.name}'.")
        self._refresh()

    def _join(self, values):
        selected = self._selected(values)
        if selected is None:
            raise SessionError(NOTHING_SELECTED)

        #look it up again, it could have been deleted or changed since the list was drawn.
        current = self.session_repository.find(selected.id)
        if current is None:
            self._refresh()
            raise SessionError("That session no longer exists.")
        if not current.is_visible_to(self.user.name):
            self._refresh()
            raise SessionError("That session is private.")

        self.on_join(current, self.user)

    def _delete(self, values):
        selected = self._selected(values)
        if selected is None:
            raise SessionError(NOTHING_SELECTED)
        if not selected.is_owned_by(self.user.name):
            raise SessionError(NOT_OWNER_MESSAGE)
        if not self.view.confirm_delete(selected.name):
            return

        self.session_repository.delete(selected.id, self.user.name)
        self.view.show_status(f"Deleted '{selected.name}'.")
        self._refresh()