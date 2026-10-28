import asyncio

import httpx
from fastapi import FastAPI

from inventory_service.main import create_app as create_inventory_app
from order_service.main import create_app as create_order_app


async def post_order(
    order_app: FastAPI,
    product_id: str,
    quantity: int,
) -> httpx.Response:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=order_app),
        base_url="http://order",
    ) as client:
        return await client.post(
            "/api/v1/orders",
            json={"product_id": product_id, "quantity": quantity},
        )


def test_order_is_confirmed_when_stock_is_available(tmp_path):
    inventory_app = create_inventory_app(tmp_path / "inventory.db")
    order_app = create_order_app(
        tmp_path / "order.db",
        inventory_transport=httpx.ASGITransport(app=inventory_app),
    )

    async def scenario():
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=inventory_app),
            base_url="http://inventory",
        ) as inventory_client:
            stock_response = await inventory_client.post(
                "/api/v1/inventory/widget/stock",
                json={"quantity": 5},
            )
            assert stock_response.status_code == 200

        response = await post_order(order_app, "widget", 3)
        assert response.status_code == 201
        assert response.json()["status"] == "confirmed"

        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=inventory_app),
            base_url="http://inventory",
        ) as inventory_client:
            stock_response = await inventory_client.get(
                "/api/v1/inventory/widget"
            )
        assert stock_response.json()["available_quantity"] == 2

    asyncio.run(scenario())


def test_order_is_rejected_when_stock_is_insufficient(tmp_path):
    inventory_app = create_inventory_app(tmp_path / "inventory.db")
    order_app = create_order_app(
        tmp_path / "order.db",
        inventory_transport=httpx.ASGITransport(app=inventory_app),
    )

    async def scenario():
        response = await post_order(order_app, "missing-widget", 1)

        assert response.status_code == 201
        assert response.json()["status"] == "rejected"
        assert response.json()["rejection_reason"] == "insufficient_stock"

    asyncio.run(scenario())


def test_order_stays_pending_when_inventory_is_unavailable(tmp_path):
    def unavailable_inventory(_: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("inventory is unavailable")

    order_app = create_order_app(
        tmp_path / "order.db",
        inventory_transport=httpx.MockTransport(unavailable_inventory),
    )

    async def scenario():
        response = await post_order(order_app, "widget", 1)

        assert response.status_code == 202
        assert response.json()["status"] == "pending"

        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=order_app),
            base_url="http://order",
        ) as client:
            order_response = await client.get(
                f"/api/v1/orders/{response.json()['order_id']}"
            )
        assert order_response.json()["status"] == "pending"

    asyncio.run(scenario())


def test_repeated_reservation_does_not_decrement_stock_twice(tmp_path):
    inventory_app = create_inventory_app(tmp_path / "inventory.db")
    order_id = "order-123"

    async def scenario():
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=inventory_app),
            base_url="http://inventory",
        ) as client:
            await client.post(
                "/api/v1/inventory/widget/stock",
                json={"quantity": 5},
            )
            request = {
                "order_id": order_id,
                "product_id": "widget",
                "quantity": 2,
            }
            first = await client.post("/internal/v1/reservations", json=request)
            second = await client.post("/internal/v1/reservations", json=request)
            stock = await client.get("/api/v1/inventory/widget")

        assert first.json() == second.json()
        assert stock.json()["available_quantity"] == 3

    asyncio.run(scenario())
