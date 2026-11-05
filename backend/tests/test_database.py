from sqlalchemy import inspect, text

from app.database.engine import create_database_engine
from app.database.initialize import initialize_database


def test_initialize_database_creates_expected_schema(tmp_path):
    database_url = f"sqlite:///{tmp_path / 'test.db'}"
    engine = create_database_engine(database_url)

    try:
        initialize_database(engine)

        inspector = inspect(engine)
        assert set(inspector.get_table_names()) == {"datasets", "cleaning_runs"}
        assert {
            index["name"] for index in inspector.get_indexes("cleaning_runs")
        } >= {"ix_cleaning_runs_dataset_created"}
        assert inspector.get_foreign_keys("cleaning_runs")[0]["options"]["ondelete"] == "CASCADE"
        with engine.connect() as connection:
            assert connection.execute(text("PRAGMA foreign_keys")).scalar_one() == 1
    finally:
        engine.dispose()
