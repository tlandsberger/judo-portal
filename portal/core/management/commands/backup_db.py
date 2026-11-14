from django.core.management.base import BaseCommand

from portal.core.backup import create_backup


class Command(BaseCommand):
    help = "Schreibt sofort einen Schnappschuss der Datenbank nach PORTAL_DATA_DIR/backups."

    def handle(self, *args: object, **options: object) -> None:
        self.stdout.write(str(create_backup()))
