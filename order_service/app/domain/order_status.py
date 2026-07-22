"""State pattern for order status transitions. Pure Python, zero I/O."""

import enum
from typing import Any


class OrderStatus(str, enum.Enum):
    DRAFT = "draft"
    UNFULFILLED = "unfulfilled"
    PARTIALLY_FULFILLED = "partially_fulfilled"
    FULFILLED = "fulfilled"
    CANCELED = "canceled"


_VALID_TRANSITIONS: dict[OrderStatus, set[OrderStatus]] = {
    OrderStatus.UNFULFILLED: {
        OrderStatus.PARTIALLY_FULFILLED,
        OrderStatus.FULFILLED,
        OrderStatus.CANCELED,
    },
    OrderStatus.PARTIALLY_FULFILLED: {OrderStatus.FULFILLED, OrderStatus.CANCELED},
    OrderStatus.FULFILLED: set(),
    OrderStatus.CANCELED: set(),
}


class InvalidTransitionError(Exception):
    def __init__(self, current: OrderStatus, target: OrderStatus) -> None:
        self.current = current
        self.target = target
        super().__init__(f"Cannot transition order from {current} to {target}")


def transition_order_status(order: Any, new_status: OrderStatus) -> Any:
    if new_status not in _VALID_TRANSITIONS[order.status]:
        raise InvalidTransitionError(order.status, new_status)
    order.status = new_status
    return order
