import os
from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, HTTPException, Path as PathParameter
from pydantic import BaseModel, Field

from inventory_service.database import (
    add_stock,
    get_available_quantity,
    initialize_database,
    reserve_stock,
)


class QuantityInput(BaseModel):
    quantity: int = Field(gt=0)


class ReservationInput(BaseModel):
    order_id: str = Field(min_length=1, max_length=64)
    product_id: str = Field(min_length=1, max_length=128)
    quantity: int = Field(gt=0)


class StockResponse(BaseModel):
    product_id: str
    available_quantity: int


class ReservationResponse(BaseModel):
    order_id: str
    product_id: str
    quantity: int
    reserved: bool
    reason: str | None


def create_app(database_path: Path | None = None) -> FastAPI:
    db_path = database_path or Path(
        os.getenv("INVENTORY_DATABASE_PATH", "data/inventory.db")
    )
    initialize_database(db_path)

    app = FastAPI(title="Inventory Service")

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post(
        "/api/v1/inventory/{product_id}/stock",
        response_model=StockResponse,
    )
    def receive_stock(
        product_id: Annotated[str, PathParameter(min_length=1, max_length=128)],
        body: QuantityInput,
    ) -> StockResponse:
        available = add_stock(db_path, product_id, body.quantity)
        return StockResponse(product_id=product_id, available_quantity=available)

    @app.get(
        "/api/v1/inventory/{product_id}",
        response_model=StockResponse,
    )
    def read_stock(
        product_id: Annotated[str, PathParameter(min_length=1, max_length=128)],
    ) -> StockResponse:
        available = get_available_quantity(db_path, product_id)
        return StockResponse(product_id=product_id, available_quantity=available)

    @app.post(
        "/internal/v1/reservations",
        response_model=ReservationResponse,
    )
    def create_reservation(body: ReservationInput) -> ReservationResponse:
        try:
            reservation = reserve_stock(
                db_path,
                body.order_id,
                body.product_id,
                body.quantity,
            )
        except ValueError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error

        return ReservationResponse(
            order_id=reservation["order_id"],
            product_id=reservation["product_id"],
            quantity=reservation["quantity"],
            reserved=reservation["status"] == "reserved",
            reason=reservation["reason"],
        )

    return app


app = create_app()
