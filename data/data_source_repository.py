from datetime import datetime, timezone

import config
from data.database_manager import DatabaseManager
from data.session_repository import SessionError
from model.data_source import DataError, DataSource

MAX_ROWS = 20000
SESSION_GONE = "That session no longer exists."

def _to_source(document):
    columns = document["columns"]
    rows = [dict(zip(columns, values)) for values in document["rows"]]
    parts = document.get("parts") or [document["name"]]
    source = DataSource(parts[0], columns, rows)
    source.part_names = list(parts)
    return source


class DataSourceRepository:
    def __init__(self, db=None):
        self.db = db if db is not None else DatabaseManager.getInstance()

    def upload(self, session_id, source, uploaded_by):
        """Stores a data source for a session and make it the session's
        current source. Returns the new source id. Rows are kept as lists in column order"""
        if len(source.rows) > MAX_ROWS:
            raise DataError(f"{source.name} has too many rows to upload (the limit is {MAX_ROWS:,}).")

        source_id = str(self.db.insert_one(config.DATA_SOURCES_COLLECTION, {
            "session_id": session_id,
            "name": source.name,
            "parts": list(source.part_names),
            "columns": list(source.columns),
            "rows": [[row.get(column, "") for column in source.columns] for row in source.rows],
            "uploaded_by": uploaded_by,
            "uploaded": datetime.now(timezone.utc),
        }))

        matched = self.db.update_one_by_id(
            config.SESSIONS_COLLECTION, session_id, {"source_id": source_id})
        if matched == 0:
            #The session was deleted while uploading: do not leave uploaded data behind
            self.db.delete_one_by_id(config.DATA_SOURCES_COLLECTION, source_id)
            raise SessionError(SESSION_GONE)
        return source_id

    def current_id(self, session_id):
        """The id of the sessions current data source, or None if nothing
        has been uploaded yet. Raises SessionError if the session is gone."""
        session = self.db.find_one_by_id(config.SESSIONS_COLLECTION, session_id)
        if session is None:
            raise SessionError(SESSION_GONE)
        return session.get("source_id")

    def load_current(self, session_id):
        """(source_id, DataSource) for the session's current source, or None if it has none."""
        source_id = self.current_id(session_id)
        if source_id is None:
            return None
        document = self.db.find_one_by_id(config.DATA_SOURCES_COLLECTION, source_id)
        if document is None:
            return None
        return source_id, _to_source(document)