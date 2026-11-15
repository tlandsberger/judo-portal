from django.apps import AppConfig


class NotificationsConfig(AppConfig):
    name = "portal.notifications"
    verbose_name = "Benachrichtigungen"

    def ready(self) -> None:
        from portal.core import scheduler

        from . import services

        scheduler.register_daily(services.cleanup)
