"""Tests fuer fahrtenbuch_app.services.plausibility.

Die Plausibilitaets-Checks werden sowohl von dieser Test-Suite als auch
spaeter vom 'p'-Button in der UI verwendet — beide nutzen denselben Code,
sodass Bugs in beiden Pfaden gleichzeitig sichtbar werden.
"""

from __future__ import annotations

from datetime import date

from fahrtenbuch_app.models.trip import Trip
from fahrtenbuch_app.models.vehicle import Vehicle
from fahrtenbuch_app.services.database import Database
from fahrtenbuch_app.services.plausibility import (
    CAT_BLACKLIST_BUSINESS,
    CAT_CHAIN_BACKWARD,
    CAT_CHAIN_BREAK,
    CAT_DISTANCE_MISMATCH,
    CAT_EMPTY_TRIP,
    CAT_HOLIDAY_BUSINESS,
    CAT_NEGATIVE_DISTANCE,
    CAT_OVER_LIMIT,
    CAT_WEEKEND_BUSINESS,
    SEVERITY_ERROR,
    SEVERITY_WARNING,
    check_blacklist_business,
    check_chain_ascending,
    check_distance_matches_columns,
    check_empty_trips,
    check_holiday_business,
    check_vehicle_end_limit,
    check_weekend_business,
    run_all_checks,
)

from tests.conftest import make_trip


# ---------------------------------------------------------------------------
# Helfer: direkter SQL-Insert ohne Cascade-Logik
# ---------------------------------------------------------------------------


def raw_insert_trip(
    database: Database,
    *,
    date_iso: str,
    km_start: int,
    km_end: int,
    km_business: int = 0,
    km_private: int = 0,
    category: str = "business",
    purpose: str = "Test",
) -> int:
    """Schiebt einen Trip ohne add_trip-Cascade direkt in die DB.

    Wird gebraucht, um KAPUTTE Daten zu erzeugen — die Cascade-Logik
    wuerde sonst alles automatisch glattziehen.
    """
    conn = database._get_conn()  # type: ignore[reportPrivateUsage]
    cursor = conn.execute(
        """
        INSERT INTO trips (date, time_from, time_to, destination, purpose,
            km_start, km_end, km_business, km_private, category, round_trip)
        VALUES (?, '', '', '', ?, ?, ?, ?, ?, ?, 0)
        """,
        (date_iso, purpose, km_start, km_end, km_business, km_private, category),
    )
    conn.commit()
    return cursor.lastrowid or 0


# ---------------------------------------------------------------------------
# check_chain_ascending
# ---------------------------------------------------------------------------


class TestCheckChainAscending:
    def test_intact_chain_no_issues(self, database: Database) -> None:
        database.add_trip(make_trip("2024-03-01", 100))
        database.add_trip(make_trip("2024-03-02", 50))
        database.add_trip(make_trip("2024-03-03", 80))
        assert check_chain_ascending(database) == []

    def test_empty_db_no_issues(self, database: Database) -> None:
        assert check_chain_ascending(database) == []

    def test_first_trip_below_vehicle_start_km(
        self, database: Database
    ) -> None:
        raw_insert_trip(
            database,
            date_iso="2024-03-01",
            km_start=5000,  # unter vehicle.start_km=10000
            km_end=5050,
            km_business=50,
        )
        issues = check_chain_ascending(database)
        assert len(issues) == 1
        assert issues[0].severity == SEVERITY_ERROR
        assert "Anfangsstand" in issues[0].message

    def test_backward_jump_is_error(self, database: Database) -> None:
        raw_insert_trip(
            database, date_iso="2024-03-01",
            km_start=10000, km_end=10100, km_business=100,
        )
        # Naechster Trip springt zurueck
        raw_insert_trip(
            database, date_iso="2024-03-02",
            km_start=10050, km_end=10120, km_business=70,
        )
        issues = check_chain_ascending(database)
        backward = [i for i in issues if i.category == CAT_CHAIN_BACKWARD]
        assert len(backward) == 1
        assert backward[0].severity == SEVERITY_ERROR

    def test_forward_gap_is_warning(self, database: Database) -> None:
        raw_insert_trip(
            database, date_iso="2024-03-01",
            km_start=10000, km_end=10100, km_business=100,
        )
        # Luecke von 50 km
        raw_insert_trip(
            database, date_iso="2024-03-02",
            km_start=10150, km_end=10200, km_business=50,
        )
        issues = check_chain_ascending(database)
        breaks = [i for i in issues if i.category == CAT_CHAIN_BREAK]
        assert len(breaks) == 1
        assert breaks[0].severity == SEVERITY_WARNING

    def test_negative_distance_is_error(self, database: Database) -> None:
        raw_insert_trip(
            database, date_iso="2024-03-01",
            km_start=10100, km_end=10050, km_business=0,
        )
        issues = check_chain_ascending(database)
        neg = [i for i in issues if i.category == CAT_NEGATIVE_DISTANCE]
        assert len(neg) == 1
        assert neg[0].severity == SEVERITY_ERROR


