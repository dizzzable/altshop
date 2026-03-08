from types import SimpleNamespace

from starlette.requests import Request

from src.api.utils.request_ip import resolve_client_ip


def _build_request(peer_ip: str, headers: dict[str, str] | None = None) -> Request:
    raw_headers = [(key.lower().encode(), value.encode()) for key, value in (headers or {}).items()]
    scope = {
        "type": "http",
        "headers": raw_headers,
        "client": (peer_ip, 12345),
    }
    return Request(scope)


def _build_config(trusted_proxy_ips: list[str]) -> SimpleNamespace:
    return SimpleNamespace(trusted_proxy_ips=trusted_proxy_ips)


def test_resolve_client_ip_uses_x_forwarded_for_from_trusted_proxy() -> None:
    request = _build_request(
        "127.0.0.1",
        headers={
            "X-Forwarded-For": "198.51.100.23, 127.0.0.1",
            "X-Real-IP": "203.0.113.10",
        },
    )

    assert resolve_client_ip(request, _build_config(["127.0.0.1"])) == "198.51.100.23"


def test_resolve_client_ip_falls_back_to_x_real_ip_for_trusted_proxy() -> None:
    request = _build_request(
        "10.0.0.5",
        headers={
            "X-Real-IP": "203.0.113.10",
        },
    )

    assert resolve_client_ip(request, _build_config(["10.0.0.0/24"])) == "203.0.113.10"


def test_resolve_client_ip_ignores_forwarded_headers_for_untrusted_peer() -> None:
    request = _build_request(
        "198.51.100.55",
        headers={
            "X-Forwarded-For": "203.0.113.10",
            "X-Real-IP": "203.0.113.11",
        },
    )

    assert resolve_client_ip(request, _build_config(["127.0.0.1"])) == "198.51.100.55"
