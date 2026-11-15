"""Tests for sessions: checking how sessions work, how they are saved
and how the session screen behaves.
No window is opened during these tests.
"""
import FreeSimpleGUI as sg

import config
from controller.session_controller import SessionController
from data.database_manager import DatabaseError
from data.session_repository import SessionError, SessionRepository
from model.session import Session
from model.user import User
from tests.fakes import BrokenDatabase
from tests.helpers import reset_database

DB_MESSAGE = "Could not reach the database. Please try again later."


# small helpers

def get_fresh_repo():
    reset_database()
    return SessionRepository()


def get_repo_with_sessions():
    """Adds four sessions: two public and two private."""
    repo = get_fresh_repo()
    repo.create("Alpha", "alex")
    repo.create("Beta", "priya")
    repo.create("Gamma", "alex", public=False)
    repo.create("Secret", "priya", public=False)
    return repo


def get_session_names(sessions):
    return [s.name for s in sessions]


def check_for_session_error(func, message):
    try:
        func()
    except SessionError as e:
        assert message in str(e), f"expected '{message}' in '{e}'"
        return
    raise AssertionError(f"no SessionError raised (wanted '{message}')")


def create_test_user(name="alex"):
    return User(name, b"hash")


class FakeSessionView:
    """Pretends to be the session window.
    Gives back saved events, answers delete questions and remembers
    what was shown on screen.

    hooks let us pretend that something happend before an event.
    """

    def __init__(self, events, confirms=(), hooks=None):
        self._events = list(events)
        self._confirms = list(confirms)
        self._hooks = hooks or {}
        self._count = 0
        self.shown = []  # sessions shown on screen
        self.buttons = []  # which buttons were turned on
        self.errors = []
        self.statuses = []
        self.confirmations = []  # names asked about
        self.cleared = 0
        self.closed = False

    def read(self, timeout=None):
        hook = self._hooks.get(self._count)
        self._count += 1
        if hook:
            hook()
        if not self._events:
            raise RuntimeError("FakeSessionView ran out of scripted events")
        return self._events.pop(0)

    def show_sessions(self, rows):
        self.shown.append(rows)

    def set_buttons(self, join_enabled, delete_enabled):
        self.buttons.append((join_enabled, delete_enabled))

    def clear_new_name(self):
        self.cleared += 1

    def confirm_delete(self, name):
        self.confirmations.append(name)
        return self._confirms.pop(0) if self._confirms else True

    def show_status(self, text):
        self.statuses.append(text)

    def show_error(self, message):
        self.errors.append(str(message))

    def close(self):
        self.closed = True


def make_event(event, row=None, name="", private=False):
    values = {"-TABLE-": [] if row is None else [row],
              "-NEW_NAME-": name, "-PRIVATE-": private}
    return event, values


def open_test_screen(repo, events, user="alex", confirms=(), hooks=None):
    """Runs the screen using saved events.
    Returns the result, the fake window and any joined sessions.
    """
    view = FakeSessionView(
        list(events) + [(sg.WIN_CLOSED, {})], confirms, hooks)
    joined = []
    controller = SessionController(
        create_test_user(user), repo,
        lambda session, who: joined.append((session.name, who.name)), view)
    result = controller.run()
    return result, view, joined


# checking sessions

def test_session_owner_and_who_can_see_it():
    public = Session("1", "Open", "alex", True)
    private = Session("2", "Closed", "alex", False)
    assert public.is_owned_by("alex") and not public.is_owned_by("priya")
    assert public.is_visible_to("priya"), "public session hidden"
    assert private.is_visible_to("alex"), "owner cannot see own private"
    assert not private.is_visible_to("priya"), "private session leaked"


# checking saved sessions

def test_new_session_is_saved_and_returned():
    repo = get_fresh_repo()
    session = repo.create("Population", "alex")
    assert session.name == "Population" and session.owner == "alex"
    assert session.public is True and session.id
    found = repo.find(session.id)
    assert found.name == "Population" and found.created is not None


def test_session_name_spaces_are_fixed():
    repo = get_fresh_repo()
    assert repo.create("  Big    Data  ", "alex").name == "Big Data"


def test_empty_or_too_long_names_are_not_allowed():
    repo = get_fresh_repo()
    for bad in ("", "   ", None):
        check_for_session_error(lambda: repo.create(
            bad, "alex"), "Please enter a name")
    check_for_session_error(lambda: repo.create(
        "x" * 61, "alex"), "Session names can be 60 characters at most")
    repo.create("x" * 60, "alex")


def test_same_person_cannot_use_the_same_name_twice():
    repo = get_fresh_repo()
    repo.create("Shared", "alex")
    check_for_session_error(lambda: repo.create(
        "shared", "alex"), "already have a session called 'shared'")
    repo.create("Shared", "priya")


def test_people_only_see_public_and_their_own_private_sessions():
    repo = get_repo_with_sessions()
    assert get_session_names(repo.list_visible("alex")) == [
        "Alpha", "Beta", "Gamma"]
    assert get_session_names(repo.list_visible("priya")) == [
        "Alpha", "Beta", "Secret"]
    assert get_session_names(repo.list_visible("stranger")) == [
        "Alpha", "Beta"]


