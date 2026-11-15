"""Einmalig: VAPID-Schlüsselpaar für Web Push erzeugen (PORTAL_VAPID_PUBLIC_KEY, PORTAL_VAPID_PRIVATE_KEY)."""

from __future__ import annotations

import base64
from typing import Any

from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from django.core.management.base import BaseCommand


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


class Command(BaseCommand):
    help = "Erzeugt ein VAPID-Schlüsselpaar für Push-Benachrichtigungen."

    def handle(self, *args: Any, **options: Any) -> None:
        key = ec.generate_private_key(ec.SECP256R1())
        private = key.private_numbers().private_value.to_bytes(32, "big")
        public = key.public_key().public_bytes(Encoding.X962, PublicFormat.UncompressedPoint)
        self.stdout.write(f"PORTAL_VAPID_PUBLIC_KEY={_b64(public)}")
        self.stdout.write(f"PORTAL_VAPID_PRIVATE_KEY={_b64(private)}")
        self.stdout.write("Den privaten Schlüssel geheim halten (Portainer). Ein neues Paar beendet alle Push-Abos.")
