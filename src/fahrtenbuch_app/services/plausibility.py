"""Plausibilitaets-Checks fuer Fahrtenbuch-Daten.

Dieses Modul buendelt alle Integritaetspruefungen ueber die Trip-Daten.
Es wird sowohl vom Unit-Test-Pfad (tests/test_plausibility.py) als auch
spaeter vom "p"-Plausibilitaets-Button in der UI verwendet.

Alle Checks sind pure Funktionen ueber einer Database-Instanz und geben
eine Liste von Issues zurueck — sie modifizieren nichts. Das macht sie
sowohl testbar als auch gefahrlos wiederholt aufrufbar.
"""

from dataclasses import dataclass, field
from datetime import date

from fahrtenbuch_app.models.trip import Trip
from fahrtenbuch_app.services.database import Database

__all__ = [
    "PlausibilityIssue",
    "PlausibilityReport",
    "SEVERITY_ERROR",
    "SEVERITY_WARNING",
    "SEVERITY_INFO",
    "CAT_CHAIN_BREAK",
    "CAT_CHAIN_BACKWARD",
    "CAT_DISTANCE_MISMATCH",
    "CAT_OVER_LIMIT",
    "CAT_WEEKEND_BUSINESS",
    "CAT_HOLIDAY_BUSINESS",
    "CAT_BLACKLIST_BUSINESS",
    "CAT_NEGATIVE_DISTANCE",
    "CAT_EMPTY_TRIP",
    "check_chain_ascending",
    "check_distance_matches_columns",
    "check_vehicle_end_limit",
    "check_empty_trips",
    "check_weekend_business",
    "check_holiday_business",
    "check_blacklist_business",
    "run_all_checks",
]


# Severity-Level
SEVERITY_ERROR = "error"
SEVERITY_WARNING = "warning"
SEVERITY_INFO = "info"

# Issue-Kategorien (fuer Gruppierung und Filter)
CAT_CHAIN_BREAK = "chain_break"
CAT_CHAIN_BACKWARD = "chain_backward"
CAT_DISTANCE_MISMATCH = "distance_mismatch"
CAT_OVER_LIMIT = "over_limit"
CAT_WEEKEND_BUSINESS = "weekend_business"
CAT_HOLIDAY_BUSINESS = "holiday_business"
CAT_BLACKLIST_BUSINESS = "blacklist_business"
CAT_NEGATIVE_DISTANCE = "negative_distance"
CAT_EMPTY_TRIP = "empty_trip"


@dataclass
class PlausibilityIssue:
    """Einzelner Befund eines Plausibilitaets-Checks."""

    severity: str
    category: str
    message: str
    trip_id: int | None = None
    trip_date: str = ""
    year: int | None = None
    month: int | None = None

    @property
    def month_key(self) -> tuple[int, int] | None:
        """Gibt (year, month) fuer die Monats-Gruppierung oder None zurueck."""
        if self.year is not None and self.month is not None:
            return (self.year, self.month)
        return None


@dataclass
class PlausibilityReport:
    """Zusammenfassung aller gefundenen Issues, gruppiert nach Monat."""

    issues: list[PlausibilityIssue] = field(default_factory=list)

    @property
    def error_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == SEVERITY_ERROR)

    @property
    def warning_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == SEVERITY_WARNING)

    @property
    def info_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == SEVERITY_INFO)

    @property
    def has_issues(self) -> bool:
        return len(self.issues) > 0

    def by_month(self) -> dict[tuple[int, int] | None, list[PlausibilityIssue]]:
        """Gruppiert Issues nach (year, month)-Tupel.

        Issues ohne Monat landen unter dem Key None (globale Probleme).
        """
        groups: dict[tuple[int, int] | None, list[PlausibilityIssue]] = {}
        for issue in self.issues:
            key = issue.month_key
            groups.setdefault(key, []).append(issue)
        return groups

    def by_category(self) -> dict[str, list[PlausibilityIssue]]:
        """Gruppiert Issues nach Kategorie."""
        groups: dict[str, list[PlausibilityIssue]] = {}
        for issue in self.issues:
            groups.setdefault(issue.category, []).append(issue)
        return groups


