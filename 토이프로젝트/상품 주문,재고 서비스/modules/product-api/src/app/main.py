# 앱 진입점: 설정·연결 자원을 준비하고 여러 라우터를 하나의 FastAPI 앱에 연결한다.
# 관련 기능과 배포 방법은 프로젝트의 docs/ 문서를 참고한다.

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

# 실행 환경에서는 실제 연결을 만들고 테스트에서는 대체 Engine·캐시를 주입할 수 있다.
def create_app(settings=None, engine=None, cache=None):
    # lifespan은 앱 시작 시 한 번 준비하고 종료 시 연결을 정리하는 구간이다.
    @asynccontextmanager
    async def lifespan(app):
        # 여러 요청에서 함께 쓸 설정·Engine·Session 생성기·캐시를 앱 상태에 보관한다.
        app.state.settings = settings or get_settings()
        app.state.engine = engine if engine is not None else make_engine(app.state.settings.database_url.get_secret_value())
        app.state.sessions = sessionmaker(bind=app.state.engine, expire_on_commit=False)
        app.state.cache = cache if cache is not None else ProductCache(app.state.settings.redis_url.get_secret_value(), app.state.settings.cache_ttl)
        try:
            # 준비가 끝나면 HTTP 요청을 처리한다. 앱 종료 시 finally 구간으로 돌아온다.
            yield
        finally:
            app.state.cache.close()
            # 이 함수가 만든 Engine만 종료한다. 외부에서 주입한 테스트 Engine은 호출자가 정리한다.
            if engine is None:
                app.state.engine.dispose()

    app = FastAPI(title='Product API', version='1.0.0', lifespan=lifespan)
    # DB 오류는 쿼리·접속정보를 노출하지 않고 통일된 503 응답으로 바꾼다.
    @app.exception_handler(SQLAlchemyError)
    async def database_error(request: Request, exc: SQLAlchemyError):
        # Do not log SQL parameters or credential-bearing URLs.
        log.error('Database operation failed: %s', type(exc).__name__)
        return JSONResponse(status_code=503, content={'detail': 'Database temporarily unavailable'})
    # 등록·수정·조회·상태 확인 모듈을 하나의 앱에 연결한다. 별도 컨테이너가 필요하지 않다.
    for module in (products, admin_products, internal_products, health):
        app.include_router(module.router)
    return app

# Uvicorn이 app.main:app으로 찾아 실행하는 실제 애플리케이션이다.
app = create_app()
