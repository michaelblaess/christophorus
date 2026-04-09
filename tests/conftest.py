"""Shared Fixtures fuer alle Tests.

Stellt eine frische, in einem temporaeren Verzeichnis liegende Database
mit konfiguriertem Vehicle bereit. Ein paar Helper machen das Anlegen von
Testtrips kompakt.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from fahrtenbuch_app.models.trip import Trip
from fahrtenbuch_app.models.vehicle import Vehicle
from fahrtenbuch_app.services.database import Database


@pytest.fixture
def vehicle() -> Vehicle:
    """Standard-Test-Fahrzeug: 12 Monate, 1500 km/Monat, 10000-30000 km."""
    return Vehicle(
        name="Testwagen",
        plate="B-TT 1",
        contract_number="X",
        lease_km_per_month=1500,
        start_km=10000,
        end_km=30000,
        start_date="2024-01-01",
        end_date="2024-12-31",
        lease_months=12,
    )


@pytest.fixture
def database(tmp_path: Path, vehicle: Vehicle) -> Iterator[Database]:
    """Frisch geoeffnete Database mit konfiguriertem Vehicle."""
    db = Database(tmp_path)
    db.open()
    db.save_vehicle(vehicle)
    try:
        yield db
    finally:
        db.close()


def make_trip(
    date: str,
    distance: int,
    *,
    business: bool = True,
    purpose: str = "Test",
    destination: str = "Berlin",
    km_business: int | None = None,
    km_private: int | None = None,
) -> Trip:
    """Hilfsfunktion: legt einen Trip mit gewuenschter Distanz an.

    km_start/km_end werden bewusst auf 0/distance gesetzt — die Database
    bestimmt den echten km_start beim Insert aus dem Vorgaenger.
    """
    if business:
        kb = km_business if km_business is not None else distance
        kp = km_private if km_private is not None else 0
        category = "business"
    else:
        kb = km_business if km_business is not None else 0
        kp = km_private if km_private is not None else distance
        category = "private"
    return Trip(
        date=date,
        destination=destination,
        purpose=purpose,
        km_start=0,
        km_end=distance,
        km_business=kb,
        km_private=kp,
        category=category,
    )
