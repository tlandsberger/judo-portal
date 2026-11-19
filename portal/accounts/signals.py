"""Signale für andere Apps, damit sie an Abläufe rund um Benutzer andocken, ohne dass accounts sie kennt."""

from django.dispatch import Signal

# Eine Einladung wurde angenommen und der Benutzer angelegt bzw. reaktiviert. Argumente: invitation, user.
invitation_accepted = Signal()

# Anrede für einen Benutzer oder eine Einladung ohne Vornamen, z. B. „Liebe Eltern von Mia“.
# Argumente: user oder invitation (das andere ist None). Empfänger geben eine Anrede oder "" zurück.
greeting_requested = Signal()

# Name des eigenen Mitgliedsprofils eines Benutzers (für „In die Mitgliedsdaten übernehmen“). Argumente: user.
# Empfänger geben den Namen oder "" zurück.
own_member_requested = Signal()

# Die neue E-Mail-Adresse eines Benutzers ist bestätigt. Argumente: user, old_email, sync_member, by.
email_changed = Signal()
