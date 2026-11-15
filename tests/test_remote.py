"""Tests for the remote DES without opening any windows.

Covers saved data, background tasks, the remote des controller,
two users sharing a session, the window manager, the session screen,
"""
import threading
import traceback
from types import SimpleNamespace

import FreeSimpleGUI as sg

from controller import remote_des_controller as rdc
from controller.background import ImmediateBackground, ThreadBackground
from controller.remote_des_controller import RemoteDesController
from controller.session_controller import SessionController
from controller.window_manager import WindowManager
from data.data_source_repository import MAX_ROWS, DataSourceRepository
from data.database_manager import DatabaseError, DatabaseManager
from data.message_repository import MessageRepository
from data.session_repository import SessionError, SessionRepository
from model.data_source import DataError, DataSource
from model.user import User
from tests.fakes import BrokenDatabase, SwitchableDatabase
from tests.helpers import reset_database
from tests.test_local_mode import write_temp_csv

FIRST = "Period,Count,Type\n2010,50,Births\n2010,40,Deaths\n" \
        "2011,55,Births\n2011,45,Deaths\n"
SECOND = "Period,Count,Type\n2012,60,Births\n2012,48,Deaths\n"
WRONG_COLUMNS = "Period,Other\n2012,1\n"
NO_NUMBERS = "Name,Colour\nx,red\n"


# test helpers

def make_sample_data(name="a.csv"):
    """Create a small example data file."""
    rows = [{"Period": "2010", "Count": "50", "Type": "Births"},
            {"Period": "2010", "Count": "40", "Type": "Deaths"}]
    return DataSource(name, ["Period", "Count", "Type"], rows)


def make_session(owner="alex"):
    """Create a fresh test database and session."""
    reset_database()
    sessions = SessionRepository()
    return sessions, sessions.create("Shared", owner)


def check_error(error_type, func, fragment=""):
    """Check that the expected error is shown."""
    try:
        func()
    except error_type as e:
        assert fragment in str(e), f"expected '{fragment}' in '{e}'"
        return
    raise AssertionError(f"no {error_type.__name__} raised")


class FakeRemoteView:
    """A pretend remote des window that records what is displayed."""

    def __init__(self, files=()):
        self._files = list(files)
        self.window = object()
        self.draws = []
        self.statuses = []
        self.errors = []
        self.chat_updates = []
        self.chat_statuses = []
        self.chat_cleared = 0
        self.asked = []
        self.closed = 0

    def draw(self, explorer, loading=False, message=None):
        self.draws.append((explorer.has_data(), loading, message))

    def ask_for_file(self, prompt):
        self.asked.append(prompt)
        return self._files.pop(0) if self._files else ""

    def show_status(self, text):
        self.statuses.append(text)

    def update_chat(self, messages):
        self.chat_updates.append([(m.username, m.text) for m in messages])

    def clear_chat_input(self):
        self.chat_cleared += 1

    def show_chat_status(self, text):
        self.chat_statuses.append(text)

    def show_error(self, message):
        self.errors.append(str(message))

    def close(self):
        self.closed += 1


class ManualBackground:
    """Hold background tasks until the test chooses to run them."""

    def __init__(self):
        self.pending = []

    def submit(self, job, on_done):
        self.pending.append((job, on_done))

    def run_all(self):
        while self.pending:
            job, on_done = self.pending.pop(0)
            try:
                outcome = (True, job())
            except Exception as error:
                outcome = (False, error)
            on_done(*outcome)


def open_remote_des(user, session, files=(), db=None, background=None):
    """open a pretend remote DES window for a user."""
    view = FakeRemoteView(files)
    controller = RemoteDesController(
        User(user, b"h"), session, DataSourceRepository(db),
        MessageRepository(db), view,
        background if background is not None else ImmediateBackground())
    controller.open()
    return controller, view


def make_csv(text, name="data.csv"):
    """Create a csv file for testing."""
    return write_temp_csv(text, name=name)


# saved data tests

def test_saved_data_can_be_loaded_again():
    sessions, session = make_session()
    sources = DataSourceRepository()
    source_id = sources.upload(session.id, make_sample_data(), "alex")
    assert sources.current_id(session.id) == source_id
    loaded_id, loaded = sources.load_current(session.id)
    assert loaded_id == source_id
    assert loaded.name == "a.csv" and loaded.columns == make_sample_data().columns
    assert loaded.rows == make_sample_data().rows


