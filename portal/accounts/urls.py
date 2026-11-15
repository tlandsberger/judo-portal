from django.urls import path

from . import views

urlpatterns = [
    path("einladung/<str:token>/", views.accept_invitation, name="accept_invitation"),
    path("konto/einrichten/", views.setup_login, name="setup_login"),
    path("konto/einrichten/per-code/", views.setup_login_by_code, name="setup_login_by_code"),
    path("konto/anmeldung/", views.security, name="security"),
    path("verwaltung/konten/", views.account_list, name="account_list"),
    path("verwaltung/konten/einladen/", views.invite, name="invite"),
    path("verwaltung/konten/<int:pk>/", views.edit_account, name="edit_account"),
    path("verwaltung/konten/<int:pk>/aktiv/", views.toggle_active, name="toggle_active"),
    path("verwaltung/einladungen/<int:pk>/erneut/", views.resend_invitation, name="resend_invitation"),
    path("verwaltung/einladungen/<int:pk>/zurueckziehen/", views.delete_invitation, name="delete_invitation"),
    path("verwaltung/einladungen/<int:pk>/link/", views.invitation_link, name="invitation_link"),
    path("verwaltung/konten/<int:pk>/einladen/", views.reinvite_account, name="reinvite_account"),
]
