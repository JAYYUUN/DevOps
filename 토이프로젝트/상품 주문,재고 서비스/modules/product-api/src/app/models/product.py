# 상품 ORM 모델: Python 객체와 products 테이블의 컬럼을 연결한다.
# 관련 기능과 배포 방법은 프로젝트의 docs/ 문서를 참고한다.

from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy import BigInteger, Integer, String, Text, Numeric, DateTime, CheckConstraint, Index
from sqlalchemy.dialects.mysql import DATETIME
from sqlalchemy.orm import Mapped, mapped_column
from ..database import Base

# DB에는 시간대 정보 없이 UTC를 저장한다. 응답할 때 UTC 시간대를 다시 표시한다.
def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)

# 상품 한 행의 구조다. 재고 수량과 주문 데이터는 이 서비스에 저장하지 않는다.
class Product(Base):
    __tablename__ = 'products'
    # API 검증을 우회한 쓰기도 막도록 가격·판매 상태의 DB 제약조건을 둔다.
    __table_args__ = (
        CheckConstraint('price >= 0 AND price <= 9999999999 AND price = FLOOR(price)', name='ck_price'),
        CheckConstraint("status IN ('ON_SALE', 'STOPPED')", name='ck_status'),
        # 판매 상태로 필터링한 뒤 상품 ID로 정렬하는 목록 조회를 지원한다.
        Index('ix_products_status_id', 'status', 'id'),
    )
    # MariaDB는 BIGINT 자동 증가를 사용한다. SQLite 테스트에서만 INTEGER로 바꾼다.
    id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, 'sqlite'), primary_key=True, autoincrement=True)
    # 상품 기본 정보다. 설명은 생략 가능하므로 NULL을 허용한다.
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    # 금액은 부동소수점 대신 DECIMAL로 저장한다. 소수 금액은 별도 검증으로 막는다.
    price: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    # 신규 상품은 기본적으로 판매 중지다. 준비가 끝나면 ON_SALE로 바꾼다.
    status: Mapped[str] = mapped_column(String(20), default='STOPPED')
    # 생성·수정 시각은 서버가 관리한다. MariaDB에서는 마이크로초까지 보관한다.
    created_at: Mapped[datetime] = mapped_column(DateTime().with_variant(DATETIME(fsp=6), "mysql"), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime().with_variant(DATETIME(fsp=6), "mysql"), default=utcnow, onupdate=utcnow)
