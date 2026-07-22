# Step 6 — Creation seam Strangler Facade (highest risk — do last)

Depends on: Steps 4 and 5 done and verified. This is the riskiest edit — only start once the HTTP client and query facade are solid.
See `plans/00-master-plan.md` for full context.

## Goal

`saleor/checkout/complete_checkout.py::_create_order()` (lines 229-284) stops inserting the `Order` row itself and delegates to order-service, while everything downstream of that INSERT (line bulk-create, stock allocation, gift cards, payment reassignment, metadata, `order_created()` event) keeps running exactly as today.

## Current code (read before editing)

```python
@transaction.atomic
def _create_order(*, checkout, order_data, user):
    from ..order.utils import add_gift_card_to_order
    order = Order.objects.filter(checkout_token=checkout.token).first()
    if order is not None:
        return order
    total_price_left = order_data.pop("total_price_left")
    order_lines = order_data.pop("lines")
    order = Order.objects.create(**order_data, checkout_token=checkout.token)   # <-- replace only this line
    for line in order_lines:
        line.order_id = order.pk
    order_lines = OrderLine.objects.bulk_create(order_lines)
    for line in order_lines:
        variant = line.variant
        if variant and variant.track_inventory:
            allocate_stock(line, checkout.get_country(), line.quantity)
    for gift_card in checkout.gift_cards.select_for_update():
        total_price_left = add_gift_card_to_order(order, gift_card, total_price_left)
    checkout.payments.update(order=order)
    order.metadata = checkout.metadata
    order.private_metadata = checkout.private_metadata
    order.save()   # <-- writes ALL fields on this instance, not just metadata — see risk note below
    transaction.on_commit(lambda: order_created(order=order, user=user))
    transaction.on_commit(lambda: send_order_confirmation.delay(order.pk, checkout.redirect_url, user.pk))
    transaction.on_commit(lambda: send_staff_order_confirmation.delay(order.pk, checkout.redirect_url))
    return order
```

