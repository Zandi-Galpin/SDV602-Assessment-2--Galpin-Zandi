from pymongo import MongoClient
from pymongo.errors import PyMongoError
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
            return self.get_collection(collection).insert_one(document).inserted_id
        except PyMongoError as e:
            raise DatabaseError(f"Could not save to {collection}") from e

    def find_one_by_id(self, collection, id):
        try:
            return self.get_collection(collection).find_one({"_id": ObjectId(id)})
        except PyMongoError as e:
            raise DatabaseError(f"Could not read from {collection}") from e

    def find_one_by_name(self, collection, name):
        try:
            return self.get_collection(collection).find_one({"name": name})
        except PyMongoError as e:
            raise DatabaseError(f"Could not read from {collection}") from e