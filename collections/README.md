# collections/

Postman collection to smoke-test the order-service Strangler Fig migration
from outside — same requests run against both checkouts of the code, only the
environment changes.

- `Saleor-Order-Service-Migration.postman_collection.json` — auth, catalog
  lookup, full checkout→order flow, order query facade (step 5) checks, and
  direct order-service REST checks (step 6/9).
- `Monolith-Pre-Modernization.postman_environment.json` — point at a checkout
  before commit `3fdb8f9c81` (Django ORM order resolvers, no facade).
- `Monolith-Post-Modernization.postman_environment.json` — point at current
  `main` with the `local` or `monolith` docker-compose profile up.

## Run it

Import all three files into Postman (or `postman collection run` /
`newman run` from the CLI), pick the matching environment, run the whole
collection top to bottom — folders 01-03 create a real order and stash its
id/token in collection variables that 04-05 read, so order matters.

Folder `05 - order-service direct` auto-skips (via a folder-level
pre-request script checking `order_service_enabled`) when run against the
pre-modernization environment, so nothing needs editing between runs — same
collection, two environments, two codebases.

```
newman run Saleor-Order-Service-Migration.postman_collection.json \
  -e Monolith-Post-Modernization.postman_environment.json
```

Requires the target stack up first — `docker compose --profile local up`
(step 7) for a full local run, or `--profile monolith` pointed at
`.env.cloud` (step 9) for the cloud-backed order-service.