def _parse_trip_date(trip: Trip) -> date | None:
    """Wandelt trip.date (ISO) in ein date-Objekt um — oder None bei Fehler."""
    try:
        parts = trip.date.split("-")
        return date(int(parts[0]), int(parts[1]), int(parts[2]))
    except (ValueError, IndexError):
        return None


def _load_all_trips_ordered(database: Database) -> list[Trip]:
    """Laedt alle Trips aus der DB sortiert nach (date, id).

    Stimmt mit der kanonischen Reihenfolge der km-Kette ueberein.
    """
    return database.get_all_trips_ordered()


# ---------------------------------------------------------------------------
# Einzelne Checks
# ---------------------------------------------------------------------------


def check_chain_ascending(database: Database) -> list[PlausibilityIssue]:
    """Prueft ob die km-Kette chronologisch aufsteigend ist.

    Jede Fahrt muss bei km_start >= km_end der Vorgaenger-Fahrt beginnen.
    - exakt gleich: sauber (kein Issue)
    - Luecke (positive Diskrepanz): warning — Kilometer fehlen
    - Rueckwaerts (negative Diskrepanz): error — Kette ist zerbrochen

    Zusaetzlich:
    - Erste Fahrt darf nicht unter vehicle.start_km liegen
    - Jede Fahrt muss km_end >= km_start haben
    """
    issues: list[PlausibilityIssue] = []
    trips = _load_all_trips_ordered(database)
    if not trips:
        return issues

    vehicle = database.get_vehicle()

    # Ersten Trip gegen vehicle.start_km pruefen
    first = trips[0]
    if vehicle.start_km > 0 and first.km_start < vehicle.start_km:
        d = _parse_trip_date(first)
        issues.append(PlausibilityIssue(
            severity=SEVERITY_ERROR,
            category=CAT_CHAIN_BREAK,
            message=(
                f"Erste Fahrt startet bei {first.km_start} km, "
                f"aber Fahrzeug-Anfangsstand ist {vehicle.start_km} km"
            ),
            trip_id=first.id,
            trip_date=first.date,
            year=d.year if d else None,
            month=d.month if d else None,
        ))

    # Jede Fahrt einzeln pruefen (negative Distanz)
    for trip in trips:
        distance = trip.km_end - trip.km_start
        if distance < 0:
            d = _parse_trip_date(trip)
            issues.append(PlausibilityIssue(
                severity=SEVERITY_ERROR,
                category=CAT_NEGATIVE_DISTANCE,
                message=(
                    f"Fahrt hat negative Distanz: "
                    f"km_start={trip.km_start} > km_end={trip.km_end}"
                ),
                trip_id=trip.id,
                trip_date=trip.date,
                year=d.year if d else None,
                month=d.month if d else None,
            ))

    # Paarweise pruefen
    for prev, curr in zip(trips, trips[1:]):
        delta = curr.km_start - prev.km_end
        if delta == 0:
            continue
        d = _parse_trip_date(curr)
        if delta < 0:
            # Rueckwaerts-Sprung — schwerer Fehler
            issues.append(PlausibilityIssue(
                severity=SEVERITY_ERROR,
                category=CAT_CHAIN_BACKWARD,
                message=(
                    f"Kette bricht: Vorgaenger endet bei {prev.km_end} km, "
                    f"diese Fahrt startet aber bei {curr.km_start} km "
                    f"({delta} km Rueckwaerts-Sprung)"
                ),
                trip_id=curr.id,
                trip_date=curr.date,
                year=d.year if d else None,
                month=d.month if d else None,
            ))
        else:
            # Luecke vorwaerts — weniger schlimm, aber verdaechtig
            issues.append(PlausibilityIssue(
                severity=SEVERITY_WARNING,
                category=CAT_CHAIN_BREAK,
                message=(
                    f"Luecke in der km-Kette: Vorgaenger endet bei "
                    f"{prev.km_end} km, diese Fahrt startet bei "
                    f"{curr.km_start} km (+{delta} km)"
                ),
                trip_id=curr.id,
                trip_date=curr.date,
                year=d.year if d else None,
                month=d.month if d else None,
            ))

    return issues


