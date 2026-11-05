import logging

from app.core.config import BackendLogLevel


def configure_logging(log_level: BackendLogLevel) -> None:
    logging.basicConfig(
        level=getattr(logging, log_level),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
