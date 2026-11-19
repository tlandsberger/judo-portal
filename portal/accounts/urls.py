from django.urls import path

from . import views

urlpatterns = [
    path("einladung/<str:token>/", views.accept_invitation, name="accept_invitation"),
    path("zugang/einrichten/", views.setup_login, name="setup_login"),
    path("zugang/einrichten/per-code/", views.setup_login_by_code, name="setup_login_by_code"),
    path("zugang/anmeldung/", views.security, name="security"),
    path("zugang/e-mail/", views.email_change, name="email_change"),
    path("zugang/e-mail/<str:token>/", views.confirm_email_change, name="confirm_email_change"),
    path("verwaltung/benutzer/", views.user_list, name="user_list"),
    path("verwaltung/benutzer/einladen/", views.invite, name="invite"),
    path("verwaltung/benutzer/<int:pk>/", views.edit_user, name="edit_user"),
    path("verwaltung/benutzer/<int:pk>/e-mail/", views.user_email_change, name="user_email_change"),
    path("verwaltung/benutzer/<int:pk>/aktiv/", views.toggle_active, name="toggle_active"),
    path("verwaltung/einladungen/<int:pk>/erneut/", views.resend_invitation, name="resend_invitation"),
    path("verwaltung/einladungen/<int:pk>/zurueckziehen/", views.delete_invitation, name="delete_invitation"),
    path("verwaltung/einladungen/<int:pk>/link/", views.invitation_link, name="invitation_link"),
    path("verwaltung/benutzer/<int:pk>/einladen/", views.reinvite_user, name="reinvite_user"),
]