def test_saved_data_keeps_blank_values_and_column_order():
    sessions, session = make_session()
    sources = DataSourceRepository()
    messy = DataSource("m.csv", ["B", "A"], [{"A": "1"}, {"B": "x", "A": ""}])
    sources.upload(session.id, messy, "alex")
    loaded = sources.load_current(session.id)[1]
    assert loaded.columns == ["B", "A"], loaded.columns
    assert loaded.rows == [{"B": "", "A": "1"}, {"B": "x", "A": ""}]


def test_merged_files_keep_their_original_names():
    sessions, session = make_session()
    sources = DataSourceRepository()
    merged = make_sample_data("a.csv")
    merged.append(make_sample_data("b.csv"))
    sources.upload(session.id, merged, "alex")
    assert sources.load_current(session.id)[1].part_names == ["a.csv", "b.csv"]


def test_new_upload_replaces_the_current_file():
    sessions, session = make_session()
    sources = DataSourceRepository()
    first = sources.upload(session.id, make_sample_data("one.csv"), "alex")
    second = sources.upload(session.id, make_sample_data("two.csv"), "priya")
    assert first != second and sources.current_id(session.id) == second
    assert sources.load_current(session.id)[1].name == "two.csv"


def test_no_upload_means_no_saved_file():
    sessions, session = make_session()
    sources = DataSourceRepository()
    assert sources.current_id(session.id) is None
    assert sources.load_current(session.id) is None


def test_upload_to_deleted_session_is_rejected():
    sessions, session = make_session()
    sources = DataSourceRepository()
    sessions.delete(session.id, "alex")
    check_error(SessionError, lambda: sources.upload(
        session.id, make_sample_data(), "alex"), "no longer exists")
    leftovers = DatabaseManager.getInstance().find_many(
        "data_sources", {"session_id": session.id})
    assert leftovers == [], "uploaded data was left behind"
    check_error(SessionError, lambda: sources.current_id(
        session.id), "no longer exists")


def test_upload_with_too_many_rows_is_rejected():
    sessions, session = make_session()
    sources = DataSourceRepository()
    big = DataSource("big.csv", ["P", "V"], [
                     {"P": str(i), "V": "1"} for i in range(MAX_ROWS + 1)])
    check_error(DataError, lambda: sources.upload(
        session.id, big, "alex"), "too many rows")
    assert sources.current_id(session.id) is None


def test_deleting_a_session_only_removes_its_own_files():
    sessions, session = make_session()
    other = sessions.create("Other", "alex")
    sources = DataSourceRepository()
    sources.upload(session.id, make_sample_data("mine.csv"), "alex")
    sources.upload(other.id, make_sample_data("kept.csv"), "alex")
    sessions.delete(session.id, "alex")
    found = DatabaseManager.getInstance().find_many(
        "data_sources", {"session_id": session.id})
    assert found == [], "data sources of a deleted session were left"
    assert sources.load_current(other.id)[1].name == "kept.csv"


def test_database_errors_are_reported_when_saving_or_loading():
    sources = DataSourceRepository(db=BrokenDatabase())
    for action in (lambda: sources.upload("s", make_sample_data(), "alex"),
                   lambda: sources.current_id("s"), lambda: sources.load_current("s")):
        check_error(DatabaseError, action)


# background task tests

class PostingView:
    def __init__(self):
        self.posted = []
        self.arrived = threading.Event()

    def post(self, key, value):
        self.posted.append((key, value))
        self.arrived.set()


def test_background_task_runs_on_another_thread():
    view, seen = PostingView(), {}

    def job():
        seen["thread"] = threading.current_thread()
        return 42

    def done(ok, value):
        pass

    ThreadBackground(view).submit(job, done)
    assert view.arrived.wait(5), "result never reported"
    key, (callback, ok, value) = view.posted[0]
    assert key == "-BACKGROUND-" and callback is done
    assert ok is True and value == 42
    assert seen["thread"] is not threading.main_thread(
    ), "the job ran on the calling thread"


def test_background_task_reports_errors():
    view = PostingView()

    def job():
        raise KeyError("boom")

    ThreadBackground(view).submit(job, lambda ok, value: None)
    assert view.arrived.wait(5), "failure never reported"
    callback, ok, value = view.posted[0][1]
    assert ok is False and isinstance(value, KeyError)


