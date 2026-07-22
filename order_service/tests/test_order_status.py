import pytest

from app.domain.order_status import (
    InvalidTransitionError,
    OrderStatus,
    transition_order_status,
)


class _Order:
    def __init__(self, status: OrderStatus) -> None:
        self.status = status


@pytest.mark.parametrize(
    ("start", "target"),
    [
        (OrderStatus.UNFULFILLED, OrderStatus.PARTIALLY_FULFILLED),
        (OrderStatus.UNFULFILLED, OrderStatus.FULFILLED),
        (OrderStatus.UNFULFILLED, OrderStatus.CANCELED),
        (OrderStatus.PARTIALLY_FULFILLED, OrderStatus.FULFILLED),
        (OrderStatus.PARTIALLY_FULFILLED, OrderStatus.CANCELED),
    ],
)
def test_valid_transition_succeeds(start: OrderStatus, target: OrderStatus) -> None:
    order = _Order(start)
    result = transition_order_status(order, target)
    assert result.status == target


@pytest.mark.parametrize(
    ("start", "target"),
    [
        (OrderStatus.UNFULFILLED, OrderStatus.UNFULFILLED),
        (OrderStatus.PARTIALLY_FULFILLED, OrderStatus.UNFULFILLED),
        (OrderStatus.FULFILLED, OrderStatus.UNFULFILLED),
        (OrderStatus.FULFILLED, OrderStatus.PARTIALLY_FULFILLED),
        (OrderStatus.FULFILLED, OrderStatus.CANCELED),
        (OrderStatus.CANCELED, OrderStatus.UNFULFILLED),
        (OrderStatus.CANCELED, OrderStatus.FULFILLED),
    ],
)
def test_invalid_transition_raises(start: OrderStatus, target: OrderStatus) -> None:
    order = _Order(start)
    with pytest.raises(InvalidTransitionError):
        transition_order_status(order, target)


@pytest.mark.parametrize("status", [OrderStatus.FULFILLED, OrderStatus.CANCELED])
def test_terminal_status_has_no_outgoing_transitions(status: OrderStatus) -> None:
    order = _Order(status)
    for target in OrderStatus:
        if target == status:
            continue
        with pytest.raises(InvalidTransitionError):
            transition_order_status(order, target)
