from django.apps import AppConfig


class PrivacyConfig(AppConfig):
    name = "portal.privacy"
    verbose_name = "Datenschutz"

    def ready(self) -> None:
        from portal.core import scheduler

        from . import services

        scheduler.register_daily(services.run_daily)
