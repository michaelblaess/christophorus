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
    BUSINESS_QUOTA_MIN,
    CAT_BLACKLIST_BUSINESS,
    CAT_BUSINESS_QUOTA_LOW,
    CAT_CHAIN_BACKWARD,
    CAT_CHAIN_BREAK,
    CAT_DISTANCE_MISMATCH,
    CAT_EMPTY_TRIP,
    CAT_FUEL_RANGE_EXCEEDED,
    CAT_GHOST_BUSINESS_TRIP,
    CAT_HOLIDAY_BUSINESS,
    CAT_NEGATIVE_DISTANCE,
    CAT_OVER_LIMIT,
    CAT_END_MISMATCH,
    CAT_TIME_INCOMPLETE,
    CAT_TIME_OVERLAP,
    CAT_TIME_REVERSED,
    CAT_WEEKEND_BUSINESS,
    CAT_WORKTIME_RATIO,
    GHOST_TRIP_MIN_KM,
    GHOST_TRIP_WINDOW_DAYS,
    SEVERITY_ERROR,
    SEVERITY_INFO,
    SEVERITY_WARNING,
    WORKTIME_RATIO_FACTOR,
    check_blacklist_business,
    check_business_quota,
    check_chain_ascending,
    check_distance_matches_columns,
    check_empty_trips,
    check_time_overlap,
    check_time_range_valid,
    check_fuel_range_exceeded,
    check_ghost_business_trips,
    check_holiday_business,
    check_vehicle_end_limit,
    check_vehicle_end_reached,
    check_weekend_business,
    check_worktime_trip_ratio,
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
        # Ein Pro-Trip-Fehler + eine Gesamt-Zusammenfassung
        assert len(issues) == 2
        assert all(i.category == CAT_OVER_LIMIT for i in issues)
        assert all(i.severity == SEVERITY_ERROR for i in issues)
        assert "100 km" in issues[-1].message
        assert "zu viel" in issues[-1].message


# ---------------------------------------------------------------------------
# check_vehicle_end_reached
# ---------------------------------------------------------------------------


class TestCheckVehicleEndReached:
    def test_no_end_set_no_issue(self, database: Database) -> None:
        v = database.get_vehicle()
        v.end_km = 0
        database.save_vehicle(v)
        database.add_trip(make_trip("2024-03-01", 100))
        assert check_vehicle_end_reached(database) == []

    def test_exact_match_no_issue(
        self, database: Database, vehicle: Vehicle
    ) -> None:
        vehicle.end_km = 10150
        database.save_vehicle(vehicle)
        database.add_trip(make_trip("2024-03-01", 100))
        database.add_trip(make_trip("2024-03-02", 50))
        assert check_vehicle_end_reached(database) == []

    def test_gap_reports_warning(
        self, database: Database, vehicle: Vehicle
    ) -> None:
        vehicle.end_km = 10500
        database.save_vehicle(vehicle)
        database.add_trip(make_trip("2024-03-01", 100))  # endet bei 10100
        issues = check_vehicle_end_reached(database)
        assert len(issues) == 1
        assert issues[0].category == CAT_END_MISMATCH
        assert "400 km" in issues[0].message

    def test_over_end_no_issue_here(
        self, database: Database, vehicle: Vehicle
    ) -> None:
        # Ueberschreitung meldet check_vehicle_end_limit, nicht dieser Check.
        vehicle.end_km = 10050
        database.save_vehicle(vehicle)
        database.add_trip(make_trip("2024-03-01", 100))
        assert check_vehicle_end_reached(database) == []


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
# check_time_range_valid
# ---------------------------------------------------------------------------