`order_data` at this point is a dict of kwargs built by `_prepare_order_data()` (lines 176-226), containing **live Django object references** for FKs (`billing_address`, `shipping_address`, `shipping_method`, `voucher`, `user` — actual model instances, not ids) plus `total` (a `TaxedMoney`, decomposed into `total_net_amount`/`total_gross_amount` by Django's `TaxedMoneyField` descriptor on assignment), `shipping_price` (same, `TaxedMoney`), `discount` (a `Money`), and plain scalars (`language_code`, `tracking_client_id`, `user_email`, `customer_note`, `weight`, `discount_name`, `translated_discount_name`).

## New code shape

```python
def _order_data_to_payload(order_data: dict, checkout_token: str) -> dict:
    payload = {
        "checkout_token": checkout_token,
        "language_code": order_data.get("language_code", ""),
        "tracking_client_id": order_data.get("tracking_client_id", ""),
        "user_email": order_data.get("user_email", ""),
        "customer_note": order_data.get("customer_note", ""),
        "discount_name": order_data.get("discount_name"),
        "translated_discount_name": order_data.get("translated_discount_name"),
        "shipping_method_name": order_data.get("shipping_method_name"),
    }
    if order_data.get("user"):
        payload["user_id"] = order_data["user"].pk
    if order_data.get("billing_address"):
        payload["billing_address_id"] = order_data["billing_address"].pk
    if order_data.get("shipping_address"):
        payload["shipping_address_id"] = order_data["shipping_address"].pk
    if order_data.get("shipping_method"):
        payload["shipping_method_id"] = order_data["shipping_method"].pk
    if order_data.get("voucher"):
        payload["voucher_id"] = order_data["voucher"].pk
    total = order_data["total"]
    payload["total_net_amount"] = str(total.net.amount)
    payload["total_gross_amount"] = str(total.gross.amount)
    payload["currency"] = total.currency
    if "shipping_price" in order_data:
        sp = order_data["shipping_price"]
        payload["shipping_price_net_amount"] = str(sp.net.amount)
        payload["shipping_price_gross_amount"] = str(sp.gross.amount)
    if "discount" in order_data:
        payload["discount_amount"] = str(order_data["discount"].amount)
    return payload


@transaction.atomic
def _create_order(*, checkout, order_data, user):
    from ..order.utils import add_gift_card_to_order
    order = Order.objects.filter(checkout_token=checkout.token).first()
    if order is not None:
        return order
    total_price_left = order_data.pop("total_price_left")
    order_lines = order_data.pop("lines")

    payload = _order_data_to_payload(order_data, checkout.token)
    try:
        response = order_service_client.create_order(payload)
    except OrderServiceUnavailable as exc:
        raise ValidationError(
            {"checkout": ValidationError("Order service unavailable, please retry.",
                                          code=CheckoutErrorCode.NOT_FOUND)}  # or a new dedicated code, check CheckoutErrorCode enum first
        ) from exc

    # IMPORTANT: build the in-memory Order from the ORIGINAL order_data (still holds live
    # Django object references for FKs), only overriding pk/token/status/totals from the
    # authoritative order-service response. Do NOT reconstruct FKs from raw ids here.
    order = Order(**order_data, checkout_token=checkout.token)
    order.id = response["id"]
    order.pk = response["id"]
    order.token = response["token"]
    order.status = response["status"]
    order.total_net_amount = Decimal(response["total_net_amount"])
    order.total_gross_amount = Decimal(response["total_gross_amount"])
    order._state.adding = False

    for line in order_lines:
        line.order_id = order.pk
    order_lines = OrderLine.objects.bulk_create(order_lines)
    for line in order_lines:
        variant = line.variant
        if variant and variant.track_inventory:
            allocate_stock(line, checkout.get_country(), line.quantity)
    for gift_card in checkout.gift_cards.select_for_update():
        total_price_left = add_gift_card_to_order(order, gift_card, total_price_left)
    checkout.payments.update(order=order)
    order.metadata = checkout.metadata
    order.private_metadata = checkout.private_metadata
    order.save()
    transaction.on_commit(lambda: order_created(order=order, user=user))
    transaction.on_commit(lambda: send_order_confirmation.delay(order.pk, checkout.redirect_url, user.pk))
    transaction.on_commit(lambda: send_staff_order_confirmation.delay(order.pk, checkout.redirect_url))
    return order
```

## Biggest correctness risk — read this before testing

`order.save()` near the end (originally there just to persist `metadata`/`private_metadata`) writes **every field** on the Django instance on `UPDATE`, not just the changed ones (no `update_fields=` passed). Since `order` here is built from `Order(**order_data, ...)` with the *same* kwargs that would have gone into the original `Order.objects.create(...)` call, plus token/status/totals explicitly overridden from order-service's response, the field set should be complete and accurate — but if any field silently differs (e.g. a default order-service applied that Django's local `order_data` dict doesn't have, like `weight` if `order_data` doesn't set it), this `save()` will overwrite order-service's stored value with Django's local default. **Test this specifically**: after `_create_order()` runs, re-fetch the row via a fresh `Order.objects.get(pk=...)` and diff every field against what order-service actually persisted.

Check `CheckoutErrorCode` enum (`saleor/checkout/error_codes.py`) before picking/adding an error code for the service-unavailable case — reuse an existing code if one fits, otherwise add one following the existing pattern.

## Verification

Extend `saleor/checkout/tests/test_checkout_complete.py` (mock `order_service_client.create_order` to return a canned response mirroring what step 1/2's real endpoint would return):
- Full happy path: stock allocation, gift cards, payment reassignment, metadata, and `order_created` event all still fire correctly.
- Re-fetch the created order via `Order.objects.get(pk=...)` after the mutation and diff every field against the mocked service response + `order_data` — no field silently reset (the risk above).
- Simulated failure: mock `create_order` to raise `OrderServiceUnavailable` → assert the checkout-complete mutation returns a controlled error (`errors` populated with the checkout error code), not an unhandled exception/500, and completes quickly (no hang).

## Next step

`plans/steps/07-docker-compose.md`
