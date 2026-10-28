# DB 공통 설정: 연결을 준비하고 요청마다 사용할 작업 단위(Session)를 제공한다.
# 관련 기능과 배포 방법은 프로젝트의 docs/ 문서를 참고한다.

from fastapi import Request
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from .config import get_settings

# 모든 ORM 모델의 공통 부모다. 자식 모델의 테이블 정의를 metadata에 모은다.
class Base(DeclarativeBase):
    pass

# Engine은 DB 연결을 관리한다. 여기서는 테이블 생성이나 쿼리를 실행하지 않는다.
def make_engine(url):
    # SQLite는 테스트용이고 MariaDB는 PyMySQL로 연결한다. 접속 제한 시간을 둔다.
    options = {'connect_args': {'check_same_thread': False}} if url.startswith('sqlite') else {'connect_args': {'connect_timeout': 3}}
    # pool_pre_ping으로 재사용할 연결이 끊어졌는지 먼저 확인한다.
    return create_engine(url, pool_pre_ping=True, **options)

# FastAPI Depends가 요청별 Session을 주입한다. 요청 종료 시 연결을 반납한다.
def get_session(request: Request):
    # commit은 서비스에서 수행한다. 예외로 미완료 트랜잭션이 남으면 close 시 취소된다.
    with request.app.state.sessions() as session:
        yield session
