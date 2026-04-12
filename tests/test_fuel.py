"""Tests fuer Tankverbrauch-Pruefungen und Schema-Migrationen.

Deckt ab:
- Migration der fuel_*-Spalten (trips) und Tank-Spalten (vehicle)
- check_fuel_tank_capacity (Tankfuellung vs. Tankkapazitaet)
- check_fuel_consumption_range (Verbrauch zwischen Volltankungen)
"""

from __future__ import annotations

from pathlib import Path

import pytest

from fahrtenbuch_app.models.trip import Trip
from fahrtenbuch_app.models.vehicle import Vehicle
from fahrtenbuch_app.services.database import Database
from fahrtenbuch_app.services.plausibility import (
    CAT_FUEL_CONSUMPTION,
    CAT_FUEL_OVER_TANK,
    FUEL_MIN_INTERVAL_KM,
    FUEL_TOLERANCE,
    SEVERITY_ERROR,
    SEVERITY_WARNING,
    check_fuel_consumption_range,
    check_fuel_tank_capacity,
    run_all_checks,
)

from tests.conftest import make_trip


# ---------------------------------------------------------------------------
# Helfer
# ---------------------------------------------------------------------------


def fuel_trip(
    date: str,
    liters: float,
    *,
    full_tank: bool = True,
    private: bool = False,
) -> Trip:
    """Erzeugt einen Tank-Trip (distance=0, keine km-Aenderung)."""
    return Trip(
        date=date,
        destination="Tanke",
        purpose="Tanken",
        km_start=0,
        km_end=0,
        km_business=0,
        km_private=0,
        category="fuel_private" if private else "fuel",
        fuel_liters=liters,
        fuel_full_tank=full_tank,
    )


def set_fuel_vehicle(
    database: Database,
    *,
    tank_capacity_l: float = 54.0,
    consumption_l_100km: float = 9.0,
) -> None:
    """Aktualisiert das Test-Vehicle mit Tank- und Verbrauchsdaten.

    Deaktiviert gleichzeitig die Winter-Toleranz, damit Verbrauchs-Tests
    deterministisch sind — unabhaengig davon in welchem Monat die Fixture-
    Daten liegen.
    """
    v = database.get_vehicle()
    v.tank_capacity_l = tank_capacity_l
    v.consumption_l_100km = consumption_l_100km
    database.save_vehicle(v)
    database.set_setting("fuel_winter_tolerance", "0")


# ---------------------------------------------------------------------------
# Schema-Migrationen
# ---------------------------------------------------------------------------


class TestFuelSchemaMigration:
    """Die Tank-Spalten muessen idempotent migriert werden."""

    def test_trip_fuel_columns_exist(self, database: Database) -> None:
        conn = database._get_conn()  # type: ignore[reportPrivateUsage]
        cols = {row[1] for row in conn.execute("PRAGMA table_info(trips)").fetchall()}
        assert "fuel_liters" in cols
        assert "fuel_full_tank" in cols

    def test_vehicle_tank_columns_exist(self, database: Database) -> None:
        conn = database._get_conn()  # type: ignore[reportPrivateUsage]
        cols = {row[1] for row in conn.execute("PRAGMA table_info(vehicle)").fetchall()}
        assert "tank_capacity_l" in cols
        assert "consumption_l_100km" in cols

    def test_migration_is_idempotent(self, tmp_path: Path, vehicle: Vehicle) -> None:
        """Wiederholtes Oeffnen darf nicht an ALTER TABLE scheitern."""
        db1 = Database(tmp_path)
        db1.open()
        db1.save_vehicle(vehicle)
        db1.close()

        db2 = Database(tmp_path)
        db2.open()
        try:
            conn = db2._get_conn()  # type: ignore[reportPrivateUsage]
            cols = {row[1] for row in conn.execute("PRAGMA table_info(trips)").fetchall()}
            assert "fuel_liters" in cols
            assert "fuel_full_tank" in cols
        finally:
            db2.close()

    def test_fuel_roundtrip(self, database: Database) -> None:
        """Tank-Trip wird mit Liter und Full-Tank-Flag zurueckgelesen."""
        trip_id = database.add_trip(fuel_trip("2024-01-15", 45.5, full_tank=True))
        stored = database.get_trip_by_id(trip_id)
        assert stored is not None
        assert stored.fuel_liters == pytest.approx(45.5)
        assert stored.fuel_full_tank is True

    def test_non_fuel_trip_has_no_liters(self, database: Database) -> None:
        """Business-Trips speichern 0 l unabhaengig vom Input."""
        t = make_trip("2024-01-10", 100)
        t.fuel_liters = 99.0  # wird ignoriert (Kategorie != fuel)
        t.fuel_full_tank = True
        trip_id = database.add_trip(t)
        stored = database.get_trip_by_id(trip_id)
        assert stored is not None
        assert stored.fuel_liters == 0.0
        assert stored.fuel_full_tank is False


# ---------------------------------------------------------------------------
# check_fuel_tank_capacity
# ---------------------------------------------------------------------------


