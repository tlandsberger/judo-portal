from argparse import ArgumentParser

from django.core.management.base import BaseCommand

from portal.accounts.models import Role
from portal.accounts.services import invitation_url, invite


class Command(BaseCommand):
    help = (
        "Lädt eine Person ein und gibt den Link aus – Rettungsweg ohne Oberfläche, z. B. "
        "docker exec judo_portal python manage.py invite du@example.org --admin"
    )

    def add_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument("email")
        parser.add_argument("--admin", action="store_true", help="mit der Rolle Administrator")
        parser.add_argument("--no-mail", action="store_true", help="keine Mail verschicken, nur den Link ausgeben")

    def handle(self, *args: object, **options: object) -> None:
        roles: list[str] = [Role.ADMIN.value] if options["admin"] else []
        invitation = invite(str(options["email"]), roles=roles, send=not options["no_mail"])
        self.stdout.write(f"Einladung für {invitation.email}: {invitation_url(invitation)}")
