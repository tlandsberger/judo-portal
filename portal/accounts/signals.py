"""Signale für andere Apps, damit sie an Abläufe rund um Benutzer andocken, ohne dass accounts sie kennt."""

from django.dispatch import Signal

# Eine Einladung wurde angenommen und der Benutzer angelegt bzw. reaktiviert. Argumente: invitation, user.
invitation_accepted = Signal()