def test_immediate_background_runs_tasks_and_reports_errors():
    results = []
    ImmediateBackground().submit(lambda: 7, lambda *r: results.append(r))
    ImmediateBackground().submit(lambda: 1 / 0, lambda *r: results.append(r))
    assert results[0] == (True, 7)
    assert results[1][0] is False
    assert isinstance(results[1][1], ZeroDivisionError)


# remote DES tests

def test_opening_shows_loading_then_no_data_message():
    sessions, session = make_session()
    controller, view = open_remote_des("alex", session)
    assert view.draws[0] == (False, True, None), view.draws
    assert view.draws[-1] == (False, False, rdc.NO_DATA_YET), view.draws
    assert not controller.explorer.has_data()


def test_opening_loads_saved_data_and_chat_messages():
    sessions, session = make_session()
    DataSourceRepository().upload(session.id, make_sample_data(), "priya")
    MessageRepository().create_message(session.id, "priya", "hello")
    controller, view = open_remote_des("alex", session)
    assert controller.explorer.has_data()
    assert view.draws[-1][0] is True
    assert view.chat_updates == [[("priya", "hello")]], view.chat_updates
    assert any("Loaded a.csv" in s for s in view.statuses), view.statuses


def test_refreshing_shows_new_chat_messages_only():
    sessions, session = make_session()
    a, a_view = open_remote_des("alex", session)
    b, b_view = open_remote_des("priya", session)
    count = len(a_view.chat_updates)
    a.tick()
    assert len(a_view.chat_updates) == count, "redrawn with nothing new"
    b.handle("-CHAT_SEND-", {"-CHAT_INPUT-": "hi alex"})
    a.tick()
    assert a_view.chat_updates[-1] == [("priya", "hi alex")]


def test_another_users_upload_appears_after_refresh():
    sessions, session = make_session()
    a, a_view = open_remote_des("alex", session)
    b, b_view = open_remote_des("priya", session, files=[
                                make_csv(FIRST, "first.csv")])
    assert not a.explorer.has_data()
    b.handle("-UPLOAD-")
    a.tick()
    assert a.explorer.has_data() and a.explorer.source.name == "first.csv"
    assert a_view.draws[-1][0] is True


def test_upload_shares_the_file_with_everyone_in_the_session():
    sessions, session = make_session()
    a, a_view = open_remote_des("alex", session, files=[
                                make_csv(FIRST, "first.csv")])
    a.handle("-UPLOAD-")
    assert a.explorer.has_data() and a_view.errors == []
    loaded = DataSourceRepository().load_current(session.id)[1]
    assert loaded.name == "first.csv" and len(loaded.rows) == 4
    assert any("everyone in this session" in s for s in a_view.statuses)
    stored = DatabaseManager.getInstance().find_many(
        "data_sources", {"session_id": session.id})
    assert stored[0]["uploaded_by"] == "alex"


def test_cancelled_upload_does_nothing():
    sessions, session = make_session()
    a, view = open_remote_des("alex", session, files=[""])
    a.handle("-UPLOAD-")
    assert DataSourceRepository().current_id(session.id) is None
    assert view.errors == [] and not a.explorer.has_data()


def test_file_without_chart_data_does_not_replace_current_file():
    sessions, session = make_session()
    good = make_csv(FIRST, "good.csv")
    bad = make_csv(NO_NUMBERS, "bad.csv")
    a, view = open_remote_des("alex", session, files=[good, bad])
    a.handle("-UPLOAD-")
    before = DataSourceRepository().current_id(session.id)
    a.handle("-UPLOAD-")
    assert view.errors and "no numeric column" in view.errors[-1]
    assert DataSourceRepository().current_id(session.id) == before
    assert a.explorer.source.name == "good.csv"


def test_missing_file_shows_an_error_message():
    sessions, session = make_session()
    a, view = open_remote_des("alex", session, files=["nowhere/none.csv"])
    a.handle("-UPLOAD-")
    assert len(view.errors) == 1 and "File not found" in view.errors[0]


def test_adding_a_file_merges_it_with_the_current_file():
    sessions, session = make_session()
    a, view = open_remote_des("alex", session, files=[make_csv(
        FIRST, "first.csv"), make_csv(SECOND, "second.csv")])
    a.handle("-UPLOAD-")
    a.handle("-APPEND-")
    assert len(a.explorer.source.rows) == 6
    stored = DataSourceRepository().load_current(session.id)[1]
    assert len(stored.rows) == 6
    assert stored.part_names == ["first.csv", "second.csv"]


