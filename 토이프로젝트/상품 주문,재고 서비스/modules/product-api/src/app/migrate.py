# 초기 DB 준비 명령: API 실행과 별도로 테이블을 생성하고 적용 이력을 남긴다.
# 관련 기능과 배포 방법은 프로젝트의 docs/ 문서를 참고한다.

"""Run explicitly before deploying the API; never run on every Pod startup."""
from sqlalchemy import text
from .config import get_settings
from .database import make_engine, Base
from .models.product import Product

# DATABASE_URL로 연결한다. DB와 사용자 계정 자체는 미리 생성되어 있어야 한다.
def main():
    engine = make_engine(get_settings().database_url.get_secret_value())
    try:
        # 성공하면 commit, 예외면 rollback한다. 단, MariaDB DDL은 암묵적 commit이 있을 수 있다.
        with engine.begin() as conn:
            conn.execute(text('CREATE TABLE IF NOT EXISTS schema_migrations (version VARCHAR(40) PRIMARY KEY)'))
            # 001_products 적용 이력이 있으면 초기 테이블 생성을 반복하지 않는다.
            version = conn.execute(text("SELECT version FROM schema_migrations WHERE version='001_products'")).first()
            if version is None:
                # Initial migration only. Future schema changes need new versioned scripts.
                # 없는 테이블만 생성한다. 기존 테이블의 컬럼 변경이나 스키마 비교는 하지 않는다.
                Base.metadata.create_all(conn)
                conn.execute(text("INSERT INTO schema_migrations (version) VALUES ('001_products')"))
    # 성공·실패와 무관하게 연결 풀을 정리한다. 마이그레이션은 동시에 실행하지 않는다.
    finally:
        engine.dispose()

# python -m app.migrate로 직접 실행할 때만 초기 DB 준비를 수행한다.
if __name__ == '__main__':
    main()
