"""Django -> order-service HTTP client: short timeout + one bounded retry.

Used by the Strangler Facade seams (steps 5/6) so a hung or down
order-service surfaces as a controlled error quickly instead of a hang.
"""

from typing import Optional

import requests
from django.conf import settings
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


class OrderServiceUnavailable(Exception):
    pass


_retry = Retry(
    total=1,
    connect=1,
    read=1,
    status_forcelist=[502, 503, 504],
    backoff_factor=0.1,
    # urllib3's default only retries idempotent methods (GET/HEAD/PUT/...);
    # POST /orders/ needs retries too, so explicitly allow it.
    method_whitelist=frozenset(["GET", "POST"]),
)
_session = requests.Session()
_session.mount("http://", HTTPAdapter(max_retries=_retry))
_session.mount("https://", HTTPAdapter(max_retries=_retry))


def _timeout() -> tuple:
    return (settings.ORDER_SERVICE_TIMEOUT_CONNECT, settings.ORDER_SERVICE_TIMEOUT_READ)


def create_order(payload: dict) -> dict:
    try:
        response = _session.post(
            f"{settings.ORDER_SERVICE_URL}/orders/", json=payload, timeout=_timeout()
        )
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as exc:
        raise OrderServiceUnavailable(str(exc)) from exc


def get_order(order_id: int) -> Optional[dict]:
    return _get(f"{settings.ORDER_SERVICE_URL}/orders/{order_id}")


def get_order_by_token(token: str) -> Optional[dict]:
    return _get(f"{settings.ORDER_SERVICE_URL}/orders/by-token/{token}")


def _get(url: str) -> Optional[dict]:
    try:
        response = _session.get(url, timeout=_timeout())
        if response.status_code == 404:
            return None
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as exc:
        raise OrderServiceUnavailable(str(exc)) from exc
