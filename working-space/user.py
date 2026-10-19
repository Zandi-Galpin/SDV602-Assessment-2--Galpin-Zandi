import bcrypt
from database_manager import DatabaseManager, DatabaseError
import config


class AuthResult:
    """sends the outcome of a login/register attempt to the UI layer"""

    def __init__(self, success, outcome, message, user=None):
        self.success = success
        self.outcome = outcome  #'success', 'no_user', 'wrong_password', 'connection_error', 'duplicate_username'
        self.message = message
        self.user = user


class User:

    def __init__(self, username, password_hash):
        self.username = username
        self.password_hash = password_hash

    @staticmethod
    def _hash_password(password):
        return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())

    @staticmethod
    def _verify_password(password, stored_hash):
        if isinstance(stored_hash, str):
            stored_hash = stored_hash.encode('utf-8')
        return bcrypt.checkpw(password.encode('utf-8'), stored_hash)

    @classmethod
    def register(cls, username, password):
        try:
            db = DatabaseManager.getInstance()

            if db.find_one_by_username(config.USERS_COLLECTION, username):
                return AuthResult(False, 'duplicate_username',
                                   f"Username '{username}' is already taken.")

            password_hash = cls._hash_password(password)
            db.insert_one(config.USERS_COLLECTION, {
                "username": username,
                "password_hash": password_hash,
            })

            return AuthResult(True, 'registered', "Account created successfully.",
                               user=cls(username, password_hash))

        except DatabaseError:
            return AuthResult(False, 'connection_error',
                               "Could not reach the database. Please try again later.")

    @classmethod
    def authenticate(cls, username, password):
        try:
            db = DatabaseManager.getInstance()
            document = db.find_one_by_username(config.USERS_COLLECTION, username)

            if document is None:
                return AuthResult(False, 'no_user', "No account found with that username.")

            if not cls._verify_password(password, document["password_hash"]):
                return AuthResult(False, 'wrong_password', "Incorrect password.")

            return AuthResult(True, 'success', "Logged in successfully.",
                               user=cls(username, document["password_hash"]))

        except DatabaseError:
            return AuthResult(False, 'connection_error',
                               "Could not reach the database. Please try again later.")