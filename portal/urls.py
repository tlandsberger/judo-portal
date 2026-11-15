from django.contrib import admin
from django.urls import include, path
from django.views.generic import RedirectView

from portal.core import views as core

admin.site.site_header = "Wedeler TSV Judo – technische Verwaltung"
admin.site.site_title = "Wedeler TSV Judo"

urlpatterns = [
    path("", core.home, name="home"),
    path("bausteine/", core.components, name="components"),
    path("healthz", core.healthz, name="healthz"),
    path("manifest.webmanifest", core.manifest, name="manifest"),
    path("sw.js", core.service_worker, name="service_worker"),
    path("offline/", core.offline, name="offline"),
    path("", include("portal.accounts.urls")),
    path("", include("portal.members.urls")),
    path("", include("portal.events.urls")),
    path("", include("portal.notifications.urls")),
    # allauths Übersicht „Zwei-Faktor-Authentifizierung“ ersetzt die eigene Seite „Meine Anmeldung“.
    path("anmeldung/2fa/", RedirectView.as_view(pattern_name="security"), name="mfa_index_redirect"),
    path("anmeldung/", include("allauth.urls")),
    path("technik/", admin.site.urls),
]
