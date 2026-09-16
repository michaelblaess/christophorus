"""Nimmt die Screenshots für README und Projektseite headless auf - mit erfundenen Daten.

Nicht der Anonymisierungs-Modus der Anwendung: der verfremdet Ziele und Zwecke,
lässt aber Kilometer, Daten und Uhrzeiten stehen. Hier bekommt die Anwendung
stattdessen ein vollständig erfundenes Fahrtenbuch in einem Wegwerf-Ordner.
Die echte Konfiguration (~/.christo) wird nie gelesen.

Ablauf: Anwendung headless starten, Ansicht ansteuern, Textual schreibt ein SVG,
das gecachte Playwright-Chromium rendert daraus ein PNG.

Aufruf aus dem Repo-Wurzelverzeichnis:

    .venv/Scripts/python.exe assets/make_screenshots.py

Die Bilder landen in docs/screenshots/<sprache>/. Vor dem Commit ansehen.
"""

from __future__ import annotations

import asyncio
import os
import subprocess
import sys
import tempfile
from collections.abc import Awaitable, Callable
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from PIL import Image, ImageChops

WURZEL = Path(__file__).resolve().parent.parent
ZIEL = WURZEL / "docs" / "screenshots"
BREITE, HOEHE = 180, 50
THEME = "corleone"
ANZEIGE_PFAD = {"en": "~/Logbooks/Kompaktkombi", "de": "~/Fahrtenbücher/Kompaktkombi"}

# Vor jedem Import aus christo umbiegen - sonst liest die Anwendung ~/.christo.
_HOME = Path(tempfile.mkdtemp(prefix="christo-screens-"))
os.environ["CHRISTO_HOME"] = str(_HOME)
sys.path.insert(0, str(WURZEL / "src"))

from textual.widgets import Tabs  # noqa: E402
from textual_widgets import DisclaimerStore  # noqa: E402

from christo.i18n import load_locale  # noqa: E402
from christo.models.fahrtenbuch import Fahrtenbuch  # noqa: E402
from christo.models.settings import GlobalConfig  # noqa: E402
from christo.models.trip import Trip  # noqa: E402
from christo.models.vehicle import Vehicle  # noqa: E402
from christo.services.holiday_service import HolidayService  # noqa: E402
from christo.widgets.config_panel import ConfigPanel  # noqa: E402

# Ziel, Zweck, einfache Strecke in km. Alles erfunden.
_ZIELE = (
    ("Kunde Nord, Musterstadt", "Projektbesprechung", 42),
    ("Beispiel AG, Beispielstadt", "Kundentermin", 67),
    ("Musterfirma GmbH, Musterhausen", "Abnahme vor Ort", 118),
    ("Steuerbüro Musterweg", "Unterlagen abgeben", 18),
    ("Werkstatt Industriestraße", "Inspektion", 9),
    ("Kunde Süd, Beispielhausen", "Schulung", 85),
)
_PRIVAT = (("Supermarkt", "Einkauf", 6), ("Freunde, Musterdorf", "Besuch", 31), ("Badesee", "Ausflug", 24))


def _trip(tag: date, ziel: str, zweck: str, km: int, kategorie: str, von: str, bis: str, liter: float = 0.0) -> Trip:
    geschaeftlich = kategorie in ("business", "fuel", "service")
    return Trip(
        date=tag.isoformat(),
        time_from=von,
        time_to=bis,
        destination=ziel,
        purpose=zweck,
        km_start=0,
        km_end=km,
        km_business=km if geschaeftlich else 0,
        km_private=0 if geschaeftlich else km,
        category=kategorie,
        round_trip=kategorie == "business",
        fuel_liters=liter,
        fuel_full_tank=liter > 0,
    )


def fahrtenbuch_anlegen() -> Path:
    """Legt einen erfundenen Jahrgang Januar bis September 2026 an."""
    pfad = _HOME / "Kompaktkombi"
    pfad.mkdir()
    fahrzeug = Vehicle(
        name="Kompaktkombi",
        plate="XX-CH 26",
        contract_number="V-2026-001",
        lease_km_per_month=1500,
        start_km=12000,
        end_km=66000,
        start_date="2026-01-01",
        end_date="2028-12-31",
        lease_months=36,
        tank_capacity_l=60,
    )
    fb = Fahrtenbuch.create(pfad, fahrzeug)
    db = fb.database
    feiertage: set[date] = set()
    for monat in range(1, 10):
        feiertage |= set(HolidayService("BB").get_holidays_in_month(2026, monat))
    # Urlaub im August - an diesen Tagen gibt es keine Geschaeftsfahrten.
    urlaub = {date(2026, 8, t) for t in range(10, 21)}
    frei = feiertage | urlaub
    tag = date(2026, 1, 2)
    zaehler = 0
    seit_tanken = 0
    while tag <= date(2026, 9, 30):
        zaehler += 1
        if tag.weekday() < 5 and tag not in frei and zaehler % 7 not in (3,):
            ziel, zweck, km = _ZIELE[zaehler % len(_ZIELE)]
            # Feste Streuung statt Zufall - das Bild bleibt reproduzierbar.
            km = km + (zaehler % 5) * 2
            start = 7 + zaehler % 3
            db.add_trip(_trip(tag, ziel, zweck, km, "business", f"{start:02d}:15", f"{start + 3:02d}:40"))
            seit_tanken += km
        elif tag.weekday() == 5 and zaehler % 2 == 0:
            ziel, zweck, km = _PRIVAT[zaehler % len(_PRIVAT)]
            db.add_trip(_trip(tag, ziel, zweck, km * 2, "private", "10:00", "12:30"))
            seit_tanken += km * 2
        if seit_tanken > 520 and tag.weekday() < 5 and tag not in frei:
            liter = round(seit_tanken * 6.4 / 100, 1)
            db.add_trip(_trip(tag, "Tankstelle Hauptstraße", "Tanken", 3, "fuel", "17:05", "17:20", liter))
            seit_tanken = 0
        tag += timedelta(days=1)

    # Ein Samstag mit Geschäftsfahrt, damit der Plausicheck etwas zu sagen hat.
    db.add_trip(_trip(date(2026, 5, 16), "Kunde Nord, Musterstadt", "Messeaufbau", 84, "business", "08:00", "18:00"))
    for urlaubstag in sorted(urlaub):
        db.add_blacklist_entry(urlaubstag.isoformat(), "Urlaub")
    for monat in range(1, 10):
        db.save_worktime(2026, monat, 150 + monat * 2)
    db.set_setting("federal_state", "BB")
    db.set_setting("last_viewed_year", "2026")
    db.set_setting("last_viewed_month", "5")
    fb.close()
    return pfad


