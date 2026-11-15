from django.apps import AppConfig


class EventsConfig(AppConfig):
    name = "portal.events"
    verbose_name = "Veranstaltungen"

    def ready(self) -> None:
        from . import notices

        notices.register_all()
