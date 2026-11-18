from django.apps import AppConfig


class EventsConfig(AppConfig):
    name = "portal.events"
    verbose_name = "Veranstaltungen"

    def ready(self) -> None:
        from . import attachments, guests, notices

        notices.register_all()
        guests.register_all()
        attachments.register_all()
