from __future__ import annotations

from ipaddress import ip_address, ip_network

from fastapi import Request

from src.core.config import AppConfig


def resolve_client_ip(request: Request, config: AppConfig) -> str:
    client_host = request.client.host if request.client else ""
    trusted_proxy = _is_trusted_proxy(client_host, config.trusted_proxy_ips)

    if trusted_proxy:
        x_forwarded_for = request.headers.get("X-Forwarded-For", "")
        forwarded_ip = _first_forwarded_ip(x_forwarded_for)
        if forwarded_ip:
            return forwarded_ip

        x_real_ip = request.headers.get("X-Real-IP", "").strip()
        if x_real_ip:
            return x_real_ip

    return client_host or "unknown"


def _first_forwarded_ip(value: str) -> str | None:
    for raw_part in value.split(","):
        part = raw_part.strip()
        if part:
            return part
    return None


def _is_trusted_proxy(candidate_ip: str, trusted_proxy_ips: list[str]) -> bool:
    if not candidate_ip:
        return False

    try:
        candidate = ip_address(candidate_ip)
    except ValueError:
        return False

    for raw_network in trusted_proxy_ips:
        network = raw_network.strip()
        if not network:
            continue

        try:
            if "/" in network:
                if candidate in ip_network(network, strict=False):
                    return True
            elif candidate == ip_address(network):
                return True
        except ValueError:
            continue

    return False