def test_adding_a_file_without_loading_one_shows_a_message():
    sessions, session = make_session()
    a, view = open_remote_des("alex", session, files=[make_csv(SECOND)])
    a.handle("-APPEND-")
    assert view.errors == ["Load a data source first."], view.errors
    assert view.asked == []


def test_adding_a_file_with_different_columns_is_refused():
    sessions, session = make_session()
    a, view = open_remote_des("alex", session, files=[
        make_csv(FIRST, "first.csv"), make_csv(WRONG_COLUMNS, "wrong.csv")])
    a.handle("-UPLOAD-")
    before = DataSourceRepository().current_id(session.id)
    a.handle("-APPEND-")
    assert "does not match" in view.errors[-1], view.errors
    assert DataSourceRepository().current_id(session.id) == before
    assert len(a.explorer.source.rows) == 4


def test_sending_a_message_saves_it_and_clears_the_input():
    sessions, session = make_session()
    a, view = open_remote_des("alex", session)
    a.handle("-CHAT_SEND-", {"-CHAT_INPUT-": " hello "})
    stored = MessageRepository().all(session.id)
    assert [(m.username, m.text) for m in stored] == [("alex", "hello")]
    assert view.chat_cleared == 1 and view.errors == []
    assert view.chat_updates[-1] == [("alex", "hello")]


def test_empty_messages_are_ignored_and_long_messages_are_rejected():
    sessions, session = make_session()
    a, view = open_remote_des("alex", session)
    a.handle("-CHAT_SEND-", {"-CHAT_INPUT-": "   "})
    a.handle("-CHAT_SEND-", {"-CHAT_INPUT-": "x" * 501})
    assert MessageRepository().all(session.id) == []
    assert view.chat_cleared == 0
    assert view.errors == ["Messages can be at most 500 characters."]


def test_zoom_and_reset_work_in_a_shared_session():
    sessions, session = make_session()
    a, view = open_remote_des("alex", session, files=[
                              make_csv(FIRST, "first.csv")])
    a.handle("-UPLOAD-")
    a.handle("-ZOOM_IN-")
    assert not a.explorer.view.is_full_view()
    a.handle("-RESET-")
    assert a.explorer.view.is_full_view() and view.errors == []


def test_connection_problem_shows_once_and_clears_when_reconnected():
    sessions, session = make_session()
    database = SwitchableDatabase(DatabaseManager.getInstance())
    a, view = open_remote_des("alex", session, db=database)
    database.down = True
    a.tick()
    a.tick()
    a.tick()
    assert view.chat_statuses == [rdc.OFFLINE_STATUS], view.chat_statuses
    assert view.errors == [], "an outage must not pop up an error every tick"
    database.down = False
    a.tick()
    assert view.chat_statuses == [rdc.OFFLINE_STATUS, ""]
    assert a.offline is False


def test_message_is_kept_when_sending_during_a_connection_problem():
    sessions, session = make_session()
    database = SwitchableDatabase(DatabaseManager.getInstance())
    a, view = open_remote_des("alex", session, db=database)
    database.down = True
    a.handle("-CHAT_SEND-", {"-CHAT_INPUT-": "hi"})
    assert view.errors == [rdc.SEND_FAILED] and view.chat_cleared == 0


def test_upload_during_a_connection_problem_shows_a_message():
    sessions, session = make_session()
    database = SwitchableDatabase(DatabaseManager.getInstance())
    a, view = open_remote_des("alex", session, db=database, files=[
                              make_csv(FIRST, "first.csv")])
    database.down = True
    a.handle("-UPLOAD-")
    assert view.errors == [rdc.DATABASE_UNREACHABLE], view.errors
    assert not a.explorer.has_data()


def test_deleted_session_closes_the_window_and_shows_a_message():
    sessions, session = make_session()
    a, view = open_remote_des("priya", session)
    sessions.delete(session.id, "alex")
    a.tick()
    a.tick()
    assert view.errors == [rdc.SESSION_DELETED], view.errors
    assert a.is_finished() and view.closed == 1


def test_closing_the_window_stops_all_further_actions():
    sessions, session = make_session()
    a, view = open_remote_des("alex", session)
    a.handle(sg.WIN_CLOSED)
    assert a.is_finished() and view.closed == 1
    draws, updates = len(view.draws), len(view.chat_updates)
    a.tick()
    a.handle("-ZOOM_IN-")
    assert len(view.draws) == draws and len(view.chat_updates) == updates


