from fastapi import APIRouter, BackgroundTasks, HTTPException

from app.schemas.order import OrderCreateRequest, OrderResponse
from app.services.order_service import OrderServiceDep

router = APIRouter(prefix="/orders", tags=["orders"])


@router.post("/", status_code=201)
async def create_order(
    payload: OrderCreateRequest,
    order_service: OrderServiceDep,
    background_tasks: BackgroundTasks,
) -> OrderResponse:
    order = await order_service.create_order(
        payload.model_dump(exclude_none=True), background_tasks
    )
    return OrderResponse.model_validate(order)


@router.get("/by-token/{token}")
async def get_order_by_token(
    token: str, order_service: OrderServiceDep
) -> OrderResponse:
    order = await order_service.get_order_by_token(token)
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")
    return OrderResponse.model_validate(order)


@router.get("/{order_id}")
async def get_order(order_id: int, order_service: OrderServiceDep) -> OrderResponse:
    order = await order_service.get_order(order_id)
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")
    return OrderResponse.model_validate(order)