class TestFuelTankCapacityCheck:
    """Prueft Fundstellen, bei denen die getankte Menge den Tank uebersteigt."""

    def test_within_capacity_no_issue(self, database: Database) -> None:
        set_fuel_vehicle(database, tank_capacity_l=54.0)
        database.add_trip(fuel_trip("2024-01-10", 50.0))
        assert check_fuel_tank_capacity(database) == []

    def test_over_capacity_is_error(self, database: Database) -> None:
        set_fuel_vehicle(database, tank_capacity_l=54.0)
        database.add_trip(fuel_trip("2024-01-10", 60.0))
        issues = check_fuel_tank_capacity(database)
        assert len(issues) == 1
        assert issues[0].severity == SEVERITY_ERROR
        assert issues[0].category == CAT_FUEL_OVER_TANK
        assert issues[0].trip_date == "2024-01-10"

    def test_half_liter_tolerance_ok(self, database: Database) -> None:
        """0.5 L Toleranz fuer Tankwart-Rundung."""
        set_fuel_vehicle(database, tank_capacity_l=54.0)
        database.add_trip(fuel_trip("2024-01-10", 54.4))
        assert check_fuel_tank_capacity(database) == []

    def test_above_tolerance_is_error(self, database: Database) -> None:
        set_fuel_vehicle(database, tank_capacity_l=54.0)
        database.add_trip(fuel_trip("2024-01-10", 54.6))
        issues = check_fuel_tank_capacity(database)
        assert len(issues) == 1
        assert issues[0].severity == SEVERITY_ERROR

    def test_fuel_private_also_checked(self, database: Database) -> None:
        set_fuel_vehicle(database, tank_capacity_l=54.0)
        database.add_trip(fuel_trip("2024-01-10", 70.0, private=True))
        issues = check_fuel_tank_capacity(database)
        assert len(issues) == 1
        assert issues[0].category == CAT_FUEL_OVER_TANK

    def test_tank_not_configured_skipped(self, database: Database) -> None:
        """Ohne gepflegte Tankkapazitaet laeuft der Check stumm durch."""
        # Default-Vehicle hat tank_capacity_l == 0.0
        database.add_trip(fuel_trip("2024-01-10", 200.0))
        assert check_fuel_tank_capacity(database) == []

    def test_zero_liters_skipped(self, database: Database) -> None:
        """Tank-Trip ohne eingetragene Liter wird nicht bewertet."""
        set_fuel_vehicle(database, tank_capacity_l=54.0)
        database.add_trip(fuel_trip("2024-01-10", 0.0))
        assert check_fuel_tank_capacity(database) == []


# ---------------------------------------------------------------------------
# check_fuel_consumption_range
# ---------------------------------------------------------------------------


