# Instructions — Terraform + Experiment

## Prerequisites
- AWS Academy Learner Lab session started, credentials exported:
  ```
  export AWS_ACCESS_KEY_ID=...
  export AWS_SECRET_ACCESS_KEY=...
  export AWS_SESSION_TOKEN=...
  ```
- `infra/terraform/terraform.tfvars` filled in from `terraform.tfvars.example` (gitignored — never commit real values). Needs `my_ip` (`curl -s https://checkip.amazonaws.com`), `db_username`, `db_password`, `order_service_shared_secret`.
- Docker Desktop running (for the local monolith).

## 1. Provision AWS (RDS + SQS + order-service EC2)
```
python scripts/cloud_dev.py apply --yes
```
Real, billed AWS resources. Without `--yes` it only shows a plan.

## 2. Point the local monolith at it
```
python scripts/cloud_dev.py wire
```
Writes `.env.cloud` from `terraform output` + your current AWS creds.

## 3. Start the monolith locally
```
python scripts/cloud_dev.py start
```
Runs `web` + `celeryworker` locally (`docker compose --profile monolith`), pointed at the cloud RDS/SQS/order-service.

Steps 1-3 in one shot: `python scripts/cloud_dev.py all --yes`.

## 4. Seed data (first run only)
```
docker compose exec web python manage.py populatedb --createsuperuser
```
Creates `admin@example.com` / `admin`, products, shipping zones, warehouse stock.

## 5. Run the experiment (Postman)
```
newman run collections/Saleor-Order-Service-Migration.postman_collection.json \
  -e collections/Monolith-Post-Modernization.postman_environment.json
```
Or import both files into Postman and run the collection there. Checks the full checkout→order flow, the query/creation facade (ORD-01/ORD-02), and status transitions (ORD-04) against the live order-service.

For the "before" baseline, check out the pre-facade commit (`c7be1bc8e8`) and run the same collection with `Monolith-Pre-Modernization.postman_environment.json`.

## 6. Tear down
```
python scripts/cloud_dev.py stop        # stop local monolith
python scripts/cloud_dev.py destroy --yes   # destroy AWS resources
```
Always destroy before ending the lab session — Learner Lab doesn't reliably reclaim resources on its own.

## Purely local run (no AWS)
```
docker compose --profile local up -d --build
docker compose exec web python manage.py populatedb --createsuperuser
newman run collections/Saleor-Order-Service-Migration.postman_collection.json \
  -e collections/Monolith-Post-Modernization.postman_environment.json
```