def test_only_one_background_check_runs_at_a_time():
    sessions, session = make_session()
    background = ManualBackground()
    a, view = open_remote_des("alex", session, background=background)
    background.run_all()
    a.tick()
    a.tick()
    a.tick()
    assert len(background.pending) == 1, background.pending


def test_results_are_ignored_if_the_window_has_closed():
    sessions, session = make_session()
    DataSourceRepository().upload(session.id, make_sample_data(), "priya")
    MessageRepository().create_message(session.id, "priya", "late")
    background = ManualBackground()
    a, view = open_remote_des("alex", session, background=background)
    a.close()
    background.run_all()
    assert view.chat_updates == [] and not a.explorer.has_data()
    assert view.errors == []


def test_unexpected_background_error_does_not_crash_the_window():
    sessions, session = make_session()

    class Exploding:
        def current_id(self, session_id):
            raise ValueError("boom")

        def load_current(self, session_id):
            raise ValueError("boom")

    printed = []
    original = traceback.print_exception
    traceback.print_exception = lambda *args, **kwargs: printed.append(args)
    try:
        view = FakeRemoteView()
        controller = RemoteDesController(User("alex", b"h"), session, Exploding(
        ), MessageRepository(), view, ImmediateBackground())
        controller.open()
        controller.tick()
        controller.tick()
    finally:
        traceback.print_exception = original
    assert len(printed) == 1, "the traceback should be printed once"
    assert rdc.UNEXPECTED_STATUS in view.chat_statuses
    assert view.errors == [] and not controller.is_finished()


def test_chat_messages_are_shown_after_a_failed_file_check():
    """A failed file check shouldnt cause new chat messages to be missed."""
    sessions, session = make_session()
    MessageRepository().create_message(session.id, "priya", "hi")

    class FlakySources(DataSourceRepository):
        fail = True

        def current_id(self, session_id):
            if self.fail:
                raise DatabaseError("simulated outage")
            return super().current_id(session_id)

    sources = FlakySources()
    view = FakeRemoteView()
    controller = RemoteDesController(
        User("alex", b"h"), session, sources, MessageRepository(), view,
        ImmediateBackground())
    controller.open()
    assert view.chat_updates == [], "shown despite the failed check"
    sources.fail = False
    controller.tick()
    assert view.chat_updates == [[("priya", "hi")]], view.chat_updates


def test_background_results_are_handled_by_the_window():
    sessions, session = make_session()
    a, view = open_remote_des("alex", session)
    seen = []
    a.handle("-BACKGROUND-", {"-BACKGROUND-": (lambda ok,
             value: seen.append((ok, value)), True, 5)})
    assert seen == [(True, 5)]


# window manager

class FakeWindowView:
    def __init__(self):
        self.window = object()
        self.closed = 0

    def close(self):
        self.closed += 1


class FakeWindowController:
    def __init__(self, finish_on=None, session_id=None):
        self.view = FakeWindowView()
        self.finish_on = finish_on
        self.events = []
        self.ticks = 0
        self.finished = False
        if session_id:
            self.session = SimpleNamespace(id=session_id)

    def handle(self, event, values):
        self.events.append(event)
        if event == self.finish_on:
            self.finished = True

    def tick(self):
        self.ticks += 1

    def is_finished(self):
        return self.finished


def scripted(steps):
    """Return planned window events one at a time."""
    queue = list(steps)

    def reader(timeout=None):
        if not queue:
            raise RuntimeError("manager kept reading after the script ended")
        return queue.pop(0)
    return reader


def test_manager_sends_events_to_the_correct_window():
    main, extra = FakeWindowController("done"), FakeWindowController()
    manager = WindowManager(main, scripted([
        (extra.view.window, "a", {}), (main.view.window, "b", {}),
        (main.view.window, "done", {})]))
    manager.add(extra)
    manager.run()
    assert extra.events == ["a"] and main.events == ["b", "done"]


def test_manager_refreshes_every_window_after_a_timeout():
    main, extra = FakeWindowController("done"), FakeWindowController()
    manager = WindowManager(main, scripted([
        (None, "__TIMEOUT__", None), (main.view.window, "done", {})]))
    manager.add(extra)
    manager.run()
    assert main.ticks == 1 and extra.ticks == 1


def test_finished_windows_are_closed_and_removed():
    main, extra = FakeWindowController("done"), FakeWindowController("bye")
    manager = WindowManager(main, scripted([
        (extra.view.window, "bye", {}), (None, "__TIMEOUT__", None),
        (main.view.window, "done", {})]))
    manager.add(extra)
    manager.run()
    assert extra.view.closed == 1 and extra.ticks == 0, "a finished window was kept"


