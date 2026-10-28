import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker
from .config import get_settings
from .database import make_engine
from .cache import ProductCache
from .routers import products, admin_products, internal_products, health

log = logging.getLogger(__name__)

def create_app(settings=None, engine=None, cache=None):
    @asynccontextmanager
    async def lifespan(app):
        app.state.settings = settings or get_settings()
        app.state.engine = engine if engine is not None else make_engine(app.state.settings.database_url.get_secret_value())
        app.state.sessions = sessionmaker(bind=app.state.engine, expire_on_commit=False)
        app.state.cache = cache if cache is not None else ProductCache(app.state.settings.redis_url.get_secret_value(), app.state.settings.cache_ttl)
        try:
            yield
        finally:
            app.state.cache.close()
            if engine is None:
                app.state.engine.dispose()

    app = FastAPI(title='Product API', version='1.0.0', lifespan=lifespan)
    @app.exception_handler(SQLAlchemyError)
    async def database_error(request: Request, exc: SQLAlchemyError):
        # Do not log SQL parameters or credential-bearing URLs.
        log.error('Database operation failed: %s', type(exc).__name__)
        return JSONResponse(status_code=503, content={'detail': 'Database temporarily unavailable'})
    for module in (products, admin_products, internal_products, health):
        app.include_router(module.router)
    return app

app = create_app()
