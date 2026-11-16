import sqlite3
from datetime import date, timedelta

import pytest
from django.urls import reverse

from portal.accounts.models import Role, User
from portal.core import backup

pytestmark = pytest.mark.django_db


def test_healthz(client) -> None:
    response = client.get("/healthz")
    assert response.status_code == 200 and response.content == b"ok"


def test_healthz_via_localhost_even_with_public_allowed_hosts(client, settings) -> None:
    # Der Docker-Healthcheck im Image ruft 127.0.0.1 auf, auch wenn nur die öffentliche Domain konfiguriert ist.
    assert "127.0.0.1" in settings.ALLOWED_HOSTS
    assert client.get("/healthz", HTTP_HOST="127.0.0.1:8000").status_code == 200


def test_security_headers(client) -> None:
    response = client.get(reverse("account_login"))
    csp = response["Content-Security-Policy"]
    assert "default-src 'self'" in csp and "frame-ancestors 'none'" in csp
    assert response["X-Frame-Options"] == "DENY"
    assert response["X-Content-Type-Options"] == "nosniff"


def test_home_requires_login(client) -> None:
    response = client.get(reverse("home"))
    assert response.status_code == 302


def test_home_shows_greeting_and_role_based_tiles(client) -> None:
    user = User.objects.create_user("mia@example.org", first_name="Mia")
    client.force_login(user)
    page = client.get(reverse("home")).content.decode()
    assert "Hallo Mia" in page
    assert reverse("user_list") not in page
    user.set_roles([Role.DEPARTMENT_HEAD])
    assert reverse("user_list") in client.get(reverse("home")).content.decode()


def test_components_page_only_for_admins(client) -> None:
    user = User.objects.create_user("mia@example.org")
    client.force_login(user)
    assert client.get(reverse("components")).status_code == 403
    user.set_roles([Role.ADMIN])
    assert client.get(reverse("components")).status_code == 200


def test_favicon_follows_browser_color_scheme(client) -> None:
    page = client.get(reverse("account_login")).content.decode()
    assert 'favicon-hell.png" type="image/png" sizes="64x64" media="(prefers-color-scheme: light)"' in page
    assert 'favicon-dunkel.png" type="image/png" sizes="64x64" media="(prefers-color-scheme: dark)"' in page


def test_pwa_files(client) -> None:
    manifest = client.get("/manifest.webmanifest")
    assert manifest["Content-Type"] == "application/manifest+json"
    assert '"display": "standalone"' in manifest.content.decode()
    worker = client.get("/sw.js")
    assert worker["Content-Type"] == "text/javascript"
    assert worker["Service-Worker-Allowed"] == "/"
    assert "img/pwa/badge-96" in worker.content.decode()  # Symbol in der Statusleiste bei Push-Benachrichtigungen
    assert "Android" in worker.content.decode()  # auf Android kein zusätzliches großes Icon


@pytest.mark.django_db(transaction=True)
def test_backup_writes_consistent_copy_and_prunes(settings) -> None:
    User.objects.create_user("mia@example.org")
    today = date(2026, 11, 14)
    old = backup.backup_path(today - timedelta(days=settings.BACKUP_KEEP_DAYS + 1))
    old.parent.mkdir(parents=True, exist_ok=True)
    old.write_bytes(b"alt")
    path = backup.create_backup(today)
    assert path.name == "portal-2026-11-14.sqlite3"
    assert not old.exists()
    with sqlite3.connect(path) as copy:
        count = copy.execute("SELECT COUNT(*) FROM accounts_user").fetchone()[0]
    assert count >= 1


def test_footer_shows_version_with_link_to_release_notes(client, settings) -> None:
    settings.VERSION = "0.2.0"
    page = client.get(reverse("account_login")).content.decode()
    assert "Version 0.2.0" in page
    assert "https://github.com/tlandsberger/judo-portal/releases/tag/v0.2.0" in page


def test_development_version_links_to_release_overview(client, settings) -> None:
    settings.VERSION = "dev"
    page = client.get(reverse("account_login")).content.decode()
    assert "Version dev" in page
    assert 'href="https://github.com/tlandsberger/judo-portal/releases"' in page
