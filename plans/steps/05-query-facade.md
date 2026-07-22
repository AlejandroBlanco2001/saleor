# Step 5 — Query seam Strangler Facade

Depends on: Step 4 (`plans/steps/04-django-http-client.md`) done and verified. Do this before step 6 (lower risk, read-only).
See `plans/00-master-plan.md` for full context.

## Goal

Make `resolve_order` / `resolve_order_by_token` fetch the **root** Order row from order-service instead of the Django ORM, while every nested GraphQL field (`lines`, `fulfillments`, `events`, `billingAddress`, etc.) keeps working completely unchanged.

## Why this works

`saleor/graphql/order/types.py`'s `Order` type (line 315) has field resolvers like `resolve_lines` (`root.lines.all()`), `resolve_fulfillments` (`root.fulfillments...`), `resolve_events` (`root.events.all()`), `resolve_billing_address` (`root.billing_address`) — all reverse-FK/FK managers that lazily hit the DB keyed off `root.pk` / `root.billing_address_id`, regardless of whether `root` came from a real `.objects.get()` or was constructed in memory. So: build a Django `Order` instance without querying the DB for it, set its `pk` and FK-id fields from order-service's response, mark it as "already persisted" (`_state.adding = False` so nothing downstream tries to re-INSERT it), and hand it to the GraphQL type machinery exactly as if it had been `.objects.get()`'d.

## Files to modify

- `saleor/graphql/order/resolvers.py` — `resolve_order`, `resolve_order_by_token`

## Current code (read before editing)

```python
def resolve_order(info, order_id):
    return graphene.Node.get_node_from_global_id(info, order_id, Order)

def resolve_order_by_token(token):
    return (
        models.Order.objects.exclude(status=OrderStatus.DRAFT)
        .filter(token=token)
        .first()
    )
```

`graphene.Node.get_node_from_global_id` internally decodes the global id **and** calls the ORM (`Order.get_node` default implementation does `cls._meta.model._default_manager.get(pk=id)`). This means the facade can't just edit inside `resolve_order`'s body while still calling `get_node_from_global_id` — it must stop calling it entirely and decode the id manually.

## New code shape

```python
def _hydrate_order(data: dict) -> models.Order:
    order = models.Order(
        id=data["id"],
        token=data["token"],
        checkout_token=data["checkout_token"],
        status=data["status"],
        currency=data["currency"],
        total_net_amount=Decimal(data["total_net_amount"]),
        total_gross_amount=Decimal(data["total_gross_amount"]),
        # ... other scalar fields the GraphQL type's `only_fields` list needs directly, see saleor/graphql/order/types.py Meta.only_fields
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

def resolve_order_by_token(token):
    try:
        data = order_service_client.get_order_by_token(token)
    except OrderServiceUnavailable as exc:
        raise GraphQLError("Order service unavailable") from exc
    return _hydrate_order(data) if data else None
```

Check `saleor/graphql/order/types.py`'s `Meta.only_fields` list (already read: `billing_address`, `created`, `customer_note`, `discount`, `discount_name`, `display_gross_prices`, `gift_cards`, `id`, `language_code`, `shipping_address`, `shipping_method`, `shipping_method_name`, `shipping_price`, `status`, `token`, `tracking_client_id`, `translated_discount_name`, `user`, `voucher`, `weight`) — every scalar in that list that isn't an FK needs to be set on the hydrated instance too (`created`, `customer_note`, `discount_amount`, `discount_name`, `display_gross_prices`, `language_code`, `shipping_method_name`, `shipping_price_net_amount`/`shipping_price_gross_amount`, `tracking_client_id`, `translated_discount_name`, `weight`), pulled from order-service's response (extend `OrderResponse` in step 2 if any of these aren't already in it).

`GraphQLError` import: from the `graphql` package (already a transitive dependency via `graphene`/`graphene-django`).

## Verification

New file `saleor/graphql/order/tests/test_order_service_facade.py`, mocking `order_service_client`:
- `order(id: ...)` query, found → returns full GraphQL `Order` object with correct scalar fields; assert nested fields (`lines`, `events`) still resolve (may be empty lists if no rows, that's fine — assert no exception).
- `order(id: ...)` missing → returns `null`, no exception.
- `orderByToken(token: ...)` found/missing, same pattern.
- Simulated failure: mock `order_service_client.get_order` to raise `OrderServiceUnavailable` → assert the GraphQL response has a populated `errors` array and the test completes quickly (no hang).

## Next step

`plans/steps/06-creation-facade.md`