def test_closing_main_window_closes_all_other_windows():
    main = FakeWindowController("done")
    a, b = FakeWindowController(), FakeWindowController()
    manager = WindowManager(main, scripted([(main.view.window, "done", {})]))
    manager.add(a)
    manager.add(b)
    manager.run()
    assert a.view.closed == b.view.closed == main.view.closed == 1
    assert manager.controllers == []


def test_manager_ignores_events_from_unknown_windows():
    main = FakeWindowController("done")
    manager = WindowManager(main, scripted([
        (object(), "x", {}), (main.view.window, "done", {})]))
    manager.run()
    assert main.events == ["done"]


def test_manager_can_find_a_window_by_session():
    main = FakeWindowController()
    s1 = FakeWindowController(session_id="s1")
    manager = WindowManager(main)
    manager.add(s1)
    assert manager.find_session("s1") is s1
    assert manager.find_session("s2") is None


# session screen tests

class NullSessionView:
    def __init__(self):
        self.shown = []
        self.window = object()

    def show_sessions(self, rows):
        self.shown.append(rows)

    def set_buttons(self, join, delete):
        pass

    def close(self):
        pass


def test_session_screen_opens_and_logs_out():
    sessions, session = make_session()
    controller = SessionController(
        User("alex", b"h"), sessions, lambda s, u: None, NullSessionView())
    assert not controller.is_finished()
    controller.open()
    assert controller.view.shown[0][0][0] == "Shared"
    controller.tick()
    controller.handle("-LOGOUT-", {})
    assert controller.is_finished() and controller.result == "logout"


def test_closing_session_screen_marks_it_as_closed():
    sessions, session = make_session()
    controller = SessionController(
        User("alex", b"h"), sessions, lambda s, u: None, NullSessionView())
    controller.handle(sg.WIN_CLOSED, None)
    assert controller.result == "closed" and controller.is_finished()


ALL_TESTS = [
    test_saved_data_can_be_loaded_again,
    test_saved_data_keeps_blank_values_and_column_order,
    test_merged_files_keep_their_original_names,
    test_new_upload_replaces_the_current_file,
    test_no_upload_means_no_saved_file,
    test_upload_to_deleted_session_is_rejected,
    test_upload_with_too_many_rows_is_rejected,
    test_deleting_a_session_only_removes_its_own_files,
    test_database_errors_are_reported_when_saving_or_loading,
    test_background_task_runs_on_another_thread,
    test_background_task_reports_errors,
    test_immediate_background_runs_tasks_and_reports_errors,
    test_opening_shows_loading_then_no_data_message,
    test_opening_loads_saved_data_and_chat_messages,
    test_refreshing_shows_new_chat_messages_only,
    test_another_users_upload_appears_after_refresh,
    test_upload_shares_the_file_with_everyone_in_the_session,
    test_cancelled_upload_does_nothing,
    test_file_without_chart_data_does_not_replace_current_file,
    test_missing_file_shows_an_error_message,
    test_adding_a_file_merges_it_with_the_current_file,
    test_adding_a_file_without_loading_one_shows_a_message,
    test_adding_a_file_with_different_columns_is_refused,
    test_sending_a_message_saves_it_and_clears_the_input,
    test_empty_messages_are_ignored_and_long_messages_are_rejected,
    test_zoom_and_reset_work_in_a_shared_session,
    test_connection_problem_shows_once_and_clears_when_reconnected,
    test_message_is_kept_when_sending_during_a_connection_problem,
    test_upload_during_a_connection_problem_shows_a_message,
    test_deleted_session_closes_the_window_and_shows_a_message,
    test_closing_the_window_stops_all_further_actions,
    test_only_one_background_check_runs_at_a_time,
    test_results_are_ignored_if_the_window_has_closed,
    test_unexpected_background_error_does_not_crash_the_window,
    test_chat_messages_are_shown_after_a_failed_file_check,
    test_background_results_are_handled_by_the_window,
    test_manager_sends_events_to_the_correct_window,
    test_manager_refreshes_every_window_after_a_timeout,
    test_finished_windows_are_closed_and_removed,
    test_closing_main_window_closes_all_other_windows,
    test_manager_ignores_events_from_unknown_windows,
    test_manager_can_find_a_window_by_session,
    test_session_screen_opens_and_logs_out,
    test_closing_session_screen_marks_it_as_closed,
]
