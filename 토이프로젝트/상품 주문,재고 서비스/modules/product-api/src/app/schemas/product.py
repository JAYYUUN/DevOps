from datetime import datetime, timezone
from decimal import Decimal
from typing import Annotated, Literal
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator, model_validator

Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
Price = Annotated[Decimal, Field(ge=0, le=9999999999, decimal_places=0, allow_inf_nan=False)]
Status = Literal['ON_SALE', 'STOPPED']

class ProductCreate(BaseModel):
    model_config = ConfigDict(extra='forbid')
    name: Name
    description: str | None = Field(default=None, max_length=10000)
    price: Price
    status: Status = 'STOPPED'

class ProductUpdate(BaseModel):
    model_config = ConfigDict(extra='forbid')
    name: Name | None = None
    description: str | None = Field(default=None, max_length=10000)
    price: Price | None = None
    status: Status | None = None

    @model_validator(mode='after')
    def valid_patch(self):
        if not self.model_fields_set:
            raise ValueError('At least one field is required')
        for name in self.model_fields_set - {'description'}:
            if getattr(self, name) is None:
                raise ValueError(f'{name} cannot be null')
        return self

class ProductRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    description: str | None
    price: Decimal
    status: Status
    created_at: datetime
    updated_at: datetime

    @field_validator('created_at', 'updated_at')
    @classmethod
    def utc_timestamp(cls, value):
        return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value

class ProductPage(BaseModel):
    items: list[ProductRead]
    page: int
    size: int
    total: int

class LookupRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    product_ids: list[Annotated[int, Field(gt=0, strict=True)]] = Field(min_length=1, max_length=100)

class LookupProduct(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    price: Decimal
    status: Status

class LookupResponse(BaseModel):
    items: list[LookupProduct]
    missing_ids: list[int]
