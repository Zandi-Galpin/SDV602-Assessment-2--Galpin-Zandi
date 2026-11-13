"""Tests for chat messages in each session.

Checks that messages are saved separately, displayed in the chat,
deleted with their session, and handled correctly when the database
is unavailable. Uses a fake chat window, so no real window opens.
"""
import FreeSimpleGUI as sg

import config
from controller.chat_controller import OFFLINE_STATUS, SEND_FAILED, ChatController
from data.database_manager import DatabaseError, DatabaseManager
from data.message_repository import MAX_MESSAGE_LENGTH, ChatError, MessageRepository
from data.session_repository import SessionError, SessionRepository
from model.chat_feed import ChatFeed
from model.chat_message import ChatMessage
from model.session import Session
from tests.fakes import BrokenDatabase, SwitchableDatabase
from tests.helpers import reset_database
from view.chat_view import format_messages

TIMEOUT = ("__TIMEOUT__", {})


#Test helpers

def create_fresh_messages():
    reset_database()
    return MessageRepository()


def get_message_texts(messages):
    return [m.text for m in messages]

def check_chat_error(func, expected_text):
    try:
        func()
    except ChatError as e:
        assert expected_text in str(e), f"expected '{expected_text}' in '{e}'"
        return
    raise AssertionError(f"No ChatError raised (wanted '{expected_text}')")


def create_send_event(text):
    return "Send", {"-CHAT-": text}

class FakeChatView:
    """Pretends to be a chat window and records what happens.

    Can also run extra actions just before message or event is returned.
    allows to test the database going offline.
    """

    def __init__(self, events, hooks=None):
        self._events = list(events)
        self._hooks = hooks or {}
        self._count = 0
        self.timeouts = []
        self.updates = []
        self.statuses = []
        self.errors = []
        self.cleared = 0
        self.closed = False

    def read(self, timeout=None):
        self.timeouts.append(timeout)
        hook = self._hooks.get(self._count)
        self._count += 1
        if hook:
            hook()
        if not self._events:
            raise RuntimeError("No more test events available")
        return self._events.pop(0)

    def update_messages(self, messages):
        self.updates.append([(m.username, m.text) for m in messages])

    def show_status(self, text):
        self.statuses.append(text)

    def show_error(self, message):
        self.errors.append(str(message))

    def clear_input(self):
        self.cleared += 1

    def close(self):
        self.closed = True


def run_chat_test(repo, events, user="alex", session_id="s1", hooks=None):
    view = FakeChatView(list(events) + [(sg.WIN_CLOSED, {})], hooks)
    session = Session(session_id, "Rainfall", "alex")
    controller = ChatController(user, repo, session, view)
    controller.run()
    return controller, view


#Message storage tests

def test_messages_are_saved_separately_for_each_session():
    repo = create_fresh_messages()
    repo.create_message("s1", "alex", "in one")
    repo.create_message("s2", "priya", "in two")
    repo.create_message("s1", "priya", "also one")
    assert get_message_texts(repo.all("s1")) == ["in one", "also one"]
    assert get_message_texts(repo.all("s2")) == ["in two"]
    assert repo.all("nobody-here") == []


def test_messages_stay_in_the_order_they_were_sent():
    repo = create_fresh_messages()
    for i in range(20):
        repo.create_message("s1", "alex", str(i))
    assert get_message_texts(repo.all("s1")) == [str(i) for i in range(20)]


def test_saved_messages_include_all_their_details():
    repo = create_fresh_messages()
    repo.create_message("s1", "alex", "hello")
    message = repo.all("s1")[0]
    assert isinstance(message, ChatMessage)
    assert message.username == "alex" and message.text == "hello"
    assert message.timestamp is not None

def test_messages_are_trimmed_and_empty_messages_are_not_saved():
    repo = create_fresh_messages()
    repo.create_message("s1", "alex", "  hi there  ")
    assert get_message_texts(repo.all("s1")) == ["hi there"]
    for blank in ("", "   ", None):
        check_chat_error(
            lambda: repo.create_message("s1", "alex", blank),
            "Type a message first.")
    assert len(repo.all("s1")) == 1, "An empty message was saved"
def test_message_length_limit_is_enforced():
    repo = create_fresh_messages()
    too_long = "x" * (MAX_MESSAGE_LENGTH + 1)
    check_chat_error(
        lambda: repo.create_message("s1", "alex", too_long),
        f"Messages can be {MAX_MESSAGE_LENGTH} characters max.")
    repo.create_message("s1", "alex", "x" * MAX_MESSAGE_LENGTH)
    assert len(repo.all("s1")) == 1

