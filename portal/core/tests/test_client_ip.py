import pytest
from django.test import RequestFactory

from portal.core.middleware import ClientIPMiddleware, client_ip

TRAEFIK = "172.18.0.11"


@pytest.mark.parametrize(
    ("meta", "expected"),
    [
        # Von außen: Cloudflare trägt die Besucher-IP ein, Traefik hängt cloudflared an
        ({"REMOTE_ADDR": TRAEFIK, "HTTP_X_FORWARDED_FOR": "203.0.113.7, 10.250.0.3"}, "203.0.113.7"),
        # Über Cloudflare vorgetäuschte Einträge stehen links und zählen nicht
        ({"REMOTE_ADDR": TRAEFIK, "HTTP_X_FORWARDED_FOR": "6.6.6.6, 203.0.113.7, 10.250.0.3"}, "203.0.113.7"),
        # Im LAN: Traefik setzt den Header selbst auf die Geräte-IP
        ({"REMOTE_ADDR": TRAEFIK, "HTTP_X_FORWARDED_FOR": "192.168.11.50"}, "192.168.11.50"),
        # CF-Connecting-IP wird nicht ausgewertet (Traefik entfernt ihn nicht, aus dem LAN fälschbar)
        (
            {"REMOTE_ADDR": TRAEFIK, "HTTP_CF_CONNECTING_IP": "1.2.3.4", "HTTP_X_FORWARDED_FOR": "192.168.11.50"},
            "192.168.11.50",
        ),
        # Direkt von außen (kein vertrauenswürdiger Proxy): Header werden ignoriert
        ({"REMOTE_ADDR": "198.51.100.20", "HTTP_X_FORWARDED_FOR": "5.6.7.8"}, "198.51.100.20"),
        # Kaputte oder fehlende Header: Verbindungsadresse bleibt
        ({"REMOTE_ADDR": TRAEFIK, "HTTP_X_FORWARDED_FOR": "auch-nicht"}, TRAEFIK),
        ({"REMOTE_ADDR": TRAEFIK}, TRAEFIK),
        # IPv6
        ({"REMOTE_ADDR": TRAEFIK, "HTTP_X_FORWARDED_FOR": "2001:db8::1, 10.250.0.3"}, "2001:db8::1"),
    ],
)
def test_client_ip(meta: dict[str, str], expected: str) -> None:
    assert client_ip(meta) == expected


def test_middleware_rewrites_remote_addr() -> None:
    request = RequestFactory().get("/", REMOTE_ADDR=TRAEFIK, HTTP_X_FORWARDED_FOR="203.0.113.7, 10.250.0.3")
    seen = {}

    def view(req):
        seen["ip"] = req.META["REMOTE_ADDR"]
        seen["proxy"] = req.META["PORTAL_PROXY_ADDR"]
        return None

    ClientIPMiddleware(view)(request)
    assert seen == {"ip": "203.0.113.7", "proxy": TRAEFIK}


@pytest.mark.django_db
def test_active_sessions_show_real_ip(client) -> None:
    from allauth.usersessions.models import UserSession

    from portal.accounts.models import User

    User.objects.create_user("mia@example.org", password="Sicher-12345!")
    client.post(
        "/anmeldung/login/",
        {"login": "mia@example.org", "password": "Sicher-12345!"},
        REMOTE_ADDR=TRAEFIK,
        HTTP_X_FORWARDED_FOR="203.0.113.7, 10.250.0.3",
    )
    assert UserSession.objects.get().ip == "203.0.113.7"
