"""Feste Antworten statt eines Sprachmodells (``PORTAL_ASSISTANT_URL=fake``) für E2E-Tests und die Demo.

Ruft wie ein echtes Modell Werkzeuge auf: Fragen mit „Termin“ oder „Training“ suchen die Termine der nächsten Woche,
Fragen mit „Hilfe“ oder „wie“ durchsuchen die Hilfe; die Antwort fasst das Ergebnis zusammen.
"""

from __future__ import annotations

import json
from typing import Any

from .llm import Reply, ToolCall

GREETING = (
    "Hallo, ich bin Uke! Frag mich zum Beispiel: „Welche Trainings sind diese Woche?“ oder „Wie richte ich einen "
    "Passkey ein?“"
)


def complete(messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> Reply:
    last = messages[-1]
    if last["role"] == "tool":
        data = json.loads(last["content"])
        if isinstance(data, dict) and "termine" in data:
            if not data["termine"]:
                return Reply(f"Von {data['zeitraum']} habe ich keine Termine gefunden.")
            lines = [f"- {t['titel']}: {t['wann']}" for t in data["termine"]]
            return Reply(f"Ich habe {data['anzahl']} Termine gefunden:\n" + "\n".join(lines))
        if isinstance(data, list) and data:
            return Reply(f"Dazu steht in der Hilfe im Kapitel „{data[0]['kapitel']}“:\n{data[0]['text'][:300]}")
        return Reply("Dazu habe ich nichts gefunden.")
    text = str(last.get("content", "")).lower()
    names = {tool["function"]["name"] for tool in tools}
    if ("termin" in text or "training" in text) and "termine_suchen" in names:
        return Reply(tool_calls=[ToolCall("call_0", "termine_suchen", {})])
    if ("hilfe" in text or text.startswith("wie")) and "hilfe_suchen" in names:
        return Reply(tool_calls=[ToolCall("call_0", "hilfe_suchen", {"frage": text})])
    return Reply(GREETING)