def test_only_the_most_recent_messages_are_shown_when_limited():
    repo = create_fresh_messages()
    for i in range(5):
        repo.create_message("s1", "alex", str(i))
    assert get_message_texts(repo.all("s1", limit=3)) == ["2", "3", "4"]


def test_deleting_messages_removes_only_the_selected_sessions_messages():
    repo = create_fresh_messages()
    repo.create_message("s1", "alex", "a")
    repo.create_message("s1", "alex", "b")
    repo.create_message("s2", "alex", "c")
    assert repo.delete_for_session("s1") == 2
    assert repo.all("s1") == [] and get_message_texts(repo.all("s2")) == ["c"]
    assert repo.delete_for_session("s1") == 0


def test_database_errors_are_not_hidden():
    repo = MessageRepository(db=BrokenDatabase())
    for action in (lambda: repo.create_message("s1", "alex", "hi"),
                   lambda: repo.all("s1"),
                   lambda: repo.delete_for_session("s1")):
        try:
            action()
        except DatabaseError:
            continue
        raise AssertionError("Database error was not reported")


#Session deletion tests

def test_deleting_a_session_also_deletes_its_messages():
    reset_database()
    sessions, messages = SessionRepository(), MessageRepository()
    first = sessions.create("First", "alex")
    second = sessions.create("Second", "alex")
    messages.create_message(first.id, "alex", "doomed")
    messages.create_message(second.id, "alex", "survivor")
    sessions.delete(first.id, "alex")
    assert messages.all(first.id) == [], "Deleted session messages remain"
    assert get_message_texts(messages.all(second.id)) == ["survivor"]

def test_messages_are_kept_when_someone_else_tries_to_delete_a_session():
    reset_database()
    sessions, messages = SessionRepository(), MessageRepository()
    session = sessions.create("Mine", "alex")
    messages.create_message(session.id, "alex", "keep me")
    try:
        sessions.delete(session.id, "priya")
    except SessionError:
        pass
    else:
        raise AssertionError("Someone who does not own the session deleted it")
    assert get_message_texts(messages.all(session.id)) == ["keep me"]

#Chat feed tests

def test_first_chat_refresh_returns_an_empty_list_when_there_are_no_messages():
    feed = ChatFeed(create_fresh_messages(), "s1")
    first = feed.refresh()
    assert first == [], "The first refresh should return [] instead of None"
    assert feed.refresh() is None

def test_chat_refresh_only_returns_messages_that_have_changed():
    repo = create_fresh_messages()
    feed = ChatFeed(repo, "s1")
    feed.refresh()
    repo.create_message("s1", "alex", "one")
    assert get_message_texts(feed.refresh()) == ["one"]
    assert feed.refresh() is None
    repo.create_message("s2", "alex", "another session")
    assert feed.refresh() is None, "A message from another session was counted"
    repo.create_message("s1", "priya", "two")
    assert get_message_texts(feed.refresh()) == ["one", "two"]


def test_chat_does_not_save_empty_messages():
    repo = create_fresh_messages()
    feed = ChatFeed(repo, "s1")
    assert feed.send("alex", "   ") is False and feed.send("alex", "") is False
    assert repo.all("s1") == []
    assert feed.send("alex", " hi ") is True
    assert get_message_texts(repo.all("s1")) == ["hi"]


def test_chat_recovers_from_database_problems_without_losing_messages():
    reset_database()
    database = SwitchableDatabase(DatabaseManager.getInstance())
    repo = MessageRepository(db=database)
    feed = ChatFeed(repo, "s1")
    repo.create_message("s1", "alex", "before")
    assert get_message_texts(feed.refresh()) == ["before"]

    database.down = True
    try:
        feed.refresh()
    except DatabaseError:
        pass
    else:
        raise AssertionError("Database problem was not reported")

    database.down = False
    assert feed.refresh() is None, "Nothing changed while the database was offline"
    repo.create_message("s1", "alex", "after")
    assert get_message_texts(feed.refresh()) == ["before", "after"]


#Chat message display tests

def test_chat_messages_are_displayed_in_the_correct_format():
    assert format_messages([]) == ""
    log = [ChatMessage("alex", "hi", None), ChatMessage("priya", "yo", None)]
    assert format_messages(log) == "alex: hi\npriya: yo\n"


#Chat window tests

def test_chat_opens_with_the_correct_sessions_messages():
    repo = create_fresh_messages()
    repo.create_message("s1", "alex", "mine")
    repo.create_message("s2", "priya", "not mine")
    controller, view = run_chat_test(repo, [])
    assert view.updates == [[("alex", "mine")]], view.updates
    assert view.closed


