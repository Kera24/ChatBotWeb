from __future__ import annotations

import ipaddress
from dataclasses import dataclass


@dataclass(frozen=True)
class ClientIpResult:
    identity: str
    source: str
    trusted_proxy_used: bool = False


def canonical_ip(value: str) -> str:
    return ipaddress.ip_address(value.strip()).compressed.lower()


def parse_trusted_proxy_networks(raw_networks: str | tuple[str, ...] | list[str]) -> tuple[ipaddress._BaseNetwork, ...]:
    if isinstance(raw_networks, str):
        parts = [part.strip() for part in raw_networks.split(",") if part.strip()]
    else:
        parts = [str(part).strip() for part in raw_networks if str(part).strip()]
    return tuple(ipaddress.ip_network(part, strict=False) for part in parts)


def extract_client_ip(
    *,
    peer_ip: str,
    headers: dict[str, str] | None = None,
    trusted_proxy_networks: tuple[ipaddress._BaseNetwork, ...] = (),
    trust_x_real_ip: bool = True,
) -> ClientIpResult:
    peer = ipaddress.ip_address(peer_ip.strip())
    headers = {str(key).lower(): str(value) for key, value in (headers or {}).items()}
    if not _is_trusted(peer, trusted_proxy_networks):
        return ClientIpResult(identity=peer.compressed.lower(), source="peer", trusted_proxy_used=False)

    xff = headers.get("x-forwarded-for")
    if xff:
        chain = _parse_forwarded_for(xff)
        if chain:
            for candidate in reversed(chain):
                if not _is_trusted(candidate, trusted_proxy_networks):
                    return ClientIpResult(identity=candidate.compressed.lower(), source="x-forwarded-for", trusted_proxy_used=True)
            return ClientIpResult(identity=chain[0].compressed.lower(), source="x-forwarded-for", trusted_proxy_used=True)
    x_real_ip = headers.get("x-real-ip")
    if trust_x_real_ip and x_real_ip:
        return ClientIpResult(identity=canonical_ip(x_real_ip), source="x-real-ip", trusted_proxy_used=True)
    return ClientIpResult(identity=peer.compressed.lower(), source="peer", trusted_proxy_used=True)


def _parse_forwarded_for(value: str) -> list[ipaddress._BaseAddress]:
    addresses: list[ipaddress._BaseAddress] = []
    for part in value.split(","):
        item = part.strip()
        if not item:
            continue
        addresses.append(ipaddress.ip_address(item))
    return addresses


def _is_trusted(ip: ipaddress._BaseAddress, networks: tuple[ipaddress._BaseNetwork, ...]) -> bool:
    return any(ip in network for network in networks)
