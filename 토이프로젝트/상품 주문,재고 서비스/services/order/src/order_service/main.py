import logging
import os
import sqlite3
import uuid
from pathlib import Path
from typing import Annotated

import httpx
from fastapi import FastAPI, HTTPException, Path as PathParameter, Response, status
from pydantic import BaseModel, Field, ValidationError

from order_service.database import (
    create_order,
    get_order,
    initialize_database,
    update_order_result,
)

logger = logging.getLogger(__name__)


class OrderInput(BaseModel):
    product_id: str = Field(min_length=1, max_length=128)
    quantity: int = Field(gt=0)


class OrderResponse(BaseModel):
    order_id: str
    product_id: str
    quantity: int
    status: str
    rejection_reason: str | None


class InventoryReservationResponse(BaseModel):
    order_id: str
    product_id: str
    quantity: int
    reserved: bool
    reason: str | None


def serialize_order(row: sqlite3.Row) -> OrderResponse:
    return OrderResponse(
        order_id=row["order_id"],
        product_id=row["product_id"],
        quantity=row["quantity"],
        status=row["status"],
        rejection_reason=row["rejection_reason"],
    )


def create_app(
    database_path: Path | None = None,
    inventory_url: str | None = None,
    inventory_transport: httpx.AsyncBaseTransport | None = None,
) -> FastAPI:
    db_path = database_path or Path(os.getenv("ORDER_DATABASE_PATH", "data/order.db"))
    service_url = inventory_url or os.getenv(
        "INVENTORY_SERVICE_URL",
        "http://127.0.0.1:8001",
    )
    initialize_database(db_path)

    app = FastAPI(title="Order Service")

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post(
        "/api/v1/orders",
        response_model=OrderResponse,
        status_code=status.HTTP_201_CREATED,
    )
    async def submit_order(
        body: OrderInput,
        response: Response,
    ) -> OrderResponse:
        order_id = str(uuid.uuid4())
        create_order(db_path, order_id, body.product_id, body.quantity)

        try:
            async with httpx.AsyncClient(
                base_url=service_url,
                timeout=2.0,
                transport=inventory_transport,
            ) as client:
                inventory_response = await client.post(
                    "/internal/v1/reservations",
                    json={
                        "order_id": order_id,
                        "product_id": body.product_id,
                        "quantity": body.quantity,
                    },
                )
                inventory_response.raise_for_status()
                reservation = InventoryReservationResponse.model_validate(
                    inventory_response.json()
                )
                if (
                    reservation.order_id != order_id
                    or reservation.product_id != body.product_id
                    or reservation.quantity != body.quantity
                ):
                    raise ValueError("inventory response does not match the order")
        except (httpx.HTTPError, ValidationError, ValueError) as error:
            logger.warning(
                "Inventory result unavailable for order %s; leaving it pending: %s",
                order_id,
                error,
            )
            response.status_code = status.HTTP_202_ACCEPTED
            return serialize_order(get_order(db_path, order_id))

        order_status = "confirmed" if reservation.reserved else "rejected"
        rejection_reason = None if reservation.reserved else reservation.reason
        updated_order = update_order_result(
            db_path,
            order_id,
            order_status,
            rejection_reason,
        )
        return serialize_order(updated_order)

    @app.get("/api/v1/orders/{order_id}", response_model=OrderResponse)
    def read_order(
        order_id: Annotated[str, PathParameter(min_length=1, max_length=64)],
    ) -> OrderResponse:
        order = get_order(db_path, order_id)
        if order is None:
            raise HTTPException(status_code=404, detail="order not found")
        return serialize_order(order)

    return app


app = create_app()
