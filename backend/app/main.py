from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from fastapi import FastAPI
from sqlalchemy.engine import Engine

from app.api.routers.datasets import router as datasets_router
from app.api.routers.health import router as health_router
from app.core.config import Settings, get_settings
from app.core.error_handlers import register_error_handlers
from app.core.logging import configure_logging
from app.database.engine import create_database_engine
from app.database.initialize import initialize_database
from app.database.session import create_session_factory


def create_app(
    settings: Settings | None = None,
    database_engine: Engine | None = None,
) -> FastAPI:
    app_settings = settings or get_settings()
    configure_logging(app_settings.log_level)
    engine = database_engine or create_database_engine(app_settings.database_url)

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        initialize_database(engine)
        application.state.database_engine = engine
        application.state.session_factory = create_session_factory(engine)
        yield
        engine.dispose()

    application = FastAPI(
        title=app_settings.app_name,
        version="0.1.0",
        lifespan=lifespan,
    )
    application.state.settings = app_settings
    register_error_handlers(application)
    application.include_router(health_router)
    application.include_router(datasets_router)
    return application


app = create_app()