class TestFuelConsumptionRangeCheck:
    """Prueft den Verbrauchs-Check zwischen zwei Volltankungen."""

    def _build_chain(
        self,
        database: Database,
        *,
        distance_km: int,
        liters_second_tank: float,
        liters_first_tank: float = 45.0,
    ) -> None:
        """Legt Volltank → Business-Strecke → Volltank an.

        Der erste Volltank hat immer 45 L (Referenz), der zweite laesst sich
        per Argument variieren, um verschiedene Verbrauchswerte zu erzeugen.
        """
        database.add_trip(fuel_trip("2024-01-01", liters_first_tank, full_tank=True))
        database.add_trip(make_trip("2024-01-02", distance_km))
        database.add_trip(fuel_trip("2024-01-03", liters_second_tank, full_tank=True))

    def test_consumption_in_range_no_issue(self, database: Database) -> None:
        set_fuel_vehicle(database, consumption_l_100km=9.0)
        # 500 km, 45 L  -> 9.0 l/100km (genau am Ziel)
        self._build_chain(database, distance_km=500, liters_second_tank=45.0)
        assert check_fuel_consumption_range(database) == []

    def test_consumption_within_tolerance_no_issue(self, database: Database) -> None:
        set_fuel_vehicle(database, consumption_l_100km=9.0)
        # 500 km, 50 L -> 10 l/100km, innerhalb 15 % (Obergrenze 10.35)
        self._build_chain(database, distance_km=500, liters_second_tank=50.0)
        assert check_fuel_consumption_range(database) == []

    def test_consumption_too_low_is_warning(self, database: Database) -> None:
        set_fuel_vehicle(database, consumption_l_100km=9.0)
        # 1000 km, 20 L -> 2.0 l/100km (unmoeglich niedrig, km-Luecke)
        self._build_chain(database, distance_km=1000, liters_second_tank=20.0)
        issues = check_fuel_consumption_range(database)
        assert len(issues) == 1
        assert issues[0].severity == SEVERITY_WARNING
        assert issues[0].category == CAT_FUEL_CONSUMPTION

    def test_consumption_too_high_is_error(self, database: Database) -> None:
        set_fuel_vehicle(database, consumption_l_100km=9.0)
        # 100 km, 45 L -> 45 l/100km (> 2x target = 18) -> Error
        self._build_chain(database, distance_km=100, liters_second_tank=45.0)
        issues = check_fuel_consumption_range(database)
        assert len(issues) == 1
        assert issues[0].severity == SEVERITY_ERROR
        assert issues[0].category == CAT_FUEL_CONSUMPTION

    def test_slightly_over_tolerance_is_warning(self, database: Database) -> None:
        """Knapp ausserhalb der 15 %-Toleranz ist Warning, nicht Error."""
        set_fuel_vehicle(database, consumption_l_100km=9.0)
        # 500 km, 55 L -> 11.0 l/100km (> 10.35, aber < 18)
        self._build_chain(database, distance_km=500, liters_second_tank=55.0)
        issues = check_fuel_consumption_range(database)
        assert len(issues) == 1
        assert issues[0].severity == SEVERITY_WARNING

    def test_winter_tolerance_suppresses_small_deviation(
        self, database: Database
    ) -> None:
        """In Winter-Monaten mit aktivem Setting greift erweiterte Toleranz."""
        set_fuel_vehicle(database, consumption_l_100km=9.0)
        database.set_setting("fuel_winter_tolerance", "1")
        # 500 km, 55 L -> 11.0 l/100km, 22 % ueber 9.0 -> normal Warning,
        # mit Winter-Toleranz (20 + 15 = 35 %) aber clean.
        self._build_chain(database, distance_km=500, liters_second_tank=55.0)
        assert check_fuel_consumption_range(database) == []

    def test_winter_tolerance_still_flags_large_deviation(
        self, database: Database
    ) -> None:
        """Grobe Ausreisser bleiben auch im Winter erkannt."""
        set_fuel_vehicle(database, consumption_l_100km=9.0)
        database.set_setting("fuel_winter_tolerance", "1")
        # 500 km, 80 L -> 16.0 l/100km, 78 % ueber Ziel -> immer noch Warning
        self._build_chain(database, distance_km=500, liters_second_tank=80.0)
        issues = check_fuel_consumption_range(database)
        assert len(issues) == 1

    def test_short_interval_skipped(self, database: Database) -> None:
        """Intervalle < FUEL_MIN_INTERVAL_KM werden uebersprungen."""
        set_fuel_vehicle(database, consumption_l_100km=9.0)
        assert FUEL_MIN_INTERVAL_KM == 50
        # 30 km (< 50) — Verbrauch waere 150 l/100km, wird aber ignoriert
        self._build_chain(database, distance_km=30, liters_second_tank=45.0)
        assert check_fuel_consumption_range(database) == []

    def test_partial_refill_included_in_consumption(self, database: Database) -> None:
        """Teilbetankungen werden im Verbrauch mitgezaehlt, spannen aber kein
        eigenes Intervall auf (nur full_tank=True definiert Fenstergrenzen)."""
        set_fuel_vehicle(database, consumption_l_100km=9.0)
        database.add_trip(fuel_trip("2024-01-01", 45.0, full_tank=True))
        database.add_trip(make_trip("2024-01-02", 300))
        # Zwischendrin Teil-Tankung — wird mitgezaehlt
        database.add_trip(fuel_trip("2024-01-03", 5.0, full_tank=False))
        database.add_trip(make_trip("2024-01-04", 200))
        database.add_trip(fuel_trip("2024-01-05", 40.0, full_tank=True))
        # 500 km, 40 + 5 = 45 L -> 9.0 l/100km (prev=Tag 01, curr=Tag 05)
        assert check_fuel_consumption_range(database) == []

    def test_single_full_tank_no_issue(self, database: Database) -> None:
        """Mit nur einem Volltank kann kein Verbrauch berechnet werden."""
        set_fuel_vehicle(database, consumption_l_100km=9.0)
        database.add_trip(fuel_trip("2024-01-01", 45.0, full_tank=True))
        database.add_trip(make_trip("2024-01-02", 500))
        assert check_fuel_consumption_range(database) == []

    def test_consumption_not_configured_skipped(self, database: Database) -> None:
        """Ohne gepflegten Soll-Verbrauch laeuft der Check stumm durch."""
        # Default-Vehicle hat consumption_l_100km == 0.0
        database.add_trip(fuel_trip("2024-01-01", 45.0, full_tank=True))
        database.add_trip(make_trip("2024-01-02", 100))
        database.add_trip(fuel_trip("2024-01-03", 45.0, full_tank=True))
        assert check_fuel_consumption_range(database) == []

    def test_tolerance_constant_is_20_percent(self) -> None:
        """Dokumentiert die feste Toleranz als Teil des Contracts."""
        assert FUEL_TOLERANCE == 0.20


# ---------------------------------------------------------------------------
# run_all_checks integriert Fuel-Checks
# ---------------------------------------------------------------------------


class TestRunAllChecksFuel:
    """Smoke-Test: Fuel-Checks sind in run_all_checks verdrahtet."""

    def test_fuel_issues_reach_report(self, database: Database) -> None:
        set_fuel_vehicle(database, tank_capacity_l=54.0, consumption_l_100km=9.0)
        # Ueber-Tank
        database.add_trip(fuel_trip("2024-01-10", 60.0))
        report = run_all_checks(database)
        categories = {i.category for i in report.issues}
        assert CAT_FUEL_OVER_TANK in categories