def check_distance_matches_columns(database: Database) -> list[PlausibilityIssue]:
    """Prueft ob km_business + km_private der Distanz entspricht.

    Bei Fahrten mit vernuenftigen Spalten-Summen soll
    km_business + km_private == km_end - km_start sein.
    Abweichungen sind warnungs-wuerdig, weil sie auf manuelle Aenderungen
    hindeuten, die die Buchhaltung verzerren.
    """
    issues: list[PlausibilityIssue] = []
    trips = _load_all_trips_ordered(database)
    for trip in trips:
        distance = trip.km_end - trip.km_start
        columns = trip.km_business + trip.km_private
        if distance == columns:
            continue
        # Ausnahme: Trip mit 0 Distanz und 0 Spalten ist konsistent
        if distance == 0 and columns == 0:
            continue
        d = _parse_trip_date(trip)
        issues.append(PlausibilityIssue(
            severity=SEVERITY_WARNING,
            category=CAT_DISTANCE_MISMATCH,
            message=(
                f"Distanz stimmt nicht mit Spalten ueberein: "
                f"km_end-km_start={distance} km, "
                f"business+private={columns} km"
            ),
            trip_id=trip.id,
            trip_date=trip.date,
            year=d.year if d else None,
            month=d.month if d else None,
        ))
    return issues


def check_vehicle_end_limit(database: Database) -> list[PlausibilityIssue]:
    """Prueft ob irgendeine Fahrt das Vertragsende-km ueberschreitet.

    Wichtig: das war frueher ein Hard-Stop in add_trip/update_trip — wir
    lassen die Aenderung durchgehen, aber melden die Ueberschreitung hier.
    """
    issues: list[PlausibilityIssue] = []
    vehicle = database.get_vehicle()
    if vehicle.end_km <= 0:
        return issues
    trips = _load_all_trips_ordered(database)
    for trip in trips:
        if trip.km_end > vehicle.end_km:
            d = _parse_trip_date(trip)
            issues.append(PlausibilityIssue(
                severity=SEVERITY_ERROR,
                category=CAT_OVER_LIMIT,
                message=(
                    f"Fahrt endet bei {trip.km_end} km — ueber Vertragslimit "
                    f"von {vehicle.end_km} km"
                ),
                trip_id=trip.id,
                trip_date=trip.date,
                year=d.year if d else None,
                month=d.month if d else None,
            ))
    return issues


def check_empty_trips(database: Database) -> list[PlausibilityIssue]:
    """Findet Fahrten ohne Distanz aber mit gebuchten km_business/km_private.

    Das war der Bug bei Trip 103/104: km_start == km_end == 16070, aber
    km_business = 260. Solche Datensaetze verzerren die Monatssumme.
    """
    issues: list[PlausibilityIssue] = []
    trips = _load_all_trips_ordered(database)
    for trip in trips:
        distance = trip.km_end - trip.km_start
        if distance == 0 and (trip.km_business > 0 or trip.km_private > 0):
            d = _parse_trip_date(trip)
            issues.append(PlausibilityIssue(
                severity=SEVERITY_ERROR,
                category=CAT_EMPTY_TRIP,
                message=(
                    f"Fahrt hat 0 km Distanz, aber "
                    f"business={trip.km_business} / private={trip.km_private} km "
                    f"gebucht"
                ),
                trip_id=trip.id,
                trip_date=trip.date,
                year=d.year if d else None,
                month=d.month if d else None,
            ))
    return issues


