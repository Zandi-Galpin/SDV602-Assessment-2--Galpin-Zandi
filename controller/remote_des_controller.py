import os
import traceback

import FreeSimpleGUI as sg

from controller.background import ThreadBackground
from controller.des_controller import DesController
from data.csv_loader import load_csv
from data.database_manager import DatabaseError
from data.message_repository import ChatError
from data.session_repository import SessionError
from model.chat_feed import ChatFeed
from model.data_source import DataError

OFFLINE_STATUS = "Cannot reach the database. Retrying..."
DATABASE_UNREACHABLE = "Could not reach the database. Please try again later."
SEND_FAILED = "Your message could not be sent. Please try again."
SESSION_DELETED = "This session was deleted by its owner, so this window will close."
NO_DATA_YET = "No data uploaded yet"
UNEXPECTED_STATUS = "Something unexpected went wrong while updating."


class RemoteDesController(DesController):
    """A DES for a shared session. the local chart controls plus the
    session's data, uploads, and live chat.

    slow work runs on worker threads through self.background, and 
    the results come back to handle() as events, so many of these windows
    can be open and busy at the same time without freezing each other or the session screen.
    """

    def __init__(self, user, session, source_repository, message_repository, view=None, background=None, loader=load_csv, explorer=None):
        if view is None:
            from view.des_view import DesView
            view = DesView(f"Data Explorer - {session.name}", remote=True)
        super().__init__(explorer, view, loader)
        self.user = user
        self.session = session
        self.sources = source_repository
        self.feed = ChatFeed(message_repository, session.id)
        self.background = (background if background is not None else ThreadBackground(view))
        self.finished = False
        self.offline = False
        self.loaded_id = None
        self._polling = False
        self._loading = False
        self._unexpected_seen = False

#the interface WindowManager uses

    def open(self):
        """Show the placeholder chart, then load the sessions data and chat in the background."""
        self.view.draw(self.explorer, loading=True)
        self._start_load()
        self.tick()

    def tick(self):
        """Called like once a second. looks for new chat messages and a new data source. Only one check runs at a time."""
        if self.finished or self._polling:
            return
        self._polling = True
        self.background.submit(self._poll_job, self._poll_done)

    def is_finished(self):
        return self.finished

    def close(self):
        if not self.finished:
            self.finished = True
            self.view.close()

    def handle(self, event, values=None):
        if self.finished:
            return #a late event for a window that has already closed
        values = values or {}
        if event == "-BACKGROUND-":
            on_done, ok, value = values["-BACKGROUND-"]
            on_done(ok, value)
        elif event == sg.WIN_CLOSED:
            self.close()
        elif event == "__TIMEOUT__":
            self.tick()
        elif event == "-UPLOAD-":
            self._attempt(self._upload)
        elif event == "-APPEND-":
            self._attempt(self._append_remote)
        elif event == "-CHAT_SEND-":
            self._send(values.get("-CHAT_INPUT-", ""))
        else:
            super().handle(event) #zoom, pan and reset

    #polling 

    def _poll_job(self):
        #worker thread. The chat refresh goes last.
        source_id = self.sources.current_id(self.session.id)
        return self.feed.refresh(), source_id

    def _poll_done(self, ok, value):
        self._polling = False
        if self.finished:
            return
        if not ok:
            self._report(value, quiet=True)
            return

        if self.offline:
            self.offline = False
            self.view.show_chat_status("")
        messages, source_id = value
        if messages is not None:
            self.view.update_chat(messages)
        if (source_id is not None and source_id != self.loaded_id
                and not self._loading):
            self._start_load()

    #loading the sessions data source 

    def _start_load(self):
        self._loading = True
        if not self.explorer.has_data():
            self.view.draw(self.explorer, loading=True)
        self.background.submit(
            lambda: self.sources.load_current(self.session.id),
            self._load_done)

    def _load_done(self, ok, value):
        self._loading = False
        if self.finished:
            return
        if not ok:
            self._report(value, quiet=True)
            return
        if value is None:
            if not self.explorer.has_data():
                self.view.draw(self.explorer, message=NO_DATA_YET)
            return

        source_id, source = value
        self.loaded_id = source_id #even if unusable do not retry it
        try:
            self.explorer.set_source(source)
        except DataError as e:
            self.view.show_error(str(e))
            return
        self.view.show_status(f"Loaded {' + '.join(source.part_names)} "
                              "(shared with this session).")
        self.view.draw(self.explorer)

    #uploading 

    def _upload(self):
        path = self.view.ask_for_file("Choose a CSV file to upload")
        if not path:
            return
        self._transfer(lambda: self.loader(path), f"Uploading {os.path.basename(path)}...")

    def _append_remote(self):
        self.explorer.require_data() #fails before opening the dialog
        path = self.view.ask_for_file("Choose a CSV file to add")
        if not path:
            return
        current = self.explorer.source.copy()

        def build():
            current.append(self.loader(path))
            return current

        self._transfer(build, f"Adding {os.path.basename(path)}...")

    def _transfer(self, build, status):
        def job():
            source = build()
            """dont accept data that cant be charted BEFORE it reaches the
            server, so a bad upload cant replace a working source"""
            source.chart_data(*source.guess_chart_columns())
            return (self.sources.upload(self.session.id, source, self.user.name), source)

        self.view.show_status(status)
        self.background.submit(job, self._transfer_done)

    def _transfer_done(self, ok, value):
        if self.finished:
            return
        if not ok:
            self.view.show_status("")
            self._report(value)
            return
        source_id, source = value
        self.explorer.set_source(source)
        self.loaded_id = source_id
        self.view.show_status(f"Uploaded; everyone in this session now sees {' + '.join(source.part_names)}.")
        self.view.draw(self.explorer)

    #chat 

    def _send(self, text):
        text = text.strip()

        if not text:
            return

        if len(text) > 500:
            self.view.show_error(
                "Messages can be at most 500 characters."
            )
            return

        self.background.submit(
            lambda: self.feed.send(self.user.name, text),
            self._send_done
        )

    def _send_done(self, ok, value):
        if self.finished:
            return
        if not ok:
            if isinstance(value, DatabaseError):
                self.view.show_error(SEND_FAILED)
            else:
                self._report(value)
            return #the text stays in the box
        if value:
            self.view.clear_chat_input()
            self.tick()

    #errors 

    def _report(self, error, quiet=False):
        """Turn an exception into something the user can read. quiet=True 
        is for the background checks that run every second"""
        if isinstance(error, SessionError):
            if not self.finished:
                self.view.show_error(SESSION_DELETED)
                self.close()
        elif isinstance(error, DatabaseError):
            if not quiet:
                self.view.show_error(DATABASE_UNREACHABLE)
            elif not self.offline:
                self.offline = True
                self.view.show_chat_status(OFFLINE_STATUS)
        elif isinstance(error, (DataError, ChatError)):
            self.view.show_error(str(error))
        else:
            if not self._unexpected_seen:
                self._unexpected_seen = True
                traceback.print_exception(error)
            if quiet:
                self.view.show_chat_status(UNEXPECTED_STATUS)
            else:
                self.view.show_error("Something unexpected went wrong.")