class TestCheckTimeRangeValid:
    def test_valid_time_range_no_issue(self, database: Database) -> None:
        trip = make_trip("2024-03-01", 100)
        trip.time_from = "08:00"
        trip.time_to = "09:30"
        database.add_trip(trip)
        assert check_time_range_valid(database) == []

    def test_equal_time_no_issue(self, database: Database) -> None:
        trip = make_trip("2024-03-01", 100)
        trip.time_from = "10:00"
        trip.time_to = "10:00"
        database.add_trip(trip)
        assert check_time_range_valid(database) == []

    def test_empty_times_no_issue(self, database: Database) -> None:
        database.add_trip(make_trip("2024-03-01", 100))
        assert check_time_range_valid(database) == []

    def test_reversed_time_is_warning(self, database: Database) -> None:
        # Der echte Trip #20 Bug: 15:45 - 15:30
        trip = make_trip("2024-02-28", 50)
        trip.time_from = "15:45"
        trip.time_to = "15:30"
        database.add_trip(trip)
        issues = check_time_range_valid(database)
        assert len(issues) == 1
        assert issues[0].category == CAT_TIME_REVERSED
        assert issues[0].severity == SEVERITY_WARNING
        assert issues[0].year == 2024
        assert issues[0].month == 2
        assert "15:45" in issues[0].message
        assert "15:30" in issues[0].message

    def test_invalid_time_string_no_issue(self, database: Database) -> None:
        trip = make_trip("2024-03-01", 100)
        trip.time_from = "kaputt"
        trip.time_to = "08:00"
        database.add_trip(trip)
        assert check_time_range_valid(database) == []

    def test_start_without_end_is_warning(self, database: Database) -> None:
        # Der echte Trip #34 Bug: Startzeit ohne Endzeit
        trip = make_trip("2024-03-01", 50)
        trip.time_from = "08:00"
        trip.time_to = ""
        database.add_trip(trip)
        issues = check_time_range_valid(database)
        assert len(issues) == 1
        assert issues[0].category == CAT_TIME_INCOMPLETE
        assert issues[0].severity == SEVERITY_WARNING
        assert "08:00" in issues[0].message
        assert "ohne Endzeit" in issues[0].message

    def test_end_without_start_is_warning(self, database: Database) -> None:
        trip = make_trip("2024-03-01", 50)
        trip.time_from = ""
        trip.time_to = "09:30"
        database.add_trip(trip)
        issues = check_time_range_valid(database)
        assert len(issues) == 1
        assert issues[0].category == CAT_TIME_INCOMPLETE
        assert "09:30" in issues[0].message
        assert "ohne Startzeit" in issues[0].message


# ---------------------------------------------------------------------------
# check_time_overlap
# ---------------------------------------------------------------------------


class TestCheckTimeOverlap:
    def test_non_overlapping_no_issue(self, database: Database) -> None:
        t1 = make_trip("2024-03-01", 50)
        t1.time_from = "08:00"
        t1.time_to = "10:00"
        database.add_trip(t1)
        t2 = make_trip("2024-03-01", 50)
        t2.time_from = "10:00"
        t2.time_to = "12:00"
        database.add_trip(t2)
        assert check_time_overlap(database) == []

    def test_different_days_no_issue(self, database: Database) -> None:
        t1 = make_trip("2024-03-01", 50)
        t1.time_from = "16:00"
        t1.time_to = "19:00"
        database.add_trip(t1)
        t2 = make_trip("2024-03-02", 50)
        t2.time_from = "18:00"
        t2.time_to = "21:00"
        database.add_trip(t2)
        assert check_time_overlap(database) == []

    def test_overlap_same_day_is_error(self, database: Database) -> None:
        # Der echte Bug: ID 136 16:00-19:00, ID 127 18:00-21:00 gleicher Tag
        t1 = make_trip("2024-03-01", 50)
        t1.time_from = "16:00"
        t1.time_to = "19:00"
        database.add_trip(t1)
        t2 = make_trip("2024-03-01", 50)
        t2.time_from = "18:00"
        t2.time_to = "21:00"
        database.add_trip(t2)
        issues = check_time_overlap(database)
        assert len(issues) == 1
        assert issues[0].category == CAT_TIME_OVERLAP
        assert issues[0].severity == SEVERITY_ERROR
        # Gemeldet wird am spaeter startenden Trip
        assert issues[0].trip_id is not None
        assert "18:00" in issues[0].message
        assert "19:00" in issues[0].message

    def test_full_containment_is_error(self, database: Database) -> None:
        # Ein Trip komplett in einem anderen enthalten
        t1 = make_trip("2024-03-01", 50)
        t1.time_from = "08:00"
        t1.time_to = "18:00"
        database.add_trip(t1)
        t2 = make_trip("2024-03-01", 50)
        t2.time_from = "10:00"
        t2.time_to = "12:00"
        database.add_trip(t2)
        issues = check_time_overlap(database)
        assert len(issues) == 1
        assert issues[0].category == CAT_TIME_OVERLAP

    def test_touching_boundary_no_issue(self, database: Database) -> None:
        # Trip A endet 10:00, Trip B startet 10:00 — das ist erlaubt
        t1 = make_trip("2024-03-01", 50)
        t1.time_from = "08:00"
        t1.time_to = "10:00"
        database.add_trip(t1)
        t2 = make_trip("2024-03-01", 50)
        t2.time_from = "10:00"
        t2.time_to = "12:00"
        database.add_trip(t2)
        assert check_time_overlap(database) == []

    def test_missing_times_skipped(self, database: Database) -> None:
        # Ein Trip ohne Zeiten wird uebersprungen — Overlap mit dem anderen
        # kann nicht festgestellt werden.
        t1 = make_trip("2024-03-01", 50)
        database.add_trip(t1)
        t2 = make_trip("2024-03-01", 50)
        t2.time_from = "10:00"
        t2.time_to = "12:00"
        database.add_trip(t2)
        assert check_time_overlap(database) == []


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
    def test_clean_data_no_issues(self, database: Database, vehicle: Vehicle) -> None:
        # Endkm auf 0 setzen, sonst meldet check_vehicle_end_reached eine
        # Luecke (Fixture hat end_km=30000).
        vehicle.end_km = 0
        database.save_vehicle(vehicle)
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


