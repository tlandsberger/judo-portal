from django.apps import AppConfig


class BillingConfig(AppConfig):
    name = "portal.billing"
    verbose_name = "Abrechnung"

    def ready(self) -> None:
        from . import notices, services

        services.register_all()
        notices.register_all()
