"""Headless testing. doesnt open windows. Each test builds its own fresh
state so tests cant effect each other.

Database tests use a separate test database that gets wiped before each
test and at the end. The real database isnt touched.
"""
import contextlib
import io

import bcrypt
import FreeSimpleGUI as sg

import config
from app import build_parser
from controller.login_controller import LoginController
from controller.register_controller import RegisterController
from data.user_repository import AuthError, UserRepository
from tests.fakes import BrokenDatabase, FakeView
from tests import test_local_mode
from tests import test_des, test_local_mode
from tests.helpers import TEST_DB_NAME, reset_database
from tests import test_sessions

EMPTY_MSG = "Please enter both a username and password."


def fresh_repo():
    reset_database()
    return UserRepository()


def creds(username, password, confirm=None):
    values = {"-USERNAME-": username, "-PASSWORD-": password}
    if confirm is not None:
        values["-CONFIRM_PASSWORD-"] = confirm
    return values


def expect_auth_error(func, expected_message):
    try:
        func()
    except AuthError as e:
        assert str(e) == expected_message, \
            f"expected '{expected_message}', got '{e}'"
        return
    raise AssertionError(f"no AuthError raised: {expected_message}")


#repository tests

def test_register_login_succeed():
    repo = fresh_repo()
    repo.create_user("alice", "pw123")
    user = repo.login("alice", "pw123")
    assert user.name == "alice", f"expected alice, got {user.name}"


def test_password_stored_as_hashed():
    repo = fresh_repo()
    repo.create_user("alice", "pw123")
    stored = repo.db.find_one_by_name(config.USER_COLLECTION, "alice")
    assert stored["password"] != b"pw123", "password stord as plain text"
    assert bcrypt.checkpw(b"pw123", stored["password"]), "stored value is not a bcrypt hash of the password"


def test_duplicate_usernames_are_rejected():
    repo = fresh_repo()
    repo.create_user("alice", "pw123")
    expect_auth_error(lambda: repo.create_user("alice", "other"), "That username is already taken.")


def test_login_for_unknown_user():
    repo = fresh_repo()
    expect_auth_error(lambda: repo.login("nobody", "pw123"), "No account found with that username.")


def test_login_for_wrong_password():
    repo = fresh_repo()
    repo.create_user("alice", "pw123")
    expect_auth_error(lambda: repo.login("alice", "wrong"), "Incorrect password.")


def test_that_empty_credentials_are_rejected():
    repo = fresh_repo()
    expect_auth_error(lambda: repo.login("alice", ""), EMPTY_MSG)
    expect_auth_error(lambda: repo.login("", "pw123"), EMPTY_MSG)
    expect_auth_error(lambda: repo.login("   ", "pw123"), EMPTY_MSG)
    expect_auth_error(lambda: repo.create_user("", "pw123"), EMPTY_MSG)
    expect_auth_error(lambda: repo.create_user("alice", ""), EMPTY_MSG)


def test_too_long_passwords_are_rejected():
    repo = fresh_repo()
    expect_auth_error(lambda: repo.create_user("alice", "x" * 100), "Password is too long (72 bytes maximum).")
    repo.create_user("alice", "pw123")
    expect_auth_error(lambda: repo.login("alice", "x" * 100),"Incorrect password.")


#controller tests (fake view)

def test_login_controller_so_a_wrong_password_shows_message():
    repo = fresh_repo()
    repo.create_user("alice", "pw123")
    view = FakeView([
        ("Login", creds("alice", "wrong")),
        (sg.WIN_CLOSED, {}),
    ])
    result = LoginController(repo, view).run()
    assert result is None, "no user should be returned"
    assert view.errors == ["Incorrect password."], view.errors


def test_login_controller_so_a_success_returns_a_user():
    repo = fresh_repo()
    repo.create_user("alice", "pw123")
    view = FakeView([("Login", creds("alice", "pw123"))])
    user = LoginController(repo, view).run()
    assert user is not None and user.name == "alice"
    assert view.messages == ["Login successful"], view.messages
    assert view.closed, "login window should be closed for success"