# ---------------------------------------------------------------------------
# check_worktime_trip_ratio
# ---------------------------------------------------------------------------


def _add_business_trips_in_month(
    database: Database, year: int, month: int, count: int
) -> None:
    """Legt count Business-Fahrten im angegebenen Monat an (Wochentage)."""
    added = 0
    day = 1
    while added < count and day <= 28:
        d = date(year, month, day)
        if d.weekday() < 5:
            database.add_trip(make_trip(d.strftime("%Y-%m-%d"), 30))
            added += 1
        day += 1


class TestCheckWorktimeTripRatio:
    def test_no_worktimes_no_issues(self, database: Database) -> None:
        """Ohne gepflegte Arbeitszeit kein Vergleich moeglich."""
        _add_business_trips_in_month(database, 2024, 9, 10)
        assert check_worktime_trip_ratio(database) == []

    def test_single_month_worktime_no_baseline(
        self, database: Database
    ) -> None:
        """Ein einzelner Monat mit Arbeitszeit reicht nicht als Baseline."""
        _add_business_trips_in_month(database, 2024, 9, 20)
        database.save_worktime(2024, 9, 168.0)
        assert check_worktime_trip_ratio(database) == []

    def test_proportional_trips_no_issue(self, database: Database) -> None:
        """Wenn Fahrten proportional zu Arbeitszeit sind, keine Warnung."""
        # September: 160h, 20 Fahrten -> 0.125/h
        # Oktober:   80h,  10 Fahrten -> 0.125/h (gleiche Rate)
        _add_business_trips_in_month(database, 2024, 9, 20)
        _add_business_trips_in_month(database, 2024, 10, 10)
        database.save_worktime(2024, 9, 160.0)
        database.save_worktime(2024, 10, 80.0)
        issues = check_worktime_trip_ratio(database)
        assert [i for i in issues if i.category == CAT_WORKTIME_RATIO] == []

    def test_vacation_month_flagged(self, database: Database) -> None:
        """Urlaubsmonat mit wenig Arbeitszeit aber vielen Fahrten warnt.

        User-Szenario: August 98.5h statt September 168.25h, gleich viele
        Fahrten — das ist der klassische Urlaub-mit-Fehlbuchung.
        """
        _add_business_trips_in_month(database, 2024, 8, 18)
        _add_business_trips_in_month(database, 2024, 9, 18)
        database.save_worktime(2024, 8, 98.5)
        database.save_worktime(2024, 9, 168.25)
        issues = check_worktime_trip_ratio(database)
        worktime = [i for i in issues if i.category == CAT_WORKTIME_RATIO]
        # Nur August ueberschreitet die Rate — September liegt unter
        assert len(worktime) == 1
        assert worktime[0].severity == SEVERITY_WARNING
        assert worktime[0].year == 2024
        assert worktime[0].month == 8

    def test_threshold_factor(self, database: Database) -> None:
        """Grenzfall: genau am Faktor loest keine Warnung aus."""
        # Drei Monate mit gleichen 100h. Monat 1 hat mehr Fahrten.
        _add_business_trips_in_month(database, 2024, 1, 15)
        _add_business_trips_in_month(database, 2024, 2, 10)
        _add_business_trips_in_month(database, 2024, 3, 10)
        database.save_worktime(2024, 1, 100.0)
        database.save_worktime(2024, 2, 100.0)
        database.save_worktime(2024, 3, 100.0)
        # Durchschnitt = 35/300 = 0.1167/h, expected Jan = 11.67
        # Jan actual = 15, ratio zu expected = 15/11.67 = 1.286 < 1.3
        assert WORKTIME_RATIO_FACTOR == 1.3
        issues = check_worktime_trip_ratio(database)
        worktime = [i for i in issues if i.category == CAT_WORKTIME_RATIO]
        assert worktime == []

    def test_skip_months_without_worktime(self, database: Database) -> None:
        """Monate ohne Arbeitszeit werden komplett uebersprungen."""
        _add_business_trips_in_month(database, 2024, 1, 5)
        _add_business_trips_in_month(database, 2024, 2, 5)
        _add_business_trips_in_month(database, 2024, 3, 50)  # kein worktime
        database.save_worktime(2024, 1, 160.0)
        database.save_worktime(2024, 2, 160.0)
        issues = check_worktime_trip_ratio(database)
        # Maerz darf keinen Befund erzeugen, da keine Arbeitszeit gepflegt
        march = [i for i in issues if i.month == 3]
        assert march == []


