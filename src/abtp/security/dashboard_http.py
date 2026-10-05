"""HTTP boundary policy for a loopback dashboard behind a trusted TLS proxy."""

from __future__ import annotations

import base64
import binascii
import hmac
import ipaddress
from collections.abc import Mapping
from dataclasses import dataclass, field
from urllib.parse import urlsplit


def require_loopback_bind(host: str) -> None:
    if host == "localhost":
        return
    try:
        if ipaddress.ip_address(host).is_loopback:
            return
    except ValueError:
        pass
    raise ValueError("dashboard must bind to loopback; use an authenticated HTTPS reverse proxy")


@dataclass(frozen=True, slots=True)
class DashboardHTTPPolicy:
    username: str = ""
    password: str = field(default="", repr=False)
    public_origin: str = ""
    max_body_bytes: int = 65536

    def __post_init__(self) -> None:
        if bool(self.username) != bool(self.password):
            raise ValueError("both dashboard username and password are required")
        if self.password and len(self.password) < 20:
            raise ValueError("dashboard password must contain at least 20 characters")
        if ":" in self.username or any(ord(char) < 32 for char in self.username + self.password):
            raise ValueError("invalid dashboard credentials")
        if self.public_origin:
            parsed = urlsplit(self.public_origin)
            if (
                parsed.scheme != "https"
                or not parsed.hostname
                or parsed.username
                or parsed.password
                or parsed.path
                or parsed.query
                or parsed.fragment
            ):
                raise ValueError("public dashboard origin must be an HTTPS origin without a path")
            if not self.username:
                raise ValueError("public dashboard origin requires authentication")

    @classmethod
    def from_environment(cls, environment: Mapping[str, str]) -> DashboardHTTPPolicy:
        return cls(
            username=environment.get("ABTP_DASHBOARD_USERNAME", ""),
            password=environment.get("ABTP_DASHBOARD_PASSWORD", ""),
            public_origin=environment.get("ABTP_DASHBOARD_PUBLIC_ORIGIN", ""),
        )

    def authorize(
        self, method: str, headers: Mapping[str, str], *, port: int
    ) -> tuple[int, str] | None:
        expected_hosts = {f"127.0.0.1:{port}", f"localhost:{port}", f"[::1]:{port}"}
        origins = {f"http://{host}" for host in expected_hosts}
        if self.public_origin:
            expected_hosts.add(urlsplit(self.public_origin).netloc)
            origins.add(self.public_origin)
        if headers.get("Host", "").lower() not in {host.lower() for host in expected_hosts}:
            return 403, "untrusted dashboard host"
        if self.username:
            try:
                kind, encoded = headers.get("Authorization", "").split(" ", 1)
                actual = base64.b64decode(encoded, validate=True)
                expected = f"{self.username}:{self.password}".encode()
                valid = kind.lower() == "basic" and hmac.compare_digest(actual, expected)
            except (ValueError, binascii.Error):
                valid = False
            if not valid:
                return 401, "dashboard authentication required"
        if method == "POST":
            origin = headers.get("Origin")
            if origin is not None and origin not in origins:
                return 403, "cross-origin dashboard control is not permitted"
            if headers.get("Sec-Fetch-Site") == "cross-site":
                return 403, "cross-site dashboard control is not permitted"
            if (
                headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
                != "application/json"
            ):
                return 415, "dashboard controls require application/json"
            if headers.get("Transfer-Encoding") is not None:
                return 400, "transfer encoding is not supported"
            try:
                length = int(headers.get("Content-Length", "0"))
            except ValueError:
                return 400, "invalid content length"
            if length < 0 or length > self.max_body_bytes:
                return 413, "dashboard request body is too large"
        return None
