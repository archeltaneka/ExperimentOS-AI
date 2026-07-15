from __future__ import annotations

import ipaddress
from typing import Any

_LOCAL_HOSTNAMES = {"localhost", "localhost.localdomain"}


def ensure_network_address_allowed(address: object) -> None:
    """Reject outbound network addresses while permitting loopback and Unix sockets."""
    if isinstance(address, (str, bytes)):
        return
    if not isinstance(address, tuple) or not address:
        raise RuntimeError(f"external network access is disabled during tests: {address!r}")

    host = address[0]
    if not isinstance(host, str) or not _is_loopback_host(host):
        raise RuntimeError(f"external network access is disabled during tests: {address!r}")


def guard_getaddrinfo_host(host: Any) -> None:
    if host is None:
        return
    if isinstance(host, bytes):
        host = host.decode(errors="replace")
    ensure_network_address_allowed((str(host), 0))


def _is_loopback_host(host: str) -> bool:
    normalized = host.rstrip(".").lower()
    if normalized in _LOCAL_HOSTNAMES:
        return True
    try:
        return ipaddress.ip_address(normalized.split("%", maxsplit=1)[0]).is_loopback
    except ValueError:
        return False