# ---------------------------------------------------------------------------
# check_business_quota
# ---------------------------------------------------------------------------


class TestCheckBusinessQuota:
    def test_empty_db_no_issues(self, database: Database) -> None:
        assert check_business_quota(database) == []

    def test_all_business_no_issue(self, database: Database) -> None:
        database.add_trip(make_trip("2024-03-01", 100))
        database.add_trip(make_trip("2024-04-01", 200))
        assert check_business_quota(database) == []

    def test_exactly_fifty_percent_no_issue(self, database: Database) -> None:
        """50% ist der Grenzwert — genau am Limit kein Befund."""
        database.add_trip(make_trip("2024-03-01", 100, business=True))
        database.add_trip(make_trip("2024-04-01", 100, business=False))
        assert BUSINESS_QUOTA_MIN == 0.50
        issues = check_business_quota(database)
        assert [i for i in issues if i.category == CAT_BUSINESS_QUOTA_LOW] == []

    def test_below_fifty_percent_warns(self, database: Database) -> None:
        """Weniger als 50% Business loest Warnung aus."""
        database.add_trip(make_trip("2024-03-01", 40, business=True))
        database.add_trip(make_trip("2024-04-01", 60, business=False))
        issues = check_business_quota(database)
        quota = [i for i in issues if i.category == CAT_BUSINESS_QUOTA_LOW]
        assert len(quota) == 1
        assert quota[0].severity == SEVERITY_WARNING
        assert quota[0].year == 2024
        assert "40.0 %" in quota[0].message

    def test_per_year_independent(self, database: Database) -> None:
        """Jahre werden unabhaengig beurteilt."""
        # 2024 ok (80% business)
        database.add_trip(make_trip("2024-03-01", 80, business=True))
        database.add_trip(make_trip("2024-04-01", 20, business=False))
        # 2025 nicht ok (30% business) — muss warnen
        database.add_trip(make_trip("2025-03-01", 30, business=True))
        database.add_trip(make_trip("2025-04-01", 70, business=False))
        issues = check_business_quota(database)
        quota = [i for i in issues if i.category == CAT_BUSINESS_QUOTA_LOW]
        years = [i.year for i in quota]
        assert years == [2025]

    def test_run_all_checks_includes_new_checks(
        self, database: Database
    ) -> None:
        """Beide neuen Checks laufen ueber run_all_checks."""
        # Setup fuer beide Checks: niedrige Quote + Urlaubsmonat
        database.add_trip(make_trip("2024-03-01", 40, business=True))
        database.add_trip(make_trip("2024-04-01", 60, business=False))
        report = run_all_checks(database)
        cats = {i.category for i in report.issues}
        assert CAT_BUSINESS_QUOTA_LOW in cats


