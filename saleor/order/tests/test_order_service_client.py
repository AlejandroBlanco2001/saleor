"""Tests run against a real (stdlib-only) local HTTP server rather than a
mocked `requests.Session`, so the actual `urllib3.Retry` machinery -
connect/read timeouts, status_forcelist retries, bounded total - is what's
under test, not a hand-waved mock of it.
"""

import json
import socket
import threading
import time
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest
from django.test import override_settings

from ..order_service_client import (
    OrderServiceUnavailable,
    create_order,
    get_order,
    get_order_by_token,
)


class _Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def _handle(self):
        self.server.request_count += 1
        status, body, delay = self.server.script(self.server.request_count)
        if delay:
            time.sleep(delay)
        payload = json.dumps(body).encode() if body is not None else b""
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(payload)

    do_GET = _handle
    do_POST = _handle


@contextmanager
def _server(script):
    """`script(attempt_number) -> (status, body_or_None, delay_seconds)`."""
    httpd = HTTPServer(("127.0.0.1", 0), _Handler)
    httpd.request_count = 0
    httpd.script = script
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield httpd
    finally:
        httpd.shutdown()
        thread.join()


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def test_create_order_happy_path():
    with _server(lambda n: (201, {"id": 1, "token": "abc"}, None)) as httpd:
        with override_settings(ORDER_SERVICE_URL=f"http://127.0.0.1:{httpd.server_port}"):
            result = create_order({"currency": "USD"})

    assert result == {"id": 1, "token": "abc"}
    assert httpd.request_count == 1


def test_get_order_not_found_returns_none():
    with _server(lambda n: (404, None, None)) as httpd:
        with override_settings(ORDER_SERVICE_URL=f"http://127.0.0.1:{httpd.server_port}"):
            result = get_order(999)

    assert result is None


def test_get_order_by_token_not_found_returns_none():
    with _server(lambda n: (404, None, None)) as httpd:
        with override_settings(ORDER_SERVICE_URL=f"http://127.0.0.1:{httpd.server_port}"):
            result = get_order_by_token("does-not-exist")

    assert result is None


def test_get_order_found_returns_dict():
    with _server(lambda n: (200, {"id": 5}, None)) as httpd:
        with override_settings(ORDER_SERVICE_URL=f"http://127.0.0.1:{httpd.server_port}"):
            result = get_order(5)

    assert result == {"id": 5}


def test_status_forcelist_5xx_retries_once_then_raises():
    with _server(lambda n: (503, None, None)) as httpd:
        with override_settings(ORDER_SERVICE_URL=f"http://127.0.0.1:{httpd.server_port}"):
            with pytest.raises(OrderServiceUnavailable):
                create_order({"currency": "USD"})

    assert httpd.request_count == 2


def test_non_forcelist_5xx_does_not_retry():
    with _server(lambda n: (500, None, None)) as httpd:
        with override_settings(ORDER_SERVICE_URL=f"http://127.0.0.1:{httpd.server_port}"):
            with pytest.raises(OrderServiceUnavailable):
                create_order({"currency": "USD"})

    assert httpd.request_count == 1


def test_read_timeout_retries_once_then_raises():
    with _server(lambda n: (200, {"id": 1}, 0.5)) as httpd:
        with override_settings(
            ORDER_SERVICE_URL=f"http://127.0.0.1:{httpd.server_port}",
            ORDER_SERVICE_TIMEOUT_READ=0.1,
        ):
            with pytest.raises(OrderServiceUnavailable):
                create_order({"currency": "USD"})
        # server keeps handling in the background even after the client
        # gives up; give it a moment to register the second attempt.
        time.sleep(0.7)

    assert httpd.request_count == 2


def test_connection_refused_raises_quickly():
    dead_port = _free_port()

    with override_settings(
        ORDER_SERVICE_URL=f"http://127.0.0.1:{dead_port}",
        ORDER_SERVICE_TIMEOUT_CONNECT=0.2,
    ):
        started = time.monotonic()
        with pytest.raises(OrderServiceUnavailable):
            create_order({"currency": "USD"})
        elapsed = time.monotonic() - started

    assert elapsed < 3.0
