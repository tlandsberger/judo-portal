"""Echte Client-IP hinter dem Reverse-Proxy.

Kommt eine Anfrage von einem vertrauenswürdigen Proxy (PORTAL_TRUSTED_PROXIES, Standard: private Netze), wird
REMOTE_ADDR durch die Quell-IP aus ``X-Forwarded-For`` ersetzt: von rechts der erste Eintrag, der kein
vertrauenswürdiger Proxy ist. Sind alle Einträge privat (Gerät im LAN), gilt der linke. Ohne Header bleibt die
Verbindungsadresse.

Der Proxy muss den Header vertrauenswürdig setzen. In der Homecloud übernimmt Traefik das ``X-Forwarded-For`` von
Cloudflare nur aus dem Netz von cloudflared und setzt es am LAN-Eingang selbst. Herstellerspezifische Header wie
``CF-Connecting-IP`` wertet das Portal bewusst nicht aus: Traefik entfernt sie nicht, sie wären fälschbar.

So verwenden „Angemeldete Geräte“ (allauth usersessions) und die Sperre gegen Durchprobieren (allauth-Ratelimits)
die echte IP. Anfragen von nicht vertrauenswürdigen Adressen können keine IP vortäuschen.
"""

from __future__ import annotations

import ipaddress
from collections.abc import Callable
from functools import cache

from django.conf import settings
from django.http import HttpRequest, HttpResponse

Network = ipaddress.IPv4Network | ipaddress.IPv6Network


@cache
def trusted_networks() -> tuple[Network, ...]:
    return tuple(ipaddress.ip_network(net.strip(), strict=False) for net in settings.TRUSTED_PROXIES if net.strip())


def _parse(value: str | None) -> ipaddress.IPv4Address | ipaddress.IPv6Address | None:
    if not value:
        return None
    try:
        return ipaddress.ip_address(value.strip())
    except ValueError:
        return None


def _trusted(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    return any(ip in net for net in trusted_networks())


def client_ip(meta: dict[str, str]) -> str | None:
    remote = _parse(meta.get("REMOTE_ADDR"))
    if remote is None or not _trusted(remote):
        return meta.get("REMOTE_ADDR")
    chain = [ip for ip in (_parse(part) for part in meta.get("HTTP_X_FORWARDED_FOR", "").split(",")) if ip]
    for ip in reversed(chain):
        if not _trusted(ip):
            return str(ip)
    return str(chain[0]) if chain else str(remote)


class ClientIPMiddleware:
    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        ip = client_ip(request.META)
        if ip and ip != request.META.get("REMOTE_ADDR"):
            request.META["PORTAL_PROXY_ADDR"] = request.META.get("REMOTE_ADDR", "")
            request.META["REMOTE_ADDR"] = ip
        return self.get_response(request)
