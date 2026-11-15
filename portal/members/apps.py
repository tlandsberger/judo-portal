from django.apps import AppConfig


class MembersConfig(AppConfig):
    name = "portal.members"
    verbose_name = "Mitglieder"

    def ready(self) -> None:
        from . import signals  # noqa: F401
