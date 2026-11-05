from pathlib import Path

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.engine.interfaces import DBAPIConnection
from sqlalchemy.engine import make_url
from sqlalchemy.pool import ConnectionPoolEntry


def create_database_engine(database_url: str) -> Engine:
    url = make_url(database_url)
    connect_args: dict[str, object] = {}
    engine_options: dict[str, object] = {"pool_pre_ping": True}

    if url.drivername.startswith("sqlite"):
        connect_args["check_same_thread"] = False
        database = url.database
        if database and database != ":memory:" and not database.startswith("file:"):
            Path(database).expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)
        if database in (None, "", ":memory:"):
            from sqlalchemy.pool import StaticPool

            engine_options["poolclass"] = StaticPool

    engine = create_engine(
        url,
        connect_args=connect_args,
        **engine_options,
    )

    if url.drivername.startswith("sqlite"):
        @event.listens_for(engine, "connect")
        def enable_sqlite_foreign_keys(
            dbapi_connection: DBAPIConnection,
            _connection_record: ConnectionPoolEntry,
        ) -> None:
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    return engine