def test_login_controller_database_failure_message():
    repo = UserRepository(db=BrokenDatabase())
    view = FakeView([
        ("Login", creds("alice", "pw123")),
        (sg.WIN_CLOSED, {}),
    ])
    LoginController(repo, view).run()
    assert len(view.errors) == 1, view.errors
    assert "Could not reach the database" in view.errors[0], view.errors


def test_register_controller_password_not_matching():
    repo = fresh_repo()
    view = FakeView([
        ("Register", creds("alice", "pw123", confirm="different")),
        (sg.WIN_CLOSED, {}),
    ])
    RegisterController(repo, view).run()
    assert view.errors == ["Passwords do not match."], view.errors
    stored = repo.db.find_one_by_name(config.USER_COLLECTION, "alice")
    assert stored is None, "user should not have been created"


def test_register_controller_success_makes_user():
    repo = fresh_repo()
    view = FakeView([
        ("Register", creds("alice", "pw123", confirm="pw123")),
    ])
    RegisterController(repo, view).run()
    assert view.messages == ["Registration successful"], view.messages
    assert repo.login("alice", "pw123").name == "alice"


#command line tests

def test_that_the_cli_accepts_each_mode():
    parser = build_parser()
    assert parser.parse_args(["local"]).mode == "local"
    assert parser.parse_args(["local", "--file", "a.csv"]).file == "a.csv"
    remote = parser.parse_args(["remote", "--uri", "mongodb://x", "--db", "d"])
    assert (remote.uri, remote.db) == ("mongodb://x", "d")
    assert parser.parse_args(["test", "--fullinfo"]).fullinfo is True


def test_that_the_cli_rejects_bad_input():
    parser = build_parser()
    for bad in ([], ["dfasdfa"], ["local", "--aaaa"]):
        with contextlib.redirect_stderr(io.StringIO()):
            try:
                parser.parse_args(bad)
            except SystemExit:
                continue
        raise AssertionError(f"parser accepted bad arguments: {bad}")


ALL_TESTS = [
    test_register_login_succeed,
    test_password_stored_as_hashed,
    test_duplicate_usernames_are_rejected,
    test_login_for_unknown_user,
    test_login_for_wrong_password,
    test_that_empty_credentials_are_rejected,
    test_too_long_passwords_are_rejected,
    test_login_controller_so_a_wrong_password_shows_message,
    test_login_controller_so_a_success_returns_a_user,
    test_login_controller_database_failure_message,
    test_register_controller_password_not_matching,
    test_register_controller_success_makes_user,
    test_that_the_cli_accepts_each_mode,
    test_that_the_cli_rejects_bad_input,
]

ALL_TESTS += (test_local_mode.ALL_TESTS + test_des.ALL_TESTS + test_sessions.ALL_TESTS)

def run_all():
    """Runs each test, catching any problems per test so a bad test doesnt
    stop the rest. Returns {'passed': [...], 'failed': [...],
    'errors': [...]}: failed means an assert failed, errors means
    something unexpected happened.."""
    original_db = config.DB_NAME
    config.DB_NAME = TEST_DB_NAME
    results = {"passed": [], "failed": [], "errors": []}

    try:
        for test in ALL_TESTS:
            name = test.__name__
            try:
                test()
                results["passed"].append(name)
            except AssertionError as e:
                results["failed"].append((name, str(e)))
            except Exception as e:
                results["errors"].append((name, repr(e)))
        try:
            reset_database()
        except Exception:
            pass #the database may be unreachable
    finally:
        config.DB_NAME = original_db

    return results


def print_results(results, fullinfo=False):
    total = sum(len(group) for group in results.values())
    print(f"Ran {total} tests: {len(results['passed'])} passed, "
          f"{len(results['failed'])} failed, "
          f"{len(results['errors'])} errors.")

    if fullinfo:
        for name in results["passed"]:
            print(f"PASSED {name}")
    for name, message in results["failed"]:
        print(f"FAILED {name}: {message}")
    for name, error in results["errors"]:
        print(f"ERROR {name}: {error}")