# ---------------------------------------------------------------------------
# check_fuel_range_exceeded
# ---------------------------------------------------------------------------


def _vehicle_with_tank(
    database: Database, tank_l: float = 54.0, consumption: float = 7.5
) -> None:
    """Setzt Tank- und Verbrauchswerte am Testwagen.

    Ohne gepflegte Tankdaten werden die Fuel-Checks uebersprungen — die
    Tests brauchen darum ein konfiguriertes Fahrzeug.
    """
    vehicle = database.get_vehicle()
    vehicle.tank_capacity_l = tank_l
    vehicle.consumption_l_100km = consumption
    database.save_vehicle(vehicle)


def _add_full_tank(
    database: Database, date_iso: str, km_end: int, liters: float = 50.0
) -> None:
    """Legt einen Volltank-Event am angegebenen Endkilometerstand an."""
    trip = make_trip(date_iso, 0, business=False)
    trip.category = "fuel_private"
    trip.fuel_liters = liters
    trip.fuel_full_tank = True
    database.add_trip(trip)
    # km_end passend machen (rebuild + direkter Update)
    fetched = database.get_all_trips_ordered()[-1]
    conn = database._get_conn()  # type: ignore[reportPrivateUsage]
    conn.execute(
        "UPDATE trips SET km_start=?, km_end=? WHERE id=?",
        (km_end, km_end, fetched.id),
    )
    conn.commit()


def _add_partial_fill(
    database: Database, date_iso: str, km_end: int, liters: float
) -> None:
    """Legt eine Teilbetankung (fuel_full_tank=False) am km-Stand an."""
    trip = make_trip(date_iso, 0, business=False)
    trip.category = "fuel_private"
    trip.fuel_liters = liters
    trip.fuel_full_tank = False
    database.add_trip(trip)
    fetched = database.get_all_trips_ordered()[-1]
    conn = database._get_conn()  # type: ignore[reportPrivateUsage]
    conn.execute(
        "UPDATE trips SET km_start=?, km_end=? WHERE id=?",
        (km_end, km_end, fetched.id),
    )
    conn.commit()


