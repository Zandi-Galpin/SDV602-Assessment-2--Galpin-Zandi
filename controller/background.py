import threading


class ThreadBackground:
    """Runs jobs on worker threads and reports each result back to the window as an event"""

    def __init__(self, view):
        self.view = view

    def submit(self, job, on_done):
        """Run job() on a new thread. When it finishes, on_done(ok, value)
        is called on the GUI thread. value is the result (if ok), otherwise
        value is the exception that was raised."""
        def work():
            try:
                outcome = (True, job())
            except Exception as error:
                outcome = (False, error)
            try:
                self.view.post("-BACKGROUND-", (on_done, *outcome))
            except Exception:
                pass

        threading.Thread(target=work, daemon=True).start()


class ImmediateBackground:
    """Used by the headless tests where there is no window to report back to."""

    def submit(self, job, on_done):
        try:
            outcome = (True, job())
        except Exception as error:
            outcome = (False, error)
        on_done(*outcome)