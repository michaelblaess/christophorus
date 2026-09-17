"""Die TUI-Maske speichert ueber die gemeinsamen Regeln aus services/trip_rules.py.

Absicherung fuer die Umstellung vom 17.09.2026: vorher standen die Regeln in der Maske selbst.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from textual.app import App
from textual.widgets import Input

from christo.models.trip import Trip, set_business_categories, set_informational_categories
from christo.models.vehicle import Vehicle
from christo.screens.trip_screen import TripScreen
from christo.services.fahrtenbuch import Fahrtenbuch
from tests.conftest import make_trip


class _Probe(App[None]):
    def __init__(self, screen: TripScreen) -> None:
        super().__init__()
        self._screen = screen
        self.ergebnis: list[Any] = []

    def on_mount(self) -> None:
        self.push_screen(self._screen, self.ergebnis.append)


async def _speichern(tmp_path: Path, vehicle: Vehicle, eingaben: dict[str, str]) -> Trip:
    fb = Fahrtenbuch.create(tmp_path / "fb", vehicle)
    try:
        db = fb.database
        set_business_categories(db.get_business_category_names())
        set_informational_categories(db.get_informational_category_names())
        trip_id = db.add_trip(make_trip("2024-05-02", 50, destination="Kunde Nord"))
        vorhanden = db.get_trip_by_id(trip_id)
        assert vorhanden is not None
        screen = TripScreen(db, trip=vorhanden)
        app = _Probe(screen)
        async with app.run_test(size=(160, 60)) as pilot:
            await pilot.pause()
            for feld, wert in eingaben.items():
                screen.query_one(feld, Input).value = wert
            await pilot.pause()
            screen.action_save()
            await pilot.pause()
        assert len(app.ergebnis) == 1
        gespeichert = app.ergebnis[0]
        assert isinstance(gespeichert, Trip)
        return gespeichert
    finally:
        fb.close()


async def test_private_km_on_business_trip_become_private(tmp_path: Path, vehicle: Vehicle) -> None:
    fahrt = await _speichern(tmp_path, vehicle, {"#input-km-business": "0", "#input-km-private": "50"})
    assert fahrt.category == "private"
    assert (fahrt.km_business, fahrt.km_private) == (0, 50)


async def test_business_trip_is_saved_unchanged(tmp_path: Path, vehicle: Vehicle) -> None:
    fahrt = await _speichern(tmp_path, vehicle, {"#input-purpose": "  Abnahme  "})
    assert fahrt.category == "business"
    assert fahrt.purpose == "Abnahme"
    assert fahrt.destination == "Kunde Nord"
