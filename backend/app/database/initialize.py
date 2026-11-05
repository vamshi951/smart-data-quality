from sqlalchemy.engine import Engine

from app.database.base import Base
from app.models import CleaningRun, Dataset


def initialize_database(engine: Engine) -> None:
    Base.metadata.create_all(bind=engine)


__all__ = ["CleaningRun", "Dataset", "initialize_database"]