# ---------------------------------------------------------------------------
# check_distance_matches_columns
# ---------------------------------------------------------------------------


class TestCheckDistanceMatchesColumns:
    def test_matching_distance_no_issue(self, database: Database) -> None:
        database.add_trip(make_trip("2024-03-01", 100))
        assert check_distance_matches_columns(database) == []

    def test_mismatch_is_warning(self, database: Database) -> None:
        # Reproduktion des 103/104-Bugs:
        # km_end-km_start=0 km, aber km_business=260 km
        raw_insert_trip(
            database, date_iso="2024-03-01",
            km_start=10000, km_end=10000, km_business=260, km_private=0,
        )
        issues = check_distance_matches_columns(database)
        assert len(issues) == 1
        assert issues[0].category == CAT_DISTANCE_MISMATCH
        assert issues[0].severity == SEVERITY_WARNING

    def test_zero_zero_is_consistent(self, database: Database) -> None:
        raw_insert_trip(
            database, date_iso="2024-03-01",
            km_start=10000, km_end=10000, km_business=0, km_private=0,
        )
        assert check_distance_matches_columns(database) == []


# ---------------------------------------------------------------------------
# check_vehicle_end_limit
# ---------------------------------------------------------------------------


class TestCheckVehicleEndLimit:
    def test_no_limit_set_no_issue(self, database: Database) -> None:
        v = database.get_vehicle()
        v.end_km = 0
        database.save_vehicle(v)
        database.add_trip(make_trip("2024-03-01", 50000))
        assert check_vehicle_end_limit(database) == []

    def test_within_limit_no_issue(self, database: Database) -> None:
        database.add_trip(make_trip("2024-03-01", 1000))
        assert check_vehicle_end_limit(database) == []

    def test_over_limit_is_error(
        self, database: Database, vehicle: Vehicle
    ) -> None:
        vehicle.end_km = 10100
        database.save_vehicle(vehicle)
        # add_trip lehnt nicht mehr ab — Plausi-Check muss melden
        database.add_trip(make_trip("2024-03-01", 200))
        issues = check_vehicle_end_limit(database)
        assert len(issues) == 1
        assert issues[0].category == CAT_OVER_LIMIT
        assert issues[0].severity == SEVERITY_ERROR


# ---------------------------------------------------------------------------
# check_empty_trips
# ---------------------------------------------------------------------------


class TestCheckEmptyTrips:
    def test_normal_trip_no_issue(self, database: Database) -> None:
        database.add_trip(make_trip("2024-03-01", 100))
        assert check_empty_trips(database) == []

    def test_zero_distance_zero_columns_no_issue(
        self, database: Database
    ) -> None:
        raw_insert_trip(
            database, date_iso="2024-03-01",
            km_start=10000, km_end=10000, km_business=0, km_private=0,
        )
        assert check_empty_trips(database) == []

    def test_zero_distance_with_columns_is_error(
        self, database: Database
    ) -> None:
        # Der echte 103/104-Bug:
        raw_insert_trip(
            database, date_iso="2024-11-13",
            km_start=16070, km_end=16070, km_business=260, km_private=0,
        )
        issues = check_empty_trips(database)
        assert len(issues) == 1
        assert issues[0].category == CAT_EMPTY_TRIP
        assert issues[0].severity == SEVERITY_ERROR
        assert issues[0].year == 2024
        assert issues[0].month == 11


# ---------------------------------------------------------------------------
# check_weekend_business
# ---------------------------------------------------------------------------


class TestCheckWeekendBusiness:
    def test_business_on_weekday_no_issue(
        self, database: Database
    ) -> None:
        # 2024-03-04 ist ein Montag
        database.add_trip(make_trip("2024-03-04", 50))
        assert check_weekend_business(database) == []

    def test_business_on_saturday_is_warning(
        self, database: Database
    ) -> None:
        # 2024-03-02 ist ein Samstag
        database.add_trip(make_trip("2024-03-02", 50))
        issues = check_weekend_business(database)
        assert len(issues) == 1
        assert issues[0].category == CAT_WEEKEND_BUSINESS

    def test_fuel_on_sunday_is_ok(self, database: Database) -> None:
        """Tanken am Sonntag ist nicht schlimm — explizit ausgeschlossen."""
        # 2024-03-03 ist ein Sonntag
        trip = Trip(
            date="2024-03-03",
            km_start=0, km_end=20, km_business=20,
            category="fuel", purpose="Tanken",
        )
        database.add_trip(trip)
        assert check_weekend_business(database) == []