def test_session_names_are_sorted_alphabetically():
    repo = get_fresh_repo()
    for name in ("banana", "Apple", "cherry"):
        repo.create(name, "alex")
    assert get_session_names(repo.list_visible("alex")) == [
        "Apple", "banana", "cherry"]


def test_missing_or_wrong_session_ids_return_nothing():
    repo = get_fresh_repo()
    assert repo.find("asfdasdfsdaaasdfsfda") is None
    assert repo.find("not-an-id") is None
    assert repo.find("") is None
    assert repo.find(None) is None


def test_owner_can_remove_their_own_session():
    repo = get_fresh_repo()
    session = repo.create("Temp", "alex")
    repo.delete(session.id, "alex")
    assert repo.find(session.id) is None


def test_other_people_cannot_remove_a_session():
    repo = get_fresh_repo()
    session = repo.create("Mine", "alex")
    check_for_session_error(lambda: repo.delete(
        session.id, "priya"), "Only the person who created")
    assert repo.find(session.id) is not None, "session was deleted"


def test_removing_a_session_that_does_not_exist():
    repo = get_fresh_repo()
    check_for_session_error(
        lambda: repo.delete("asfdasdfsdaaasdfsfda", "alex"), "no longer exists")
    check_for_session_error(lambda: repo.delete(
        "not-an-id", "alex"), "no longer exists")


def test_database_problems_are_not_hidden():
    repo = SessionRepository(db=BrokenDatabase())
    for action in (lambda: repo.create("x", "alex"),
                   lambda: repo.list_visible("alex"),
                   lambda: repo.find("asfdasdfsdaaasdfsfda"),
                   lambda: repo.delete("asfdasdfsdaaasdfsfda", "alex")):
        try:
            action()
        except DatabaseError:
            continue
        raise AssertionError("database failure was SWALLOWED")


# checking the session screen

def test_screen_shows_the_sessions_at_start():
    repo = get_repo_with_sessions()
    result, view, joined = open_test_screen(repo, [])
    assert view.shown[0] == [["Alpha", "alex (you)", "Public"],
                             ["Beta", "priya", "Public"],
                             ["Gamma", "alex (you)", "Private"]], view.shown
    assert view.buttons == [(False, False)], view.buttons
    assert result == "closed" and view.closed


def test_buttons_change_when_a_session_is_selected():
    repo = get_repo_with_sessions()
    result, view, joined = open_test_screen(
        repo, [make_event("-TABLE-", row=0), make_event("-TABLE-", row=1),
               make_event("-TABLE-", row=None), make_event("-TABLE-", row=99)])
    assert view.buttons == [(False, False),
                            (True, True),
                            (True, False),
                            (False, False),
                            (False, False)], view.buttons


def test_creating_a_public_session_works():
    repo = get_repo_with_sessions()
    result, view, joined = open_test_screen(
        repo, [make_event("-CREATE-", name="  Delta ")], user="priya")
    assert "Delta" in get_session_names(
        repo.list_visible("alex")), "not public"
    assert view.cleared == 1 and view.errors == []
    assert view.statuses == ["Created 'Delta'."], view.statuses
    assert ["Delta", "priya (you)", "Public"] in view.shown[-1]


def test_creating_a_private_session_works():
    repo = get_repo_with_sessions()
    open_test_screen(repo, [make_event("-CREATE-", name="Hidden", private=True)],
                     user="priya")
    assert "Hidden" not in get_session_names(
        repo.list_visible("alex")), "leaked"
    assert "Hidden" in get_session_names(repo.list_visible("priya"))


def test_wrong_session_names_show_an_error():
    repo = get_repo_with_sessions()
    result, view, joined = open_test_screen(
        repo, [make_event("-CREATE-", name=""), make_event("-CREATE-", name="alpha")])
    assert len(view.errors) == 2, view.errors
    assert "Please enter a name" in view.errors[0]
    assert "already have a session called" in view.errors[1]
    assert view.cleared == 0, "input cleared even though creation failed"


def test_joining_a_session_does_not_close_the_screen():
    repo = get_repo_with_sessions()
    result, view, joined = open_test_screen(
        repo, [make_event("-JOIN-", row=1)])
    assert joined == [("Beta", "alex")], joined
    assert view.errors == []
    assert result == "closed", "screen closed itself after joining"


def test_joining_without_selecting_a_session_shows_an_error():
    repo = get_repo_with_sessions()
    result, view, joined = open_test_screen(repo, [make_event("-JOIN-")])
    assert view.errors == ["Select a session first."], view.errors
    assert joined == []


def test_cannot_join_a_session_that_was_removed():
    repo = get_repo_with_sessions()
    beta = [s for s in repo.list_visible("alex") if s.name == "Beta"][0]
    result, view, joined = open_test_screen(
        repo, [make_event("-JOIN-", row=1)],
        hooks={0: lambda: repo.delete(beta.id, "priya")})
    assert view.errors == ["That session no longer exists."], view.errors
    assert joined == []
    assert [row[0] for row in view.shown[-1]
            ] == ["Alpha", "Gamma"], "list was not refreshed"


