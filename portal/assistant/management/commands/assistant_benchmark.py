"""Wie schnell antwortet Uke auf diesem Rechner? Schickt ein paar typische Fragen an das Sprachmodell und misst.

    docker exec judo_portal python manage.py assistant_benchmark

Es werden keine Daten aus dem Portal verwendet oder gespeichert; die Werkzeuge liefern feste Beispielergebnisse.
"""

from __future__ import annotations

import json
import time
from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from portal.assistant import llm, tools

QUESTIONS = (
    "Hallo, wer bist du?",
    "Welche Trainings sind morgen?",
    "Wie richte ich einen Passkey ein?",
)
SAMPLE = {
    "termine_suchen": {
        "anzahl": 1,
        "termine": [{"termin_id": 1, "titel": "Kindertraining", "wann": "Fr, 27.11.2026, 17:00–18:30 Uhr"}],
    },
    "termin_details": {"termin_id": 1, "titel": "Kindertraining", "angemeldet": 12},
    "hilfe_suchen": [{"kapitel": "Erste Schritte", "text": "Passkey einrichten unter Meine Anmeldung."}],
}
SYSTEM = "Du bist Uke, ein Assistent für einen Judoverein. Antworte kurz auf Deutsch. Heute ist Donnerstag, 26.11.2026."


class Command(BaseCommand):
    help = "Misst die Antwortzeit des Sprachmodells mit Beispielfragen."

    def handle(self, *args: Any, **options: Any) -> None:
        if not settings.ASSISTANT_URL or settings.ASSISTANT_URL == llm.FAKE:
            raise CommandError("PORTAL_ASSISTANT_URL ist nicht auf einen Modell-Server gesetzt.")
        if not llm.healthy():
            raise CommandError(f"Der Modell-Server unter {settings.ASSISTANT_URL} antwortet nicht.")
        specs = [tool.spec for tool in tools.TOOLS]
        total = 0.0
        for question in QUESTIONS:
            messages: list[dict[str, Any]] = [
                {"role": "system", "content": SYSTEM},
                {"role": "user", "content": question},
            ]
            start = time.monotonic()
            used = []
            for _ in range(3):
                reply = llm.complete(messages, specs)
                if not reply.tool_calls:
                    break
                messages.append(reply.as_message())
                for call in reply.tool_calls:
                    used.append(call.name)
                    content = json.dumps(SAMPLE.get(call.name, {}), ensure_ascii=False)
                    messages.append({"role": "tool", "tool_call_id": call.id, "content": content})
            seconds = time.monotonic() - start
            total += seconds
            self.stdout.write(f"{seconds:5.1f} s  {question}")
            self.stdout.write(f"         Werkzeuge: {', '.join(used) or '–'}")
            self.stdout.write(f"         Antwort: {reply.content[:200]}")
        self.stdout.write(self.style.SUCCESS(f"Durchschnitt: {total / len(QUESTIONS):.1f} s je Frage"))
