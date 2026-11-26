"""Anbindung an das Sprachmodell: ein OpenAI-kompatibler Chat-Endpunkt (llama.cpp ``llama-server``) im internen Netz.

Das Modell bekommt die Beschreibung der Werkzeuge und schlägt Aufrufe vor; ausgeführt werden sie nur im Portal
(``services.ask``) mit den Rechten des Benutzers. ``PORTAL_ASSISTANT_URL=fake`` liefert feste Antworten (``fake.py``).
"""

from __future__ import annotations

import json
import logging
import re
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any

from django.conf import settings

log = logging.getLogger(__name__)

FAKE = "fake"
_THINK = re.compile(r"<think>.*?</think>\s*", re.DOTALL)


class Unavailable(Exception):
    """Das Modell antwortet nicht oder nicht verständlich."""


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class Reply:
    content: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)

    def as_message(self) -> dict[str, Any]:
        """Die Antwort so, wie sie im Verlauf an das Modell zurückgeht."""
        message: dict[str, Any] = {"role": "assistant", "content": self.content}
        if self.tool_calls:
            message["tool_calls"] = [
                {
                    "id": call.id,
                    "type": "function",
                    "function": {"name": call.name, "arguments": json.dumps(call.arguments, ensure_ascii=False)},
                }
                for call in self.tool_calls
            ]
        return message


def _arguments(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    try:
        value = json.loads(raw or "{}")
    except ValueError:
        return {}
    return value if isinstance(value, dict) else {}


def parse(data: dict[str, Any]) -> Reply:
    """Antwort im OpenAI-Format lesen; Denk-Abschnitte (<think>) fallen weg."""
    try:
        message = data["choices"][0]["message"]
    except (KeyError, IndexError, TypeError) as error:
        raise Unavailable("Unerwartete Antwort des Modells") from error
    calls = [
        ToolCall(
            id=str(call.get("id") or f"call_{index}"),
            name=str(call.get("function", {}).get("name", "")),
            arguments=_arguments(call.get("function", {}).get("arguments")),
        )
        for index, call in enumerate(message.get("tool_calls") or [])
    ]
    content = _THINK.sub("", message.get("content") or "").strip()
    return Reply(content=content, tool_calls=calls)


def complete(messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> Reply:
    """Eine Runde mit dem Modell: Verlauf und Werkzeuge hin, Text oder Werkzeugaufrufe zurück."""
    url = settings.ASSISTANT_URL
    if url == FAKE:
        from . import fake

        return fake.complete(messages, tools)
    body = {
        "model": settings.ASSISTANT_MODEL,
        "messages": messages,
        "tools": tools,
        "temperature": 0.2,
        # Qwen3 & Co.: ohne langes Nachdenken antworten, das kostet auf der CPU viel Zeit
        "chat_template_kwargs": {"enable_thinking": False},
    }
    request = urllib.request.Request(  # noqa: S310 – Adresse aus der Konfiguration, nur http(s)
        f"{url}/v1/chat/completions",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=settings.ASSISTANT_TIMEOUT) as response:  # noqa: S310
            data = json.loads(response.read())
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as error:
        log.warning("Sprachmodell nicht erreichbar: %s", error)
        raise Unavailable(str(error)) from error
    return parse(data)


def healthy() -> bool:
    """Antwortet der Modell-Server? (für den Messbefehl und die Hilfe-Seite)"""
    url = settings.ASSISTANT_URL
    if not url:
        return False
    if url == FAKE:
        return True
    try:
        with urllib.request.urlopen(f"{url}/health", timeout=5) as response:  # noqa: S310
            return bool(response.status == 200)
    except urllib.error.URLError, TimeoutError, OSError:
        return False