class TestCheckFuelRangeExceeded:
    def test_no_vehicle_tank_data_no_issues(self, database: Database) -> None:
        """Ohne gepflegte Tank-/Verbrauchs-Daten wird der Check uebersprungen."""
        # Standard-Fixture hat tank_capacity_l=0
        _add_full_tank(database, "2024-01-01", 10000)
        _add_full_tank(database, "2024-01-15", 20000)  # 10000 km = physikalisch unmoeglich
        assert check_fuel_range_exceeded(database) == []

    def test_within_range_no_issue(self, database: Database) -> None:
        """Ein Intervall innerhalb der max. Reichweite loest nichts aus."""
        _vehicle_with_tank(database)  # 54l / 7.5 * 0.8 = min 6.0 -> 900km max
        _add_full_tank(database, "2024-01-01", 10000)
        _add_full_tank(database, "2024-01-15", 10700)  # 700 km, OK
        issues = check_fuel_range_exceeded(database)
        assert [i for i in issues if i.category == CAT_FUEL_RANGE_EXCEEDED] == []

    def test_range_exceeded_errors(self, database: Database) -> None:
        """Ueber max. Reichweite -> ERROR, Message nennt km-Grenze."""
        _vehicle_with_tank(database)
        _add_full_tank(database, "2024-01-01", 10000)
        _add_full_tank(database, "2024-01-20", 11100)  # 1100 km > 900 km
        issues = check_fuel_range_exceeded(database)
        errors = [i for i in issues if i.category == CAT_FUEL_RANGE_EXCEEDED]
        assert len(errors) == 1
        assert errors[0].severity == SEVERITY_ERROR
        assert "1100 km" in errors[0].message
        assert "900" in errors[0].message

    def test_multiple_intervals_independent(self, database: Database) -> None:
        """Mehrere Intervalle werden unabhaengig beurteilt."""
        _vehicle_with_tank(database)
        _add_full_tank(database, "2024-01-01", 10000)
        _add_full_tank(database, "2024-01-10", 10700)  # 700 km, OK
        _add_full_tank(database, "2024-02-01", 11900)  # 1200 km, BAD
        _add_full_tank(database, "2024-02-10", 12600)  # 700 km, OK
        errors = [
            i for i in check_fuel_range_exceeded(database)
            if i.category == CAT_FUEL_RANGE_EXCEEDED
        ]
        assert len(errors) == 1

    def test_single_full_tank_no_issue(self, database: Database) -> None:
        """Ein einzelner Volltank kann keinen Intervall-Fehler erzeugen."""
        _vehicle_with_tank(database)
        _add_full_tank(database, "2024-01-01", 10000)
        assert check_fuel_range_exceeded(database) == []

    def test_partial_fill_extends_range(self, database: Database) -> None:
        """Teilbetankung zwischen zwei Volltanks erweitert die max. Reichweite."""
        _vehicle_with_tank(database)  # 54 l / 6 L/100km = 900 km max
        _add_full_tank(database, "2024-01-01", 10000)
        _add_partial_fill(database, "2024-01-10", 10500, 36.0)  # +36 l -> +600 km
        _add_full_tank(database, "2024-01-20", 11100)  # 1100 km insgesamt
        # Ohne Fix: 1100 > 900 -> ERROR. Mit Fix: (54+36)/6*100 = 1500 km -> OK.
        errors = [
            i for i in check_fuel_range_exceeded(database)
            if i.category == CAT_FUEL_RANGE_EXCEEDED
        ]
        assert errors == []

    def test_partial_fill_still_too_far(self, database: Database) -> None:
        """Auch mit Teilbetankung kann die physikalische Grenze ueberschritten werden."""
        _vehicle_with_tank(database)  # 54 l -> 900 km
        _add_full_tank(database, "2024-01-01", 10000)
        _add_partial_fill(database, "2024-01-10", 10500, 10.0)  # +10 l -> +167 km
        _add_full_tank(database, "2024-01-20", 12000)  # 2000 km -- zu weit
        errors = [
            i for i in check_fuel_range_exceeded(database)
            if i.category == CAT_FUEL_RANGE_EXCEEDED
        ]
        assert len(errors) == 1
        assert "2000 km" in errors[0].message
        assert "10.00 l Teilbetankung" in errors[0].message


class TestCheckFuelConsumptionPartialFills:
    def test_partial_fill_counted_in_consumption(self, database: Database) -> None:
        """Teilbetankungen zaehlen zum Gesamtverbrauch zwischen zwei Volltanks."""
        from fahrtenbuch_app.services.plausibility import (
            check_fuel_consumption_range,
            CAT_FUEL_CONSUMPTION,
        )
        _vehicle_with_tank(database)  # target 7.5 +/- 20% -> 6..9
        _add_full_tank(database, "2024-01-01", 10000, liters=50.0)
        _add_partial_fill(database, "2024-01-10", 10500, 36.0)
        # 1200 km total, 36 + 54 = 90 l insgesamt -> 7.5 l/100km (perfekt)
        _add_full_tank(database, "2024-01-20", 11200, liters=54.0)
        issues = [
            i for i in check_fuel_consumption_range(database)
            if i.category == CAT_FUEL_CONSUMPTION
        ]
        assert issues == []

    def test_partial_fill_ignored_would_falsely_warn(self, database: Database) -> None:
        """Ohne Fix wuerde der Check hier faelschlich warnen."""
        from fahrtenbuch_app.services.plausibility import (
            check_fuel_consumption_range,
            CAT_FUEL_CONSUMPTION,
        )
        _vehicle_with_tank(database)
        _add_full_tank(database, "2024-01-01", 10000, liters=50.0)
        _add_partial_fill(database, "2024-01-10", 10500, 36.0)
        _add_full_tank(database, "2024-01-20", 11200, liters=54.0)
        # Kontrollrechnung: naive Rechnung (ohne Teilbetankung) = 54 l / 1200 km
        # = 4.5 l/100km -> das waere die falsche Warnung ohne Fix.
        issues = check_fuel_consumption_range(database)
        # Mit Fix darf keine Warnung kommen:
        assert all(
            "4.5 l/100km" not in i.message for i in issues
        )