def test_chat_updates_only_when_new_messages_arrive():
    repo = create_fresh_messages()
    controller, view = run_chat_test(
        repo, [TIMEOUT, TIMEOUT, TIMEOUT],
        hooks={2: lambda: repo.create_message("s1", "priya", "new")})
    assert len(view.updates) == 2, view.updates
    assert view.updates[-1] == [("priya", "new")]


def test_chat_checks_for_new_messages_at_the_correct_interval():
    controller, view = run_chat_test(create_fresh_messages(), [TIMEOUT])
    assert view.timeouts and all(t == config.POLL_RATE for t in view.timeouts), view.timeouts


def test_sending_a_message_saves_and_displays_it_in_the_correct_session():
    repo = create_fresh_messages()
    controller, view = run_chat_test(repo, [create_send_event(" hello ")])
    assert get_message_texts(repo.all("s1")) == ["hello"]
    assert repo.all("s1")[0].username == "alex"
    assert repo.all("s2") == []
    assert view.cleared == 1 and view.errors == []
    assert view.updates[-1] == [("alex", "hello")], view.updates

def test_sending_an_empty_message_does_nothing():
    repo = create_fresh_messages()
    controller, view = run_chat_test(
        repo, [create_send_event(""), create_send_event("   ")])
    assert repo.all("s1") == []
    assert view.cleared == 0 and view.errors == []
    assert len(view.updates) == 1, "Sending an empty message caused an update"


def test_long_messages_show_an_error_and_remain_in_the_input_box():
    repo = create_fresh_messages()
    controller, view = run_chat_test(
        repo, [create_send_event("x" * (MAX_MESSAGE_LENGTH + 1))])
    assert view.errors == [f"Messages can be {MAX_MESSAGE_LENGTH} characters max."], view.errors
    assert view.cleared == 0, "The message was cleared even though it was not sent"
    assert repo.all("s1") == []

def test_chat_shows_when_the_database_goes_offline_and_recovers():
    reset_database()
    database = SwitchableDatabase(DatabaseManager.getInstance())
    repo = MessageRepository(db=database)

    def go_offline():
        database.down = True

    def come_back_online():
        database.down = False

    controller, view = run_chat_test(
        repo, [TIMEOUT, TIMEOUT, TIMEOUT, TIMEOUT, TIMEOUT],
        hooks={1: go_offline, 4: come_back_online})
    assert view.statuses == [OFFLINE_STATUS, ""], view.statuses
    assert view.errors == [], "Database problems should not cause repeated pop-ups"
    assert controller.offline is False


def test_sending_a_message_while_offline_shows_an_error_and_keeps_the_text():
    reset_database()
    database = SwitchableDatabase(DatabaseManager.getInstance())
    repo = MessageRepository(db=database)

    def go_offline():
        database.down = True

    controller, view = run_chat_test(
        repo, [create_send_event("hi")], hooks={0: go_offline})
    assert view.errors == [SEND_FAILED], view.errors
    assert view.cleared == 0, "The message was cleared even though sending failed"
    database.down = False
    assert repo.all("s1") == []


def test_closing_the_chat_also_closes_its_window():
    controller, view = run_chat_test(create_fresh_messages(), [])
    assert view.closed


ALL_TESTS = [
    test_messages_are_saved_separately_for_each_session,
    test_messages_stay_in_the_order_they_were_sent,
    test_saved_messages_include_all_their_details,
    test_messages_are_trimmed_and_empty_messages_are_not_saved,
    test_message_length_limit_is_enforced,
    test_only_the_most_recent_messages_are_shown_when_limited,
    test_deleting_messages_removes_only_the_selected_sessions_messages,
    test_database_errors_are_not_hidden,
    test_deleting_a_session_also_deletes_its_messages,
    test_messages_are_kept_when_someone_else_tries_to_delete_a_session,
    test_first_chat_refresh_returns_an_empty_list_when_there_are_no_messages,
    test_chat_refresh_only_returns_messages_that_have_changed,
    test_chat_does_not_save_empty_messages,
    test_chat_recovers_from_database_problems_without_losing_messages,
    test_chat_messages_are_displayed_in_the_correct_format,
    test_chat_opens_with_the_correct_sessions_messages,
    test_chat_updates_only_when_new_messages_arrive,
    test_chat_checks_for_new_messages_at_the_correct_interval,
    test_sending_a_message_saves_and_displays_it_in_the_correct_session,
    test_sending_an_empty_message_does_nothing,
    test_long_messages_show_an_error_and_remain_in_the_input_box,
    test_chat_shows_when_the_database_goes_offline_and_recovers,
    test_sending_a_message_while_offline_shows_an_error_and_keeps_the_text,
    test_closing_the_chat_also_closes_its_window,
]
