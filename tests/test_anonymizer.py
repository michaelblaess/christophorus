"""Anonymisierung für Screenshots: Kern und laufende App.

Die echten Werte in diesen Tests sind absichtlich so gewählt, dass sie in
keiner Ersatzliste des Anonymizers vorkommen. Sonst könnte ein Test grün
sein, weil der Ersatz zufällig dem Original gleicht.
"""

from __future__ import annotations

import html
import re
from pathlib import Path
from typing import Any

from christo.app import FahrtenbuchApp
from christo.models.fahrtenbuch import Fahrtenbuch
from christo.models.settings import GlobalConfig
from christo.models.trip import MonthData
from christo.models.vehicle import Vehicle
from christo.services.anonymizer import FAKE_PATH, FAKE_PLATE, Anonymizer
from tests.conftest import make_trip

ECHTES_ZIEL = "Zebrawerke Quastenhausen"
ECHTER_ZWECK = "Geheimprojekt Okapi"
ECHTES_KENNZEICHEN = "QX-ZZ 987"
ECHTER_FAHRZEUGNAME = "Knattermobil Deluxe"


# --- Kern -------------------------------------------------------------------------


def test_fahrt_wird_verfremdet_zahlen_bleiben() -> None:
    anon = Anonymizer()
    trip = make_trip("2024-05-06", 42, destination=ECHTES_ZIEL, purpose=ECHTER_ZWECK)
    trip.time_from, trip.time_to = "08:00", "09:00"

    fake = anon.trip(trip)

    assert ECHTES_ZIEL not in fake.destination
    assert ECHTER_ZWECK not in fake.purpose
    assert (fake.date, fake.km_end, fake.km_business, fake.time_from) == (trip.date, 42, 42, "08:00")
    assert trip.destination == ECHTES_ZIEL, "das Original darf nicht veraendert werden"


def test_ersatz_ist_stabil() -> None:
    # Derselbe Kunde muss in jeder Ansicht und nach jedem Neuladen gleich heissen.
    assert Anonymizer().destination(ECHTES_ZIEL) == Anonymizer().destination(ECHTES_ZIEL)


def test_geschaeftsessen_ueberlebt_den_ersatz() -> None:
    # Die Hervorhebung in Liste, Kalender und Pruefung haengt an diesem Wort.
    fake = Anonymizer().purpose("Geschaeftsessen mit Herrn Okapi")
    assert "geschaeftsessen" in fake.lower()
    assert "Okapi" not in fake


def test_leere_werte_bleiben_leer() -> None:
    anon = Anonymizer()
    assert anon.destination("") == ""
    assert anon.purpose("   ") == "   "


def test_fahrzeug_und_pfad() -> None:
    anon = Anonymizer()
    vehicle = Vehicle(
        name=ECHTER_FAHRZEUGNAME, plate=ECHTES_KENNZEICHEN, contract_number="VN-4711", lease_km_per_month=1234
    )
    fake = anon.vehicle(vehicle)
    assert fake is not None
    assert (fake.plate, fake.lease_km_per_month) == (FAKE_PLATE, 1234)
    assert ECHTER_FAHRZEUGNAME not in fake.name
    assert anon.path(r"D:\Dropbox\Fahrtenbuecher\Knattermobil (QX-ZZ 987)") == FAKE_PATH


def test_censor_ersetzt_alles_gesehene_in_freiem_text() -> None:
    anon = Anonymizer()
    anon.month_data(MonthData(2024, 5, [make_trip("2024-05-04", 10, destination=ECHTES_ZIEL, purpose=ECHTER_ZWECK)]))
    anon.vehicle(Vehicle(name=ECHTER_FAHRZEUGNAME, plate=ECHTES_KENNZEICHEN))

    text = anon.censor(
        f"Fahrt am Samstag: {ECHTER_ZWECK} nach {ECHTES_ZIEL}, {ECHTER_FAHRZEUGNAME} ({ECHTES_KENNZEICHEN})"
    )

    for echt in (ECHTES_ZIEL, ECHTER_ZWECK, ECHTER_FAHRZEUGNAME, ECHTES_KENNZEICHEN):
        assert echt not in text


def test_belege_verlieren_dateinamen_aber_nicht_die_endung() -> None:
    fake = Anonymizer().documents(
        [{"id": 1, "path": "belege/Rechnung Okapi GmbH.pdf", "description": "Okapi-Rechnung"}]
    )
    assert fake[0]["path"].endswith(".pdf")
    assert "Okapi" not in fake[0]["path"]
    assert "Okapi" not in fake[0]["description"]


# --- Laufende App -----------------------------------------------------------------


def _bildschirmtext(app: FahrtenbuchApp) -> str:
    svg = app.export_screenshot()
    zeilen = re.findall(r"<text[^>]*>(.*?)</text>", svg)
    return " ".join(html.unescape(re.sub(r"<[^>]+>", "", z)) for z in zeilen).replace("\xa0", " ")


async def _settle(pilot: Any) -> None:
    for _ in range(3):
        await pilot.pause()


def _fahrtenbuch_anlegen(tmp_path: Path) -> Path:
    pfad = tmp_path / "Knattermobil"
    pfad.mkdir()
    vehicle = Vehicle(
        name=ECHTER_FAHRZEUGNAME,
        plate=ECHTES_KENNZEICHEN,
        contract_number="VN-4711",
        lease_km_per_month=1500,
        start_km=10000,
        end_km=30000,
        start_date="2024-01-01",
        end_date="2024-12-31",
        lease_months=12,
    )
    fb = Fahrtenbuch.create(pfad, vehicle)
    # Samstag - die Pruefung meldet die Fahrt samt Reisezweck.
    fb.database.add_trip(make_trip("2024-05-04", 50, destination=ECHTES_ZIEL, purpose=ECHTER_ZWECK))
    fb.close()
    config = GlobalConfig.load()
    config.last_opened_path = str(pfad)
    config.keymap_style = "classic"
    config.save()
    return pfad


async def test_anonymisierung_in_der_app(tmp_path: Path) -> None:
    _fahrtenbuch_anlegen(tmp_path)
    app = FahrtenbuchApp(year_override=2024)
    async with app.run_test(size=(220, 60)) as pilot:
        await _settle(pilot)
        app._month = 5
        app._refresh_data()
        await _settle(pilot)
        assert ECHTER_ZWECK in _bildschirmtext(app), "Vorbedingung: echte Daten sind sichtbar"

        await pilot.press("a")
        await _settle(pilot)
        await pilot.press("p")  # Pruefung schreibt Meldungen mit Reisezweck ins Log
        await _settle(pilot)

        text = _bildschirmtext(app)
        for echt in (ECHTES_ZIEL, ECHTER_ZWECK, ECHTER_FAHRZEUGNAME, ECHTES_KENNZEICHEN, "Knattermobil"):
            assert echt not in text, echt
        assert FAKE_PLATE in text

        # Dialoge mit echten Daten bleiben zu.
        stapel = len(app.screen_stack)
        await pilot.press("n")
        await _settle(pilot)
        assert len(app.screen_stack) == stapel

        await pilot.press("a")
        await _settle(pilot)
        assert ECHTER_ZWECK in _bildschirmtext(app)
