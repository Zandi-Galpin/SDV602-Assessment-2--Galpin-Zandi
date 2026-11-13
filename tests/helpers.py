"""Helpers shared by the database tests."""
import config
from data.database_manager import DatabaseManager

TEST_DB_NAME = "SDV602_test_database"

def reset_database():
    """Wipe the test database. doesnt run against anything else."""
    if config.DB_NAME != TEST_DB_NAME:
        raise RuntimeError("Refusing to wipe a non-test database")
    DatabaseManager.getInstance().client.drop_database(config.DB_NAME)