# ---------------------------------------------------------------------------
# check_holiday_business
# ---------------------------------------------------------------------------


class TestCheckHolidayBusiness:
    def test_no_holiday_no_issue(self, database: Database) -> None:
        database.add_trip(make_trip("2024-03-04", 50))
        assert check_holiday_business(database, {}) == []

    def test_business_on_holiday_is_warning(
        self, database: Database
    ) -> None:
        # 2024-12-25 = 1. Weihnachtstag
        database.add_trip(make_trip("2024-12-25", 50))
        holidays = {date(2024, 12, 25): "1. Weihnachtstag"}
        issues = check_holiday_business(database, holidays)
        assert len(issues) == 1
        assert issues[0].category == CAT_HOLIDAY_BUSINESS
        assert "Weihnachtstag" in issues[0].message

    def test_fuel_on_holiday_is_ok(self, database: Database) -> None:
        trip = Trip(
            date="2024-12-25",
            km_start=0, km_end=20, km_business=20,
            category="fuel", purpose="Tanken",
        )
        database.add_trip(trip)
        holidays = {date(2024, 12, 25): "1. Weihnachtstag"}
        assert check_holiday_business(database, holidays) == []


# ---------------------------------------------------------------------------
# check_blacklist_business
# ---------------------------------------------------------------------------


class TestCheckBlacklistBusiness:
    def test_no_blacklist_no_issue(self, database: Database) -> None:
        database.add_trip(make_trip("2024-03-04", 50))
        assert check_blacklist_business(database) == []

    def test_business_on_blacklist_is_error(
        self, database: Database
    ) -> None:
        database.add_blacklist_entry("2024-03-04", "Krank")
        database.add_trip(make_trip("2024-03-04", 50))
        issues = check_blacklist_business(database)
        assert len(issues) == 1
        assert issues[0].category == CAT_BLACKLIST_BUSINESS
        assert issues[0].severity == SEVERITY_ERROR
        assert "Krank" in issues[0].message

    def test_private_on_blacklist_is_ok(self, database: Database) -> None:
        """Private Fahrt am gesperrten Tag ist erlaubt — der Tag ist nur
        fuer geschaeftliche Fahrten gesperrt."""
        database.add_blacklist_entry("2024-03-04", "Urlaub")
        database.add_trip(make_trip("2024-03-04", 50, business=False))
        assert check_blacklist_business(database) == []


# ---------------------------------------------------------------------------
# run_all_checks (Orchestrator)
# ---------------------------------------------------------------------------


class TestRunAllChecks:
    def test_clean_data_no_issues(self, database: Database) -> None:
        database.add_trip(make_trip("2024-03-04", 100))  # Mo
        database.add_trip(make_trip("2024-03-05", 50))   # Di
        report = run_all_checks(database)
        assert not report.has_issues
        assert report.error_count == 0

    def test_aggregates_multiple_check_results(
        self, database: Database, vehicle: Vehicle
    ) -> None:
        # Mehrere Probleme erzeugen
        # 1. Wochenend-Business
        database.add_trip(make_trip("2024-03-02", 50))  # Sa
        # 2. Limit-Verletzung
        vehicle.end_km = 10100
        database.save_vehicle(vehicle)
        # 3. Empty-Trip-Bug per direktem Insert
        raw_insert_trip(
            database, date_iso="2024-03-15",
            km_start=10100, km_end=10100, km_business=99,
        )
        report = run_all_checks(database)
        assert report.has_issues
        cats = {i.category for i in report.issues}
        assert CAT_WEEKEND_BUSINESS in cats
        assert CAT_OVER_LIMIT in cats or CAT_EMPTY_TRIP in cats

    def test_holidays_only_checked_when_provided(
        self, database: Database
    ) -> None:
        database.add_trip(make_trip("2024-12-25", 50))
        report_no = run_all_checks(database)
        cats_no = {i.category for i in report_no.issues}
        assert CAT_HOLIDAY_BUSINESS not in cats_no

        report_yes = run_all_checks(
            database, holidays_by_date={date(2024, 12, 25): "Weihnachten"}
        )
        cats_yes = {i.category for i in report_yes.issues}
        assert CAT_HOLIDAY_BUSINESS in cats_yes

    def test_grouping_by_month(self, database: Database) -> None:
        # Jeweils Wochenend-Fahrt in zwei verschiedenen Monaten
        database.add_trip(make_trip("2024-03-02", 50))   # Sa
        database.add_trip(make_trip("2024-04-06", 50))   # Sa
        report = run_all_checks(database)
        groups = report.by_month()
        assert (2024, 3) in groups
        assert (2024, 4) in groups
