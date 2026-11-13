import os

import FreeSimpleGUI as sg

from data.csv_loader import load_csv
from model.data_source import DataError
from model.explorer import Explorer
from model.view_window import ViewWindow


class DesController:
    """Runs a local-mode DES.
    any DataError is shown to the user instead of crashing the window."""

    def __init__(self, explorer=None, view=None, loader=load_csv):
        self.explorer = explorer if explorer is not None else Explorer()
        if view is None:
            #imported here so it doesnt pull in the GUI libraries.
            from view.des_view import DesView
            view = DesView()
        self.view = view
        self.loader = loader

    def run(self, initial_file=None):
        if initial_file:
            self._attempt(self._change_source, initial_file)
        self.view.draw(self.explorer)

        while True:
            event, _ = self.view.read()

            if event == sg.WIN_CLOSED:
                break

            self.handle(event)

        self.view.close()

    def handle(self, event):
        """do a button press, then redraw."""
        explorer = self.explorer
        view_actions = {
            "-ZOOM_IN-": explorer.zoom_in,
            "-ZOOM_OUT-": explorer.zoom_out,
            "-PAN_LEFT-": lambda: explorer.pan(-ViewWindow.PAN_STEP),
            "-PAN_RIGHT-": lambda: explorer.pan(ViewWindow.PAN_STEP),
            "-RESET-": explorer.reset_view,
        }

        if event in view_actions:
            self._attempt(view_actions[event])
        elif event == "-CHANGE_SOURCE-":
            path = self.view.ask_for_file("Choose a CSV file to open")
            self._attempt(self._change_source, path)
        elif event == "-APPEND-":
            self._attempt(self._ask_for_file_and_append)
        else:
            return

        self.view.draw(self.explorer)

    def _attempt(self, action, *args):
        """do an action, show any DataError instead of crashing."""
        try:
            action(*args)
        except DataError as e:
            self.view.show_error(str(e))

    def _change_source(self, path):
        if not path:  #if the user closed the file dialog
            return
        source = self.loader(path)
        self.explorer.set_source(source)
        self.view.show_status(f"Loaded {source.name}.")

    def _ask_for_file_and_append(self):
        self.explorer.require_data()  # failed before opening the dialog
        self._append(self.view.ask_for_file("Choose a CSV file to add"))

    def _append(self, path):
        if not path:
            return
        added = self.explorer.append_source(self.loader(path))
        self.view.show_status(
            f"Added {added} rows from {os.path.basename(path)}.")