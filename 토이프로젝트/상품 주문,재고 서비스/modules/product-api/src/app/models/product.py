from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy import BigInteger, Integer, String, Text, Numeric, DateTime, CheckConstraint, Index
from sqlalchemy.dialects.mysql import DATETIME
from sqlalchemy.orm import Mapped, mapped_column
from ..database import Base

def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)

class Product(Base):
    __tablename__ = 'products'
    __table_args__ = (
        CheckConstraint('price >= 0 AND price <= 9999999999 AND price = FLOOR(price)', name='ck_price'),
        CheckConstraint("status IN ('ON_SALE', 'STOPPED')", name='ck_status'),
        Index('ix_products_status_id', 'status', 'id'),
    )
    id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, 'sqlite'), primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    price: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    status: Mapped[str] = mapped_column(String(20), default='STOPPED')
    created_at: Mapped[datetime] = mapped_column(DateTime().with_variant(DATETIME(fsp=6), "mysql"), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime().with_variant(DATETIME(fsp=6), "mysql"), default=utcnow, onupdate=utcnow)
