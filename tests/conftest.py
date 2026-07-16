from __future__ import annotations

import socket
from collections.abc import Iterator
from typing import Any

import pytest

from packages.evals.phase3_verification.network_guard import (
    ensure_network_address_allowed,
    guard_getaddrinfo_host,
)


@pytest.fixture(autouse=True)
def block_external_network(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Fail tests immediately if they attempt non-loopback network access."""
    original_connect = socket.socket.connect
    original_connect_ex = socket.socket.connect_ex
    original_getaddrinfo = socket.getaddrinfo
    original_sendto = socket.socket.sendto

    def guarded_connect(instance: socket.socket, address: object) -> Any:
        ensure_network_address_allowed(address)
        return original_connect(instance, address)

    def guarded_connect_ex(instance: socket.socket, address: object) -> int:
        ensure_network_address_allowed(address)
        return original_connect_ex(instance, address)

    def guarded_getaddrinfo(host: Any, *args: Any, **kwargs: Any) -> Any:
        guard_getaddrinfo_host(host)
        return original_getaddrinfo(host, *args, **kwargs)

    def guarded_sendto(instance: socket.socket, data: bytes, *args: Any) -> int:
        if not args:
            raise TypeError("sendto requires an address")
        ensure_network_address_allowed(args[-1])
        return original_sendto(instance, data, *args)

    monkeypatch.setattr(socket.socket, "connect", guarded_connect)
    monkeypatch.setattr(socket.socket, "connect_ex", guarded_connect_ex)
    monkeypatch.setattr(socket, "getaddrinfo", guarded_getaddrinfo)
    monkeypatch.setattr(socket.socket, "sendto", guarded_sendto)
    yield
