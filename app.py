"""
    entry point.
    possible starts:

    python app.py local [--file data/example.csv]
    python app.py remote [--uri mongodb://host:27017] [--db NAME]
    python app.py test [--fullinfo]
"""
import argparse
import sys

import FreeSimpleGUI as sg

import config
from controller.chat_controller import ChatController
from controller.login_controller import LoginController
from data.database_manager import DatabaseError
from data.message_repository import MessageRepository
from data.user_repository import UserRepository
from controller.des_controller import DesController
from controller.session_controller import SessionController
from data.session_repository import SessionRepository

class App:
    """Remote mode: login, then chat (sessions replace chat later)."""

    def __init__(self):
        self.user_repository = UserRepository()
        self.message_repository = MessageRepository()
        self.session_repository = SessionRepository()

    def run(self):
        while True:
            user = LoginController(self.user_repository).run()
            if not user:
                break

            result = SessionController(
                user, self.session_repository, self.open_session).run()
            if result != "logout":
                break

    def open_session(self, session, user):
        ChatController(user.name, self.message_repository, session).run()


def build_parser():
    parser = argparse.ArgumentParser(description="Data Explorer")
    subparsers = parser.add_subparsers(dest="mode", required=True)

    local = subparsers.add_parser("local", help="view CSV files from disk")
    local.add_argument("--file", help="CSV file to open on start")

    remote = subparsers.add_parser("remote", help="log in and use the remote server")
    remote.add_argument("--uri", help="MongoDB connection string")
    remote.add_argument("--db", help="database name to use")

    test = subparsers.add_parser("test", help="run the headless tests")
    test.add_argument("--fullinfo", action="store_true", help="list every passing test too")

    return parser


def run_local(args):
    DesController().run(args.file)
    return 0


def run_remote(args):
    if args.uri:
        config.MONGO_URI = args.uri
    if args.db:
        config.DB_NAME = args.db

    try:
        App().run()
    except DatabaseError as e:
        sg.popup_error(f"{e}. Check the database server is running "
                       "and try again.")
        return 1
    return 0


def run_tests(args):
    from tests.test_runner import run_all, print_results

    results = run_all()
    print_results(results, fullinfo=args.fullinfo)
    failed = results["failed"] or results["errors"]
    return 1 if failed else 0


def main(argv=None):
    args = build_parser().parse_args(argv)

    if args.mode == "local":
        return run_local(args)
    if args.mode == "remote":
        return run_remote(args)
    return run_tests(args)


if __name__ == "__main__":
    sys.exit(main())