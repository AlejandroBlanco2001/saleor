# Saleor legacy-views — MISO Modernization Project

## Project context
This is Saleor v2.11, a legacy Django e-commerce monolith (Python 3.8).
We are analyzing it for a software modernization course (MISO, Universidad de los Andes).
The goal is to understand its as-is architecture and identify modernization candidates.

## Key apps (saleor/)
- product/     → catalog, variants, attributes
- order/       → orders, fulfillment, states
- checkout/    → cart and purchase flow
- account/     → users, addresses, sessions
- payment/     → payment gateway integrations
- discount/    → vouchers and sales
- shipping/    → zones and methods
- warehouse/   → stock and inventory
- giftcard/    → gift card management
- wishlist/    → customer wishlists
- plugins/     → payment/integration plugin system
- webhook/     → outbound event webhooks
- graphql/     → GraphQL schema and resolvers

## Stack
- Python 3.8, Django 3.x (^3.0.7), PostgreSQL
- Celery + Redis for async tasks
- Django templates (DjangoTemplates backend, not Jinja2)
- GraphQL API via graphene-django ^2.11
- django-extensions installed (graph_models available)
- pylint installed (pyreverse available)
- Poetry

## Do NOT modify
- migrations/ folders
- settings.py credentials
- docker-compose.yml

## Commands available
- poetry run python manage.py graph_models [apps] -o output.png
- poetry run pyreverse -o png -p [name] saleor/[app]/
- poetry run pylint saleor/[app]/ --output-format=text
- poetry run python manage.py shell