"""Erzeugt Favicons und App-Icons aus den Signet-Masken in assets/icons/.

Aufruf: uv run --with pillow python scripts/make_icons.py

- App-Icon (Home-Bildschirm, Apple, Install-Hinweis): weißes Signet mit mattgrünen Akzenten auf Tiefgrün,
  passt zu hellem und dunklem Modus.
- Favicon hell/dunkel: Signet ohne Hintergrund, schwarz bzw. weiß; der Browser wählt passend zum Modus.
- favicon.ico: neutrale Variante (wie das App-Icon) für Browser, die keine Modus-Varianten kennen.
- badge-96.png: Symbol für Push-Nachrichten in der Statusleiste (Android). Android nutzt nur die Form (Transparenz)
  und färbt selbst ein; deshalb nur die Figuren, ohne Akzente, und mit verdickten Linien (24 dp sind sehr klein).
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "assets" / "icons"
TARGET = ROOT / "portal" / "static" / "img" / "pwa"

TIEFGRUEN = (10, 61, 28)
VEREINSGRUEN_DUNKLER = (2, 106, 42)
VEREINSGRUEN = (2, 125, 49)
MATTENGRUEN = (95, 184, 120)
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)

FIGURES = Image.open(SOURCE / "signet-figuren.png").convert("L")
ACCENTS = Image.open(SOURCE / "signet-akzente.png").convert("L")


def signet(width: int, figure_color: tuple[int, int, int], accent_color: tuple[int, int, int]) -> Image.Image:
    """Signet in der gewünschten Breite und den Farben, transparenter Hintergrund."""
    height = round(FIGURES.height * width / FIGURES.width)
    # Hochauflösend einfärben, dann verkleinern: saubere Kanten auch bei 16 px
    figures = FIGURES.resize((width, height), Image.Resampling.LANCZOS)
    accents = ACCENTS.resize((width, height), Image.Resampling.LANCZOS)
    layer = Image.new("RGBA", (width, height), (*figure_color, 0))
    layer.putalpha(figures)
    accent = Image.new("RGBA", (width, height), (*accent_color, 0))
    accent.putalpha(accents)
    return Image.alpha_composite(layer, accent)


def background(size: int, radius: float = 0) -> Image.Image:
    """Tiefgrün mit leichtem Verlauf nach oben links; optional abgerundet."""
    scale = 4
    big = size * scale
    # Weicher Verlauf: klein berechnen, dann glatt vergrößern
    steps = 32
    small = Image.new("RGBA", (steps, steps))
    for y in range(steps):
        for x in range(steps):
            t = min(1.0, ((x / steps) ** 2 + (y / steps) ** 2) ** 0.5 / 1.2)
            color = tuple(round(a + (b - a) * t) for a, b in zip(VEREINSGRUEN_DUNKLER, TIEFGRUEN, strict=True))
            small.putpixel((x, y), (*color, 255))
    gradient = small.resize((big, big), Image.Resampling.BICUBIC)
    if radius:
        mask = Image.new("L", (big, big), 0)
        ImageDraw.Draw(mask).rounded_rectangle((0, 0, big - 1, big - 1), radius=radius * big, fill=255)
        gradient.putalpha(mask)
    return gradient.resize((size, size), Image.Resampling.LANCZOS)


def app_icon(size: int, coverage: float, radius: float = 0) -> Image.Image:
    icon = background(size, radius)
    mark = signet(round(size * coverage), WHITE, MATTENGRUEN)
    icon.alpha_composite(mark, ((size - mark.width) // 2, (size - mark.height) // 2))
    return icon


def favicon(size: int, figure_color: tuple[int, int, int], accent_color: tuple[int, int, int]) -> Image.Image:
    icon = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    mark = signet(size, figure_color, accent_color)
    icon.alpha_composite(mark, (0, (size - mark.height) // 2))
    return icon


def badge(size: int, coverage: float) -> Image.Image:
    icon = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    width = round(size * coverage)
    height = round(FIGURES.height * width / FIGURES.width)
    # Linien vor dem Verkleinern verdicken (Maske ist ca. 4,5-mal so breit wie das Badge)
    figures = FIGURES.filter(ImageFilter.MaxFilter(9)).resize((width, height), Image.Resampling.LANCZOS)
    mark = Image.new("RGBA", (width, height), (*WHITE, 0))
    mark.putalpha(figures)
    icon.alpha_composite(mark, ((size - width) // 2, (size - height) // 2))
    return icon


def main() -> None:
    # Android/Chrome zeigen „any“-Icons unverändert: eigene abgerundete Form
    app_icon(192, 0.72, radius=0.22).save(TARGET / "icon-192.png", optimize=True)
    app_icon(512, 0.72, radius=0.22).save(TARGET / "icon-512.png", optimize=True)
    # Maskable: vollflächig, Signet innerhalb der sicheren Zone (Kreis mit 80 % Durchmesser)
    app_icon(512, 0.62).save(TARGET / "icon-maskable-512.png", optimize=True)
    # iOS rundet selbst ab und mag keine Transparenz
    app_icon(180, 0.7).convert("RGB").save(TARGET / "apple-touch-icon.png", optimize=True)
    # Favicons passend zum Modus (Browser-Tab)
    favicon(64, BLACK, VEREINSGRUEN).save(TARGET / "favicon-hell.png", optimize=True)
    favicon(64, WHITE, MATTENGRUEN).save(TARGET / "favicon-dunkel.png", optimize=True)
    # Neutrale Variante für Browser ohne Modus-Unterstützung
    app_icon(64, 0.8, radius=0.22).save(TARGET / "favicon.ico", sizes=[(16, 16), (32, 32), (48, 48), (64, 64)])
    # Statusleiste bei Push-Nachrichten (Android, 24 dp)
    badge(96, 0.86).save(TARGET / "badge-96.png", optimize=True)
    print("Icons erzeugt in", TARGET.relative_to(ROOT))


if __name__ == "__main__":
    main()
