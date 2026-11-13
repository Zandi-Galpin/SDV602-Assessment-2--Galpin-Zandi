from pymongo import MongoClient
from pymongo.errors import PyMongoError
from bson.errors import InvalidId
from bson.objectid import ObjectId
import config


class DatabaseError(Exception):
    """Raised when database operations fails. Wraps the
    pymongo error so the rest of the app doesnt handle pymongo
    exceptions."""


class DatabaseManager:

    _instance = None

    def __init__(self):
        self.client = MongoClient(config.MONGO_URI,
                                  serverSelectionTimeoutMS=3000)
        self.client.admin.command("ping")

    @classmethod
    def getInstance(cls):
        if cls._instance is None:
            try:
                cls._instance = cls()
            except PyMongoError as e:
                raise DatabaseError("Could not connect to the database") from e
        return cls._instance

    def get_collection(self, collection):
        return self.client[config.DB_NAME][collection]

    def insert_one(self, collection, document):
        try:
            result = self.get_collection(collection).insert_one(document)
            return result.inserted_id
        except PyMongoError as e:
            raise DatabaseError(f"Could not save to {collection}") from e

    def find_one_by_id(self, collection, id):
        """The document with this id, or None if there isn't one (including
        when the id is not a valid i)."""
        try:
            return self.get_collection(collection).find_one(
                {"_id": ObjectId(id)})
        except (InvalidId, TypeError):
            return None
        except PyMongoError as e:
            raise DatabaseError(f"Could not read from {collection}") from e

    def find_one_by_name(self, collection, name):
        try:
            return self.get_collection(collection).find_one({"name": name})
        except PyMongoError as e:
            raise DatabaseError(f"Could not read from {collection}") from e

    def find_many(self, collection, query=None):
        """A list of every document matching the query (all of them if no query)."""
        try:
            return list(self.get_collection(collection).find(query or {}))
        except PyMongoError as e:
            raise DatabaseError(f"Could not read from {collection}") from e

    def delete_one_by_id(self, collection, id, **conditions):
        """Delete the document with this id, only if it matches the
        field values. Returns how many were deleted (0 or 1)."""
        try:
            query = {"_id": ObjectId(id), **conditions}
        except (InvalidId, TypeError):
            return 0
        try:
            return self.get_collection(collection).delete_one(
                query).deleted_count
        except PyMongoError as e:
            raise DatabaseError(f"Could not delete from {collection}") from e
