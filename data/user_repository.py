import bcrypt

import config
from data.database_manager import DatabaseManager
from model.user import User

MAX_PASSWORD_BYTES = 72  # bcrypt cannot hash anything longer


class AuthError(Exception):
    """any expected login or registration failure. The message is written
    for the user and can be displayed."""


class UserRepository:
    def __init__(self, db=None):
        self.db = db if db is not None else DatabaseManager.getInstance()

    def login(self, username, password):
        username = (username or "").strip()
        if not username or not password:
            raise AuthError("Please enter both a username and password.")

        stored_user = self.db.find_one_by_name(
            config.USER_COLLECTION, username)
        if not stored_user:
            raise AuthError("No account found with that username.")

        password_bytes = password.encode("utf-8")
        if (len(password_bytes) > MAX_PASSWORD_BYTES
                or not bcrypt.checkpw(password_bytes,
                                      stored_user["password"])):
            raise AuthError("Incorrect password.")

        return User(username, stored_user["password"])

    def create_user(self, username, password):
        username = (username or "").strip()
        if not username or not password:
            raise AuthError("Please enter both a username and password.")

        password_bytes = password.encode("utf-8")
        if len(password_bytes) > MAX_PASSWORD_BYTES:
            raise AuthError("Password is too long (72 bytes maximum).")

        if self.db.find_one_by_name(config.USER_COLLECTION, username):
            raise AuthError("That username is already taken.")

        password_hash = bcrypt.hashpw(password_bytes, bcrypt.gensalt())

        return self.db.insert_one(config.USER_COLLECTION, {
            "name": username,
            "password": password_hash,
        })