def test_cannot_join_a_session_that_was_made_private():
    repo = get_repo_with_sessions()

    def make_beta_private():
        repo.db.get_collection(config.SESSIONS_COLLECTION).update_one(
            {"name": "Beta"}, {"$set": {"public": False}})

    result, view, joined = open_test_screen(
        repo, [make_event("-JOIN-", row=1)], hooks={0: make_beta_private})
    assert view.errors == ["That session is private."], view.errors
    assert joined == []


def test_removing_your_session_after_saying_yes():
    repo = get_repo_with_sessions()
    result, view, joined = open_test_screen(
        repo, [make_event("-DELETE-", row=0)], confirms=[True])
    assert view.confirmations == ["Alpha"], view.confirmations
    assert "Alpha" not in get_session_names(repo.list_visible("alex"))
    assert view.statuses == ["Deleted 'Alpha'."], view.statuses
    assert [row[0] for row in view.shown[-1]] == ["Beta", "Gamma"]


def test_saying_no_keeps_the_session():
    repo = get_repo_with_sessions()
    result, view, joined = open_test_screen(
        repo, [make_event("-DELETE-", row=0)], confirms=[False])
    assert "Alpha" in get_session_names(repo.list_visible("alex"))
    assert view.errors == [] and view.statuses == []


def test_cannot_remove_someone_elses_session():
    repo = get_repo_with_sessions()
    result, view, joined = open_test_screen(
        repo, [make_event("-DELETE-", row=1)])
    assert view.errors == [
        "Only the person who created a session can delete it."], view.errors
    assert view.confirmations == [], "asked to confirm an impossible delete"
    assert "Beta" in get_session_names(repo.list_visible("alex"))


def test_removing_without_selecting_a_session_shows_an_error():
    repo = get_repo_with_sessions()
    result, view, joined = open_test_screen(repo, [make_event("-DELETE-")])
    assert view.errors == ["Select a session first."], view.errors


def test_refresh_shows_sessions_added_by_other_people():
    repo = get_repo_with_sessions()
    result, view, joined = open_test_screen(
        repo, [make_event("-REFRESH-")],
        hooks={0: lambda: repo.create("Newcomer", "sam")})
    before = [row[0] for row in view.shown[0]]
    after = [row[0] for row in view.shown[-1]]
    assert "Newcomer" not in before and "Newcomer" in after, (before, after)


def test_database_problems_show_a_simple_message():
    repo = SessionRepository(db=BrokenDatabase())
    result, view, joined = open_test_screen(
        repo, [make_event("-REFRESH-"), make_event("-CREATE-", name="x"),
               make_event("-JOIN-", row=0), make_event("-DELETE-", row=0)])
    assert view.errors[:2] == [DB_MESSAGE, DB_MESSAGE], view.errors
    for message in view.errors:
        assert "simulated" not in message, "raw error text reached the user"
    assert result == "closed"


def test_logging_out_and_closing_give_different_results():
    repo = get_repo_with_sessions()
    result, view, joined = open_test_screen(repo, [make_event("-LOGOUT-")])
    assert result == "logout" and view.closed
    result, view, joined = open_test_screen(repo, [])
    assert result == "closed" and view.closed


def test_unknown_screen_actions_are_ignored():
    repo = get_repo_with_sessions()
    result, view, joined = open_test_screen(
        repo, [make_event("-SOMETHING_ELSE-"), make_event("__TIMEOUT__")])
    assert view.errors == [] and len(view.shown) == 1


ALL_TESTS = [
    test_session_owner_and_who_can_see_it,
    test_new_session_is_saved_and_returned,
    test_session_name_spaces_are_fixed,
    test_empty_or_too_long_names_are_not_allowed,
    test_same_person_cannot_use_the_same_name_twice,
    test_people_only_see_public_and_their_own_private_sessions,
    test_session_names_are_sorted_alphabetically,
    test_missing_or_wrong_session_ids_return_nothing,
    test_owner_can_remove_their_own_session,
    test_other_people_cannot_remove_a_session,
    test_removing_a_session_that_does_not_exist,
    test_database_problems_are_not_hidden,
    test_screen_shows_the_sessions_at_start,
    test_buttons_change_when_a_session_is_selected,
    test_creating_a_public_session_works,
    test_creating_a_private_session_works,
    test_wrong_session_names_show_an_error,
    test_joining_a_session_does_not_close_the_screen,
    test_joining_without_selecting_a_session_shows_an_error,
    test_cannot_join_a_session_that_was_removed,
    test_cannot_join_a_session_that_was_made_private,
    test_removing_your_session_after_saying_yes,
    test_saying_no_keeps_the_session,
    test_cannot_remove_someone_elses_session,
    test_removing_without_selecting_a_session_shows_an_error,
    test_refresh_shows_sessions_added_by_other_people,
    test_database_problems_show_a_simple_message,
    test_logging_out_and_closing_give_different_results,
    test_unknown_screen_actions_are_ignored,
]
