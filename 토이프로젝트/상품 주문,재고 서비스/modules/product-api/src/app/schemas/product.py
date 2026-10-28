# 입출력 모델: 요청 검증 규칙과 API 응답 형식을 정의한다.
# 관련 기능과 배포 방법은 프로젝트의 docs/ 문서를 참고한다.

from datetime import datetime, timezone
from decimal import Decimal
from typing import Annotated, Literal
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator, model_validator

# 공통 타입을 재사용해 등록·수정의 검증 기준을 동일하게 유지한다.
Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
Price = Annotated[Decimal, Field(ge=0, le=9999999999, decimal_places=0, allow_inf_nan=False)]
Status = Literal['ON_SALE', 'STOPPED']

# 등록 요청: 알 수 없는 필드는 거부하고 상품명·가격을 필수로 받는다.
class ProductCreate(BaseModel):
    model_config = ConfigDict(extra='forbid')
    name: Name
    description: str | None = Field(default=None, max_length=10000)
    price: Price
    status: Status = 'STOPPED'

# 부분 수정 요청: 생략한 필드는 유지한다. 설명만 명시적인 null로 지울 수 있다.
class ProductUpdate(BaseModel):
    model_config = ConfigDict(extra='forbid')
    name: Name | None = None
    description: str | None = Field(default=None, max_length=10000)
    price: Price | None = None
    status: Status | None = None

    # 빈 수정 요청과 필수 컬럼을 null로 바꾸려는 요청을 거부한다.
    @model_validator(mode='after')
    def valid_patch(self):
        if not self.model_fields_set:
            raise ValueError('At least one field is required')
        for name in self.model_fields_set - {'description'}:
            if getattr(self, name) is None:
                raise ValueError(f'{name} cannot be null')
        return self

# SQLAlchemy 객체에서도 응답 모델을 만들 수 있다. Decimal 금액은 JSON에서 문자열이 된다.
class ProductRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    description: str | None
    price: Decimal
    status: Status
    created_at: datetime
    updated_at: datetime

    # DB의 시간대 없는 시각에 UTC를 붙여 클라이언트가 기준 시간대를 알 수 있게 한다.
    @field_validator('created_at', 'updated_at')
    @classmethod
    def utc_timestamp(cls, value):
        return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value

# 상품 목록과 페이지 정보·전체 건수를 하나의 응답으로 반환한다.
class ProductPage(BaseModel):
    items: list[ProductRead]
    page: int
    size: int
    total: int

# 한 번에 1~100개 ID만 받는다. 문자열·실수·bool을 ID로 자동 변환하지 않는다.
class LookupRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    product_ids: list[Annotated[int, Field(gt=0, strict=True)]] = Field(min_length=1, max_length=100)

# 주문 검증에 필요한 원본 필드만 반환한다. 재고나 가격 잠금 기능은 없다.
class LookupProduct(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    price: Decimal
    status: Status

# 찾은 상품과 존재하지 않는 ID를 분리한다. 누락 여부는 주문 API가 판단한다.
class LookupResponse(BaseModel):
    items: list[LookupProduct]
    missing_ids: list[int]
