from decimal import Decimal

import graphene
from django.utils.dateparse import parse_datetime
from graphql import GraphQLError
from measurement.measures import Weight

from ...order import OrderStatus, models
from ...order import order_service_client
from ...order.events import OrderEvents
from ...order.models import OrderEvent
from ...order.order_service_client import OrderServiceUnavailable
from ...order.utils import sum_order_totals
from ..utils.filters import filter_by_period
from .enums import OrderStatusFilter

ORDER_SEARCH_FIELDS = ("id", "discount_name", "token", "user_email", "user__email")


def filter_orders(qs, info, created, status):
    # DEPRECATED: Will be removed in Saleor 2.11, use the `filter` field instead.
    # filter orders by status
    if status is not None:
        if status == OrderStatusFilter.READY_TO_FULFILL:
            qs = qs.ready_to_fulfill()
        elif status == OrderStatusFilter.READY_TO_CAPTURE:
            qs = qs.ready_to_capture()

    # DEPRECATED: Will be removed in Saleor 2.11, use the `filter` field instead.
    # filter orders by creation date
    if created is not None:
        qs = filter_by_period(qs, created, "created")

    return qs


def resolve_orders(info, created, status, **_kwargs):
    qs = models.Order.objects.confirmed()
    return filter_orders(qs, info, created, status)


def resolve_draft_orders(info, created, **_kwargs):
    qs = models.Order.objects.drafts()
    return filter_orders(qs, info, created, None)


def resolve_orders_total(_info, period):
    qs = models.Order.objects.confirmed().exclude(status=OrderStatus.CANCELED)
    qs = filter_by_period(qs, period, "created")
    return sum_order_totals(qs)


def _hydrate_order(data: dict) -> models.Order:
    """Build a Django `Order` instance from order-service's response without
    querying the DB for it. Every field the `Order` GraphQL type's
    `Meta.only_fields` needs directly (see saleor/graphql/order/types.py)
    must be set here; nested fields (lines, fulfillments, events, addresses)
    are reverse-FK/FK managers that lazily query keyed off `pk`/`*_id`, so
    they keep working unchanged once `pk` is set.
    """
    order = models.Order(
        id=data["id"],
        token=data["token"],
        checkout_token=data["checkout_token"],
        status=data["status"],
        currency=data["currency"],
        created=parse_datetime(data["created"]),
        total_net_amount=Decimal(data["total_net_amount"]),
        total_gross_amount=Decimal(data["total_gross_amount"]),
        shipping_price_net_amount=Decimal(data["shipping_price_net_amount"]),
        shipping_price_gross_amount=Decimal(data["shipping_price_gross_amount"]),
        shipping_method_name=data["shipping_method_name"],
        discount_amount=Decimal(data["discount_amount"]),
        discount_name=data["discount_name"],
        translated_discount_name=data["translated_discount_name"],
        display_gross_prices=data["display_gross_prices"],
        customer_note=data["customer_note"],
        # MeasurementField doesn't coerce a raw float assigned via the model
        # constructor the way it does on a DB-fetched row -- wrap explicitly
        # or `weight { value }` resolves null despite being non-nullable.
        weight=Weight(kg=data["weight"]),
        language_code=data["language_code"],
        tracking_client_id=data["tracking_client_id"],
    )
    order.user_id = data.get("user_id")
    order.billing_address_id = data.get("billing_address_id")
    order.shipping_address_id = data.get("shipping_address_id")
    order.shipping_method_id = data.get("shipping_method_id")
    order.voucher_id = data.get("voucher_id")
    order.pk = data["id"]
    order._state.adding = False
    return order


def resolve_order(info, order_id):
    _type, pk = graphene.Node.from_global_id(order_id)
    if _type != "Order":
        return None
    try:
        data = order_service_client.get_order(pk)
    except OrderServiceUnavailable as exc:
        raise GraphQLError("Order service unavailable") from exc
    return _hydrate_order(data) if data else None


def resolve_homepage_events():
    # Filter only selected events to be displayed on homepage.
    types = [
        OrderEvents.PLACED,
        OrderEvents.PLACED_FROM_DRAFT,
        OrderEvents.ORDER_FULLY_PAID,
    ]
    return OrderEvent.objects.filter(type__in=types)


def resolve_order_by_token(token):
    try:
        data = order_service_client.get_order_by_token(token)
    except OrderServiceUnavailable as exc:
        raise GraphQLError("Order service unavailable") from exc
    return _hydrate_order(data) if data else None
