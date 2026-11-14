from django.core.management.base import BaseCommand

from portal.accounts.services import ensure_initial_admin


class Command(BaseCommand):
    help = "Lädt PORTAL_INITIAL_ADMIN_EMAIL als Administrator ein, solange es keinen aktiven Administrator gibt."

    def handle(self, *args: object, **options: object) -> None:
        invitation = ensure_initial_admin()
        if invitation:
            self.stdout.write(f"Einladung an {invitation.email} verschickt.")
