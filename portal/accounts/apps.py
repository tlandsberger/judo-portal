from django.apps import AppConfig


class AccountsConfig(AppConfig):
    name = "portal.accounts"
    label = "accounts"
    verbose_name = "Benutzer"

    def ready(self) -> None:
        from allauth.account.signals import password_set, user_logged_in
        from allauth.mfa.signals import authenticator_added

        from . import services

        def mark_setup_completed(sender: object, request: object, **kwargs: object) -> None:
            # Nur die Sitzung, in der der Anmeldeweg angelegt wurde, wird freigeschaltet (SetupSessionMiddleware).
            services.mark_setup_completed(request)  # type: ignore[arg-type]

        password_set.connect(mark_setup_completed, dispatch_uid="portal_setup_password", weak=False)
        authenticator_added.connect(mark_setup_completed, dispatch_uid="portal_setup_passkey", weak=False)

        def complete_on_login(sender: object, request: object, user: object, **kwargs: object) -> None:
            # Reguläre Anmeldung (Passkey, Passwort, Code) belegt den Zugang: offene Einladungen sind eingelöst.
            services.complete_invitations(user)  # type: ignore[arg-type]
            # Unbekannter Browser: Warnung per Mail (nicht bei der ersten Anmeldung überhaupt).
            services.check_new_device(request, user)  # type: ignore[arg-type]

        user_logged_in.connect(complete_on_login, dispatch_uid="portal_complete_invitations", weak=False)

        from . import audit_signals

        audit_signals.connect()
