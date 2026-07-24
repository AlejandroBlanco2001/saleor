# Failure-simulation transcript (Phase 4, real EC2 order-service stop)

Real container stop on the order-service EC2 instance (`44.193.222.26`), not a mock:

```
$ ssh -i infra/terraform/order_service_key.pem ubuntu@44.193.222.26 \
  'cd /opt/saleor && sudo docker compose stop order-service'
Container saleor-order-service-1  Stopping
Container saleor-order-service-1  Stopped
```

Then, against the still-running local monolith (`web`+`celeryworker`, `--profile monolith`):

## orderByToken query (controlled, 1089ms)
```json
{"errors": [{"message": "Order service unavailable", "locations": [{"line": 1, "column": 9}], "path": ["orderByToken"], "extensions": {"exception": {"code": "GraphQLError"}}}], "data": {"orderByToken": null}}
```

## order(id) query, authenticated (controlled, 1155ms)
```json
{"errors": [{"message": "Order service unavailable", "locations": [{"line": 1, "column": 9}], "path": ["order"], "extensions": {"exception": {"code": "GraphQLError"}}}], "data": {"order": null}}
```

## Full checkout completion attempt (controlled, 5099ms)
```json
{
  "data": {
    "checkoutComplete": {
      "order": null,
      "checkoutErrors": [
        {"field": "checkout", "message": "Order service unavailable, please retry."}
      ]
    }
  }
}
```

## Recovery
```
$ ssh -i infra/terraform/order_service_key.pem ubuntu@44.193.222.26 \
  'cd /opt/saleor && sudo docker compose start order-service'
Container saleor-order-service-1  Starting
Container saleor-order-service-1  Started

$ curl http://44.193.222.26:8001/health
{"status":"ok"}

$ curl -H "Authorization: JWT <token>" http://localhost:8000/graphql/ \
  -d '{"query":"query { order(id: \"T3JkZXI6MjE=\") { id status } }"}'
{"data": {"order": {"id": "T3JkZXI6MjE=", "status": "FULFILLED"}}}
```

**Result: 3/3 attempts controlled (100%)** — structured error, bounded wall-clock time, no 500/hang/leaked stack trace. Full recovery confirmed with real data (order 21's `FULFILLED` status matches the ORD-04 transition applied earlier in the battery run), not just a green health check.