# ---------------------------------------------------------------------------
# check_ghost_business_trips
# ---------------------------------------------------------------------------


class TestCheckGhostBusinessTrips:
    def test_empty_db_no_issues(self, database: Database) -> None:
        assert check_ghost_business_trips(database) == []

    def test_single_trip_no_issue(self, database: Database) -> None:
        database.add_trip(make_trip("2024-03-01", 260, destination="Kunde Nord"))
        assert check_ghost_business_trips(database) == []

    def test_close_duplicate_flagged(self, database: Database) -> None:
        """Zwei identische Trips innerhalb des Fensters -> INFO."""
        database.add_trip(make_trip("2024-03-01", 260, destination="Kunde Nord"))
        database.add_trip(make_trip("2024-03-08", 260, destination="Kunde Nord"))
        issues = check_ghost_business_trips(database)
        ghosts = [i for i in issues if i.category == CAT_GHOST_BUSINESS_TRIP]
        assert len(ghosts) == 1
        assert ghosts[0].severity == SEVERITY_INFO
        assert "2024-03-01" in ghosts[0].message
        assert "7 Tage" in ghosts[0].message

    def test_far_duplicate_not_flagged(self, database: Database) -> None:
        """Abstand groesser als Fenster -> keine Meldung."""
        assert GHOST_TRIP_WINDOW_DAYS == 14
        database.add_trip(make_trip("2024-03-01", 260, destination="Kunde Nord"))
        database.add_trip(make_trip("2024-03-20", 260, destination="Kunde Nord"))
        issues = check_ghost_business_trips(database)
        assert [i for i in issues if i.category == CAT_GHOST_BUSINESS_TRIP] == []

    def test_small_km_below_threshold(self, database: Database) -> None:
        """Kurzstrecken-Routinen (Supermarkt) werden nicht gemeldet."""
        assert GHOST_TRIP_MIN_KM == 100
        database.add_trip(make_trip("2024-03-01", 20, destination="Kunde X"))
        database.add_trip(make_trip("2024-03-02", 20, destination="Kunde X"))
        assert check_ghost_business_trips(database) == []

    def test_different_km_not_flagged(self, database: Database) -> None:
        """Gleiche Destination, aber andere km-Summe -> kein Ghost."""
        database.add_trip(make_trip("2024-03-01", 260, destination="Kunde Nord"))
        database.add_trip(make_trip("2024-03-03", 280, destination="Kunde Nord"))
        issues = check_ghost_business_trips(database)
        assert [i for i in issues if i.category == CAT_GHOST_BUSINESS_TRIP] == []

    def test_different_destinations_not_flagged(self, database: Database) -> None:
        """Gleiche km, aber andere Destination -> kein Ghost."""
        database.add_trip(make_trip("2024-03-01", 260, destination="Kunde A"))
        database.add_trip(make_trip("2024-03-03", 260, destination="Kunde B"))
        assert check_ghost_business_trips(database) == []

    def test_private_trips_not_flagged(self, database: Database) -> None:
        """Private Fahrten sind vom Ghost-Check ausgenommen."""
        database.add_trip(
            make_trip("2024-03-01", 260, destination="Kunde Nord", business=False)
        )
        database.add_trip(
            make_trip("2024-03-03", 260, destination="Kunde Nord", business=False)
        )
        assert check_ghost_business_trips(database) == []

    def test_destination_case_insensitive(self, database: Database) -> None:
        """Destination-Vergleich ist case-insensitive mit strip."""
        database.add_trip(make_trip("2024-03-01", 260, destination="  KUNDE NORD  "))
        database.add_trip(make_trip("2024-03-03", 260, destination="kunde nord"))
        issues = check_ghost_business_trips(database)
        ghosts = [i for i in issues if i.category == CAT_GHOST_BUSINESS_TRIP]
        assert len(ghosts) == 1
