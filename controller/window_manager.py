import FreeSimpleGUI as sg

import config


class WindowManager:
    """Runs every open window from one loop on the main thread.

    The first controller (the session screen) is the main one. when it
    finishes all the other windows are closed too. Each controller gives
    handle(event, values), tick() (called about once each second), 
    is_finished() and a view with a window.
    """

    def __init__(self, main, reader=None):
        self.main = main
        self.controllers = [main]
        self._read = reader if reader is not None else sg.read_all_windows

    def add(self, controller):
        self.controllers.append(controller)

    def find_session(self, session_id):
        """The controller for a session or None."""
        for controller in self.controllers:
            session = getattr(controller, "session", None)
            if session is not None and session.id == session_id:
                return controller
        return None

    def run(self):
        while not self.main.is_finished():
            window, event, values = self._read(timeout=config.POLL_RATE)

            if window is None:  # the timeout: nobody did anything
                for controller in list(self.controllers):
                    controller.tick()
                continue

            controller = self._controller_for(window)
            if controller is None:
                continue
            controller.handle(event, values)
            if controller.is_finished():
                self._remove(controller)

        for controller in list(self.controllers):
            self._remove(controller)

    def _controller_for(self, window):
        for controller in self.controllers:
            if controller.view.window is window:
                return controller
        return None

    def _remove(self, controller):
        self.controllers.remove(controller)
        controller.view.close()