def check_weekend_business(database: Database) -> list[PlausibilityIssue]:
    """Findet reine Business-Fahrten am Wochenende.

    Tanken und Service sind am Wochenende OK — hier geht es nur um
    category='business'.
    """
    issues: list[PlausibilityIssue] = []
    trips = _load_all_trips_ordered(database)
    for trip in trips:
        if trip.category != "business":
            continue
        d = _parse_trip_date(trip)
        if d is None or d.weekday() < 5:
            continue
        issues.append(PlausibilityIssue(
            severity=SEVERITY_WARNING,
            category=CAT_WEEKEND_BUSINESS,
            message=(
                f"Geschaeftliche Fahrt am {_weekday_de(d)}: {trip.purpose}"
            ),
            trip_id=trip.id,
            trip_date=trip.date,
            year=d.year,
            month=d.month,
        ))
    return issues


def check_holiday_business(
    database: Database,
    holidays_by_date: dict[date, str],
) -> list[PlausibilityIssue]:
    """Findet reine Business-Fahrten an Feiertagen.

    Erwartet ein Mapping (date -> Feiertagsname), das der Aufrufer aus
    HolidayService laedt — so bleibt das Modul frei von
    Feiertags-Dependencies.
    """
    issues: list[PlausibilityIssue] = []
    trips = _load_all_trips_ordered(database)
    for trip in trips:
        if trip.category != "business":
            continue
        d = _parse_trip_date(trip)
        if d is None:
            continue
        holiday_name = holidays_by_date.get(d, "")
        if not holiday_name:
            continue
        issues.append(PlausibilityIssue(
            severity=SEVERITY_WARNING,
            category=CAT_HOLIDAY_BUSINESS,
            message=(
                f"Geschaeftliche Fahrt am Feiertag ({holiday_name}): "
                f"{trip.purpose}"
            ),
            trip_id=trip.id,
            trip_date=trip.date,
            year=d.year,
            month=d.month,
        ))
    return issues


def check_blacklist_business(database: Database) -> list[PlausibilityIssue]:
    """Findet geschaeftliche Fahrten an gesperrten Tagen (Blacklist)."""
    issues: list[PlausibilityIssue] = []
    blacklist_entries = database.get_blacklist()
    if not blacklist_entries:
        return issues
    # Blacklist-Map aufbauen
    bl_map: dict[date, str] = {}
    for entry in blacklist_entries:
        try:
            date_str = str(entry.get("date", ""))
            parts = date_str.split("-")
            d = date(int(parts[0]), int(parts[1]), int(parts[2]))
            bl_map[d] = str(entry.get("reason", ""))
        except (ValueError, IndexError):
            continue

    trips = _load_all_trips_ordered(database)
    for trip in trips:
        if not trip.is_business_km:
            continue
        d = _parse_trip_date(trip)
        if d is None:
            continue
        reason = bl_map.get(d, "")
        if not reason:
            continue
        issues.append(PlausibilityIssue(
            severity=SEVERITY_ERROR,
            category=CAT_BLACKLIST_BUSINESS,
            message=(
                f"Geschaeftliche Fahrt an gesperrtem Tag ({reason}): "
                f"{trip.purpose}"
            ),
            trip_id=trip.id,
            trip_date=trip.date,
            year=d.year,
            month=d.month,
        ))
    return issues


# ---------------------------------------------------------------------------
# Gesamt-Report
# ---------------------------------------------------------------------------


def run_all_checks(
    database: Database,
    holidays_by_date: dict[date, str] | None = None,
) -> PlausibilityReport:
    """Fuehrt alle Plausi-Checks aus und liefert einen Report.

    Das ist der Einstiegspunkt fuer den "p"-Button in der UI.
    """
    report = PlausibilityReport()
    report.issues.extend(check_chain_ascending(database))
    report.issues.extend(check_distance_matches_columns(database))
    report.issues.extend(check_empty_trips(database))
    report.issues.extend(check_vehicle_end_limit(database))
    report.issues.extend(check_weekend_business(database))
    if holidays_by_date:
        report.issues.extend(check_holiday_business(database, holidays_by_date))
    report.issues.extend(check_blacklist_business(database))
    return report


_WEEKDAY_NAMES_DE = [
    "Montag", "Dienstag", "Mittwoch", "Donnerstag",
    "Freitag", "Samstag", "Sonntag",
]


def _weekday_de(d: date) -> str:
    return _WEEKDAY_NAMES_DE[d.weekday()]
