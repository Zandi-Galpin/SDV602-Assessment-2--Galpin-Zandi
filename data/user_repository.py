import bcrypt

import config
from data.database_manager import DatabaseManager
from model.user import User


class AuthError(Exception):
    """any expected login or registration failure. The message is written
    for the user and can be displayed."""


class UserRepository:
    def __init__(self):
        self.db = DatabaseManager.getInstance()

    def login(self, username, password):
        username = (username or "").strip()
        if not username or not password:
            raise AuthError("Please enter both a username and password.")

        stored_user = self.db.find_one_by_name(config.USER_COLLECTION, username)
        if not stored_user:
            raise AuthError("No account found with that username.")

        if not bcrypt.checkpw(password.encode("utf-8"), stored_user["password"]):
            raise AuthError("Incorrect password.")

        return User(username, stored_user["password"])

    def create_user(self, username, password):
        username = (username or "").strip()
        if not username or not password:
            raise AuthError("Please enter both a username and password.")

        if self.db.find_one_by_name(config.USER_COLLECTION, username):
            raise AuthError("That username is already taken.")

        password_hash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())

        return self.db.insert_one(config.USER_COLLECTION, {
            "name": username,
            "password": password_hash,
        })