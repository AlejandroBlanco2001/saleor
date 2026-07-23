# Gotchas

Curious/non-obvious things hit while building `order-service`. Check before big changes.

## Environment

- **Bash tool cwd resets to repo root between calls** — does not persist like a real shell session. Any command relying on a prior `cd` (e.g. `uv sync`, `uv run`) must either re-`cd` in the *same* command, or use full paths. Bit us once: `uv sync` ran at repo root instead of `order_service/` and **replaced the root `.venv`** (Python 3.8, all Django deps) with an empty Python 3.12 venv, plus stray `.python-version`/`uv.lock` at root. Always `git status` after any `uv`/`venv` operation to confirm only the intended directory changed.
- Root repo venv: Python **3.8.20**, installed via `pip install -r requirements.txt -r requirements_dev.txt` (Poetry-declared but installed with pip here). Interpreter lives at `C:\Users\Isaac Blanco\AppData\Roaming\uv\python\cpython-3.8.20-windows-x86_64-none\python.exe` — use this exact interpreter if the root `.venv` ever needs rebuilding.
- `order_service/` is a **separate uv project** (own `pyproject.toml`, `.venv`, `uv.lock`, Python 3.12 pinned via `.python-version`). Always run `uv` commands from inside `order_service/`, never from repo root.
- No Docker daemon by default in this environment — must ask user to start Docker Desktop. No `docker-compose.yml` exists yet (that's step 7), so local DB verification uses a bare `postgres:11` container (`saleor-dev-db`, host port **15432** — port 5432 was blocked by a Windows permission issue, don't fight it, just use 15432).
- No `psql` on PATH — use `docker exec saleor-dev-db psql -U saleor -d saleor -c "..."`.

## Django / weasyprint

- `saleor.plugins.invoicing.plugin.InvoicingPlugin` fails to import on this Windows machine — `weasyprint` → `cairocffi` can't find `libcairo-2.dll`. This breaks **every** Django system check (`manage.py` anything), because `check_plugins` eagerly imports all `settings.PLUGINS` entries.
  - Workaround used: temporarily comment out the `InvoicingPlugin` line in `saleor/settings.py`, run the Django command, then revert immediately and confirm `git status` shows the file clean again. Don't leave it commented out.
  - Bypassing Django's system checks entirely (e.g. to run migrations) requires going around `manage.py`/`call_command` — use `django.setup()` + `MigrationExecutor` directly, since `django.setup()` alone doesn't trigger plugin imports (only the checks framework does).
  - Even with `InvoicingPlugin` filtered out of a migration target list, Django's migration **graph dependencies** can still transitively require it (e.g. `plugins.0002_auto_20200417_0335` is a data migration that calls `get_plugins_manager()`). Excluding the `plugins` app from `leaf_nodes()` targets is not enough by itself.

## SQLAlchemy mapping onto Django's tables

