from django.apps import AppConfig


class CoreConfig(AppConfig):
    name = "portal.core"
    label = "core"
    verbose_name = "Portal"

    def ready(self) -> None:
        from . import audit, scheduler

        def cleanup_audit() -> None:
            audit.cleanup()

        scheduler.register_daily(cleanup_audit)
