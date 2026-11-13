"""used by tests so no window or real server is needed."""
from data.database_manager import DatabaseError


class FakeView:
    """gives a controller a list of (event, values) pairs and
    shows what the controller tries to show the user."""

    def __init__(self, events):
        self._events = list(events)
        self.errors = []
        self.messages = []
        self.closed = False

    def read(self, timeout=None):
        if not self._events:
            #real loop waits forever; fail test instead.
            raise RuntimeError("FakeView ran out of scripted events")
        return self._events.pop(0)

    def close(self):
        self.closed = True

    def hide(self):
        pass

    def un_hide(self):
        pass

    def show_error(self, message):
        self.errors.append(str(message))

    def show_message(self, message):
        self.messages.append(message)


class BrokenDatabase:
    """A database that is always unreachable. every operation fails."""

    def __getattr__(self, name):
        def fail(*args, **kwargs):
            raise DatabaseError("simulated outage")
        return fail

class SwitchableDatabase:
    """Wraps a working database that can be switched off then on to test
    what happens when the connection randomly goes away then comes back"""

    def __init__(self, database):
        self._database = database
        self.down = False

    def __getattr__(self, name):
        attribute = getattr(self._database, name)
        if not callable(attribute):
            return attribute

        def call(*args, **kwargs):
            if self.down:
                raise DatabaseError("simulated outage")
            return attribute(*args, **kwargs)
        return call