- **`Enum` columns**: SQLAlchemy's `Enum` type defaults to persisting the Python enum *member name* (`"UNFULFILLED"`), not `.value` (`"unfulfilled"`). Django's `status` column is a plain varchar storing the value. Must use `sqlalchemy.Enum(OrderStatus, values_callable=lambda e: [m.value for m in e], native_enum=False)` or every status column silently breaks Django-side reads.
- **`metadata` is reserved** on SQLAlchemy `DeclarativeBase` (it's `Base.metadata`, the `MetaData` registry). Map the column as `metadata_: Mapped[...] = mapped_column("metadata", ...)` — attribute name different from column name.
- Every NOT-NULL column on `order_order` needs an explicit value on INSERT from this process — Django's Python-side field defaults (e.g. `default=now`, `default=""`) don't apply to a raw SQLAlchemy INSERT. Cross-checked exact schema with `\d order_order` rather than guessing from `models.py` — matched exactly, but easy to miss one (e.g. `language_code` had no server-side default in `_SERVER_DEFAULTS` initially, caused a NOT NULL violation caught by the API test).

## How to test Django-side changes (use this, not a scratchpad script)

- **Use `saleor.tests.settings` (`--ds=saleor.tests.settings`, already wired into `setup.cfg`'s `addopts`), not raw `saleor.settings`.** It sets `PLUGINS = []`, which sidesteps the weasyprint/cairo crash *entirely* — no need for the temporary-comment-out-and-revert dance below. Write a real test file under the relevant app's `tests/` dir and run it with `pytest path/to/test_file.py -v`; don't write one-off `django.setup()` scripts in the scratchpad.
- Real `pytest-django` fixtures already exist for this: `client` (Django test client), `db` (implicit via other fixtures), `order` / `order_with_lines` (has a real `user`), `webhook` (registers an `ORDER_CREATED`-subscribed `Webhook`). Check `conftest.py` / `saleor/tests/fixtures.py` before writing a new one.
- To assert a webhook actually dispatches, you must **opt the plugin back in per-test** — `saleor.tests.settings` sets `PLUGINS = []` globally, so `WebhookPlugin` isn't wired into the manager by default. Pattern used elsewhere in the repo (`saleor/plugins/webhook/tests/test_webhook.py`): take the `settings` fixture and do `settings.PLUGINS = ["saleor.plugins.webhook.plugin.WebhookPlugin"]` inside the test, then `@mock.patch("saleor.plugins.webhook.plugin.trigger_webhooks_for_event.delay")`.
- Root venv is missing pytest/pytest-django by default after a rebuild (see below) — `requirements_dev.txt` as a whole won't install (`codecov==2.1.10` gone from PyPI, `pywatchman` needs a Visual Studio C compiler this machine doesn't have). Install just what's needed to run Django tests: `pytest==6.1.2 pytest-django==4.1.0 pytest-mock==3.3.1 pytest-xdist==1.34.0 pytest-cov==2.10.1 faker==4.14.0 freezegun==0.3.15 vcrpy==4.1.0 pytest-vcr==1.0.2`. `pytest-xdist` specifically is required even for a single test file, since `setup.cfg`'s `addopts` hardcodes `-n auto`.
- `pytest-django` creates and destroys its **own** ephemeral test database per run (`Creating/Destroying test database for alias 'default'...`) — it does not touch the persistent `saleor-dev-db` container's `saleor` database. No manual cleanup needed after these tests, unlike the manual-script/curl checks in steps 1-3.

## Django `django.test.Client` scripts run outside `manage.py` (last resort only)

Only relevant if you must run something outside pytest — prefer the section above.

- Running a standalone script with `django.setup()` + `django.test.Client()` needs `PYTHONPATH` set to the repo root, or `ModuleNotFoundError: No module named 'saleor'` — the script's own directory is on `sys.path`, not the repo.
- `ALLOWED_HOSTS` defaults to `localhost,127.0.0.1` (no `testserver`) — `django.test.Client` requests get `DisallowedHost` unless `ALLOWED_HOSTS` env includes `testserver`. (`pytest-django` handles this for you automatically — another reason to prefer it.)
- If using raw `saleor.settings` instead of `saleor.tests.settings`, the cairo/weasyprint plugin-import crash isn't just a checks-framework thing — `saleor.order.actions.order_created()` calls `get_plugins_manager()` at **request time**, eagerly importing every `settings.PLUGINS` entry including `InvoicingPlugin`. Needs the temporary-comment-out-and-revert workaround from the section above.
- `order_created_event()` (`saleor/order/events.py`) calls `account_events.customer_placed_order_event(user=...)` which does `user.is_anonymous` — **do not pass a raw `None`** for a guest order's user. The real caller (`checkout/complete_checkout.py::_create_order`) always passes `request.user`, which is Django's `AnonymousUser` for guests, never bare `None`. Any new caller of `order_created()` (e.g. the event-intake view) must do `order.user or AnonymousUser()`, since `Order.user` is a nullable FK and legitimately `None` for guest checkouts.

## pytest-asyncio + async SQLAlchemy

- Default per-test event loop (pytest-asyncio's function-scoped loop) conflicts with a **module-level** `create_async_engine()` — the asyncpg connection pool gets bound to whichever loop created it first, then errors with `InterfaceError: cannot perform operation: another operation is in progress` on later tests running in a new loop. Fix: pin `asyncio_default_fixture_loop_scope = "session"` and `asyncio_default_test_loop_scope = "session"` in `[tool.pytest.ini_options]` so the whole test session shares one loop (mirrors the single-loop reality of a running uvicorn app anyway).