def chromium() -> Path:
    basis = Path(os.environ["LOCALAPPDATA"]) / "ms-playwright"
    kandidaten = sorted(basis.glob("chromium-*/chrome-win64/chrome.exe"), reverse=True)
    if not kandidaten:
        raise SystemExit("Kein gecachtes Chromium gefunden (siehe reference_headless_browser_smoketest).")
    return kandidaten[0]


def svg_nach_png(svg: Path, png: Path, browser: Path) -> None:
    """Rendert das SVG und reduziert auf 256 Farben (Terminalbilder brauchen nicht mehr)."""
    png.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            str(browser),
            "--headless",
            "--no-sandbox",
            "--disable-gpu",
            "--hide-scrollbars",
            "--force-device-scale-factor=1",
            f"--window-size={BREITE * 9},{HOEHE * 21}",
            f"--screenshot={png}",
            svg.resolve().as_uri(),
        ],
        capture_output=True,
        check=True,
    )
    with Image.open(png) as bild:
        rgb = bild.convert("RGB")
    # Das Browserfenster ist groesser als das SVG - den weissen Rand abschneiden,
    # sonst steht das Terminal in README und auf der Projektseite in einem Kasten.
    rand = ImageChops.difference(rgb, Image.new("RGB", rgb.size, (255, 255, 255))).getbbox()
    if rand:
        rgb = rgb.crop(rand)
    klein = rgb.quantize(colors=256, method=Image.Quantize.MEDIANCUT)
    klein.save(png, optimize=True)


async def _tab(app: Any, pilot: Any, tab_id: str) -> None:
    app.query_one("#view-tabs", Tabs).active = tab_id
    for _ in range(4):
        await pilot.pause()


async def _liste(app: Any, pilot: Any) -> None:
    await _tab(app, pilot, "tab-list")


async def _kalender(app: Any, pilot: Any) -> None:
    await _tab(app, pilot, "tab-calendar")


async def _jahr(app: Any, pilot: Any) -> None:
    await _tab(app, pilot, "tab-year")


async def _plausicheck(app: Any, pilot: Any) -> None:
    await _tab(app, pilot, "tab-list")
    await pilot.press("f4")
    await pilot.press("f8")
    for _ in range(6):
        await pilot.pause()


async def _neue_fahrt(app: Any, pilot: Any) -> None:
    await _tab(app, pilot, "tab-list")
    await pilot.press("f7")
    for _ in range(6):
        await pilot.pause()


ANSICHTEN: dict[str, Callable[[Any, Any], Awaitable[None]]] = {
    "01-month-list": _liste,
    "02-calendar": _kalender,
    "03-year-overview": _jahr,
    "04-plausicheck": _plausicheck,
    "05-new-trip": _neue_fahrt,
}


async def aufnehmen(sprache: str, name: str, pfad: Path, browser: Path) -> Path:
    load_locale(sprache)
    config = GlobalConfig.load()
    config.last_opened_path = str(pfad)
    config.language = sprache
    config.theme = THEME
    config.keymap_style = "function_keys"
    config.log_visible = False
    config.save()

    from christo.app import FahrtenbuchApp

    app = FahrtenbuchApp()
    async with app.run_test(size=(BREITE, HOEHE)) as pilot:
        for _ in range(6):
            await pilot.pause()
        # Der echte Ordner liegt im Temp-Verzeichnis und traegt den Benutzernamen.
        # Im Bild steht deshalb ein neutraler Pfad.
        app.query_one("#config-panel", ConfigPanel).update_vehicle(app._fahrtenbuch.vehicle, ANZEIGE_PFAD[sprache])
        await ANSICHTEN[name](app, pilot)
        svg = _HOME / f"{sprache}-{name}.svg"
        app.save_screenshot(str(svg))
    png = ZIEL / sprache / f"{name}.png"
    svg_nach_png(svg, png, browser)
    return png


async def main() -> None:
    DisclaimerStore(_HOME / "disclaimer.json").record()
    pfad = fahrtenbuch_anlegen()
    browser = chromium()
    for sprache in ("en", "de"):
        for name in ANSICHTEN:
            png = await aufnehmen(sprache, name, pfad, browser)
            print(f"{png.relative_to(WURZEL)}  {png.stat().st_size // 1024} KB")


if __name__ == "__main__":
    asyncio.run(main())
