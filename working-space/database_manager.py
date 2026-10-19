from pymongo import MongoClient
from bson.objectid import ObjectId
import config
from pymongo.errors import PyMongoError

class DatabaseError(Exception):
    """happens whenever a database operation fails, 
    wraps whatever error caused it"""
    pass

class DatabaseManager:

    _instance = None

    def __init__(self):
        self.client = MongoClient(config.MONGO_URI)
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

    def find_one_by_username(self, collection, username):
        try:
            return self.get_collection(collection).find_one({"username": username})
        except PyMongoError as e:
            raise DatabaseError(f"Could not read from {collection}") from e