# Step 8 — Golden-fixture parity tests [DONE]

Depends on: Step 7 done (needs the full composed stack to be stable).
See `plans/00-master-plan.md` for full context.

## Goal

Prove the Strangler Facade preserves the legacy GraphQL contract: same schema, same values, for the queries/flows in scope (order-by-id, order-by-token, order creation via checkout completion), plus controlled degradation on simulated order-service failure. This is the pre-experimento's own validation requirement (`context/entregas/w7/pre-experimento.md`, "Verificación funcional").

## Files to create

- `saleor/graphql/order/tests/fixtures/golden_order_query.json`
- `saleor/graphql/order/tests/fixtures/golden_order_by_token.json`
- `saleor/graphql/order/tests/fixtures/golden_order_created.json`
- `saleor/graphql/order/tests/test_golden_fixture_parity.py`

## How to capture the "golden" (legacy, pre-facade) values

Before/independent of the facade changes (steps 5-6), run the **existing** test queries in `saleor/graphql/order/tests/test_order.py` (e.g. `test_order_query`) against a fixed seed dataset (reuse existing fixtures like `order`, `orders` from `saleor/conftest.py` / `saleor/checkout/tests/conftest.py` for determinism) and save the exact response JSON. Options, in order of preference:
1. Check out the pre-facade commit in a worktree, run the queries, save the output.
2. If that's impractical mid-development, temporarily stash the facade edits (`git stash`), run once, save fixtures, `git stash pop`.

Cover:
- `order(id: ...)` for an existing order — full field set as tested in `test_order_query`.
- `order(id: ...)` for a nonexistent id → `null`.
- `orderByToken(token: ...)` found/missing.
- An order created via the checkout-completion mutation, re-queried immediately after — lines, totals, status all populated.

## `test_golden_fixture_parity.py`

For each golden fixture: run the same GraphQL query against the **facade-enabled** app (real order-service running per step 7's `local` Compose profile, or mocked per steps 5/6 if run outside the composed stack — step 9's cloud order-service is an optional extra run, not required for this gate) and assert:
- **Schema parity**: same set of fields present/absent (no field silently disappeared or appeared).
- **Functional parity**: same values for every field (ids obviously differ per test run — compare by re-running the full flow, not literal id equality, or normalize ids before diffing).
- **Business-rule parity**: anything that was previously rejected (e.g. a lookup for a nonexistent order) is still rejected the same way (`null`, not an error).

## Simulated-failure test (in the same file or `test_order_service_facade.py` from step 5)

- Stop/block `order-service` (real container per step 7, or mock at the client level per steps 4-6).
- Assert: `order(id: ...)` query → controlled GraphQL `errors[]` entry, test completes within the configured timeout (assert wall-clock bound, not just "eventually returns").
- Assert: checkout-completion mutation → controlled `CheckoutError`, same timing bound.
- Assert: **no unhandled exception, no 500, no test timeout/hang** in either case.

## Verification — actually run, results below

Golden fixtures captured via a real throwaway `git worktree add <tmp-dir> c7be1bc8e8` (the last commit before step 5's query facade — confirmed via `git show --stat` on the step 5/6 commits), a one-shot capture test writing normalized JSON directly to `saleor/graphql/order/tests/fixtures/`, then `git worktree remove --force`. `id`/`token`/`created` normalized to placeholders (inherently per-run); everything else compared exactly.

`pytest saleor/graphql/order/tests/test_golden_fixture_parity.py saleor/graphql/order/tests/test_order_service_facade.py -v` → **10/10 passed**. Full regression sweep (`test_order.py` + both `test_checkout_complete.py` files + `test_order_service_events.py`) → **217/217 passed**.

**Real bug caught by this gate, not by any earlier step's tests**: `resolve_order`/`resolve_order_by_token`'s `_hydrate_order()` (step 5) assigned `weight=data["weight"]` — a raw `float` from order-service's JSON response — directly to the Django `Order` model's `weight` `MeasurementField` kwarg. Unlike a DB-fetched row (where the field descriptor coerces the raw column value into a `Weight` object transparently), a value passed straight to the model constructor is **not** coerced — it stayed a bare float, and `weight { value }` in GraphQL resolved to `null` on a non-nullable field, a hard `GraphQLError`. None of steps 5/6/7's own tests exercised the `weight` field, so this shipped invisibly until the golden-fixture query (which mirrors what a real client actually asks for) hit it. Fixed by wrapping explicitly: `weight=Weight(kg=data["weight"])` (`from measurement.measures import Weight`) in `saleor/graphql/order/resolvers.py`. `_create_order`'s in-memory `Order(**order_data, ...)` in `complete_checkout.py` was never at risk — its `weight` comes from `checkout.get_total_weight()`, already a real `Weight` object, not a raw float from JSON.

This is the last gate before the delivery is considered functionally complete (Terraform in step 9 is infrastructure-only and doesn't gate this).

## Next step

`plans/steps/09-terraform-aws.md`
