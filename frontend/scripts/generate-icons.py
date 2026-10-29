#!/usr/bin/env python3
"""Erzeugt Favicon und PWA-Icons aus dem Vereinslogo ohne Text.

Quelle: public/branding/logo-signet.png (transparent). Ausgabe nach public/ (Icons, Favicon,
kleines Toolbar-Logo).
Aufruf aus frontend/: python3 scripts/generate-icons.py   (benötigt Pillow)
"""

from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "public/branding/logo-signet.png"
PUBLIC = ROOT / "public"
ICONS = PUBLIC / "icons"
SIZES = [72, 96, 128, 144, 152, 192, 384, 512]
WHITE = (255, 255, 255, 255)


def square(logo: Image.Image, size: int, logo_ratio: float, background) -> Image.Image:
    """Setzt das Logo zentriert auf eine quadratische Fläche; logo_ratio = Anteil der Kantenlänge."""
    canvas = Image.new("RGBA", (size, size), background)
    target = int(size * logo_ratio)
    scaled = logo.copy()
    scaled.thumbnail((target, target), Image.LANCZOS)
    canvas.alpha_composite(scaled, ((size - scaled.width) // 2, (size - scaled.height) // 2))
    return canvas


def main() -> None:
    logo = Image.open(SOURCE).convert("RGBA")
    logo = logo.crop(logo.getbbox())
    ICONS.mkdir(parents=True, exist_ok=True)
    for old in ICONS.glob("*.png"):
        old.unlink()

    for size in SIZES:
        # "any": transparenter Hintergrund, wenig Rand.
        square(logo, size, 0.92, (0, 0, 0, 0)).save(ICONS / f"icon-{size}x{size}.png", optimize=True)
        # "maskable": weißer Hintergrund, Logo innerhalb der 80-%-Safe-Zone (Kreis-Maske).
        square(logo, size, 0.62, WHITE).save(ICONS / f"maskable-{size}x{size}.png", optimize=True)

    # iOS ignoriert Transparenz und das Manifest: eigenes, deckendes Icon.
    square(logo, 180, 0.80, WHITE).save(ICONS / "apple-touch-icon.png", optimize=True)

    # Kleines Logo für die Toolbar (48×40 bei bis zu 2-facher Pixeldichte).
    small = logo.copy()
    small.thumbnail((96, 80), Image.LANCZOS)
    toolbar = Image.new("RGBA", (96, 80), (0, 0, 0, 0))
    toolbar.alpha_composite(small, ((96 - small.width) // 2, (80 - small.height) // 2))
    toolbar.save(PUBLIC / "branding/logo-signet-small.png", optimize=True)

    square(logo, 256, 0.96, (0, 0, 0, 0)).save(
        PUBLIC / "favicon.ico", sizes=[(16, 16), (32, 32), (48, 48), (64, 64)]
    )


if __name__ == "__main__":
    main()
