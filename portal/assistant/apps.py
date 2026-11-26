from django.apps import AppConfig


class AssistantConfig(AppConfig):
    name = "portal.assistant"
    verbose_name = "Assistent Uke"

    def ready(self) -> None:
        from portal.core import scheduler

        from . import services

        scheduler.register_daily(services.cleanup)
