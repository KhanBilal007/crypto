from __future__ import annotations

import base64
from http.client import HTTPConnection
from threading import Thread

import pytest

from abtp.dashboard.paper_app import build_default_paper_dashboard_controller
from abtp.dashboard.paper_server import PaperDashboardHTTPServer
from abtp.security.dashboard_http import DashboardHTTPPolicy, require_loopback_bind

PASSWORD = "local-test-password-not-a-real-secret"


@pytest.mark.parametrize("host", ["0.0.0.0", "::", "192.168.1.10", "example.com"])
def test_dashboard_refuses_public_bind(host: str) -> None:
    with pytest.raises(ValueError, match="loopback"):
        require_loopback_bind(host)


@pytest.mark.parametrize("host", ["127.0.0.1", "::1", "localhost"])
def test_dashboard_allows_loopback_bind(host: str) -> None:
    require_loopback_bind(host)


def test_remote_origin_requires_auth_and_trusted_https() -> None:
    with pytest.raises(ValueError, match="authentication"):
        DashboardHTTPPolicy(public_origin="https://bot.example")
    for origin in ("http://bot.example", "https://bot.example/path", "https://user@bot.example"):
        with pytest.raises(ValueError, match="HTTPS origin"):
            DashboardHTTPPolicy(username="operator", password=PASSWORD, public_origin=origin)


@pytest.mark.parametrize(
    "headers,status",
    [
        ({"Host": "evil.example:8765"}, 403),
        ({"Host": "127.0.0.1:8765", "Content-Type": "text/plain"}, 415),
        (
            {
                "Host": "127.0.0.1:8765",
                "Content-Type": "application/json",
                "Origin": "https://evil.example",
            },
            403,
        ),
        (
            {
                "Host": "127.0.0.1:8765",
                "Content-Type": "application/json",
                "Content-Length": "9999999",
            },
            413,
        ),
        (
            {"Host": "127.0.0.1:8765", "Content-Type": "application/json", "Content-Length": "bad"},
            400,
        ),
        (
            {
                "Host": "127.0.0.1:8765",
                "Content-Type": "application/json",
                "Transfer-Encoding": "chunked",
            },
            400,
        ),
        (
            {
                "Host": "127.0.0.1:8765",
                "Content-Type": "application/json",
                "Sec-Fetch-Site": "cross-site",
            },
            403,
        ),
    ],
)
def test_control_boundary_rejects_unsafe_requests(headers: dict[str, str], status: int) -> None:
    rejection = DashboardHTTPPolicy().authorize("POST", headers, port=8765)
    assert rejection is not None and rejection[0] == status


def test_browser_login_authenticates_status_and_controls_end_to_end() -> None:
    controller = build_default_paper_dashboard_controller(market_data_source="demo")
    policy = DashboardHTTPPolicy(
        username="operator", password=PASSWORD, public_origin="https://bot.example"
    )
    server = PaperDashboardHTTPServer(("127.0.0.1", 0), controller, policy=policy)
    worker = Thread(target=server.serve_forever, kwargs={"poll_interval": 0.01})
    worker.start()
    try:
        connection = HTTPConnection("127.0.0.1", server.server_port, timeout=3)
        connection.request("GET", "/api/status")
        response = connection.getresponse()
        assert response.status == 401
        assert response.getheader("WWW-Authenticate") is not None
        response.read()
        connection.close()
        auth = "Basic " + base64.b64encode(f"operator:{PASSWORD}".encode()).decode()
        connection = HTTPConnection("127.0.0.1", server.server_port, timeout=3)
        connection.request("GET", "/api/status", headers={"Authorization": auth})
        response = connection.getresponse()
        assert response.status == 200
        assert response.getheader("X-Frame-Options") == "DENY"
        assert PASSWORD.encode() not in response.read()
        connection.close()
        connection = HTTPConnection("127.0.0.1", server.server_port, timeout=3)
        connection.request(
            "POST",
            "/api/pause-paper-bot",
            body='{"reason":"test"}',
            headers={
                "Authorization": auth,
                "Content-Type": "application/json",
                "Origin": "https://evil.example",
            },
        )
        response = connection.getresponse()
        assert response.status == 403
        response.read()
        connection.close()
        connection = HTTPConnection("127.0.0.1", server.server_port, timeout=3)
        connection.request(
            "POST",
            "/api/pause-paper-bot",
            body='{"reason":"test"}',
            headers={
                "Authorization": auth,
                "Content-Type": "application/json",
                "Origin": "https://bot.example",
            },
        )
        response = connection.getresponse()
        assert response.status == 200
        response.read()
        connection.close()
    finally:
        server.shutdown()
        worker.join(timeout=3)
        server.server_close()
    assert not worker.is_alive()
