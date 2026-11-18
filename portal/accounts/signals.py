"""Signale für andere Apps, damit sie an Abläufe rund um Benutzer andocken, ohne dass accounts sie kennt."""

from django.dispatch import Signal

# Eine Einladung wurde angenommen und der Benutzer angelegt bzw. reaktiviert. Argumente: invitation, user.
invitation_accepted = Signal()

# Anrede für einen Benutzer oder eine Einladung ohne Vornamen, z. B. „Liebe Eltern von Mia“.
# Argumente: user oder invitation (das andere ist None). Empfänger geben eine Anrede oder "" zurück.
greeting_requested = Signal()
