from django.apps import AppConfig


class MembersConfig(AppConfig):
    name = "portal.members"
    verbose_name = "Mitglieder"

    def ready(self) -> None:
        from portal.core import scheduler

        from . import child_access, signals  # noqa: F401

        scheduler.register_daily(child_access.run_daily)
