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

from fahrtenbuch_app.models.trip import (
    Trip,
    get_business_categories,
    get_informational_categories,
)
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
    "CAT_END_MISMATCH",
    "CAT_WEEKEND_BUSINESS",
    "CAT_HOLIDAY_BUSINESS",
    "CAT_BLACKLIST_BUSINESS",
    "CAT_NEGATIVE_DISTANCE",
    "CAT_EMPTY_TRIP",
    "CAT_CATEGORY_COLUMN_MISMATCH",
    "CAT_WORKTIME_RATIO",
    "CAT_BUSINESS_QUOTA_LOW",
    "CAT_FUEL_OVER_TANK",
    "CAT_FUEL_CONSUMPTION",
    "CAT_FUEL_RANGE_EXCEEDED",
    "CAT_GHOST_BUSINESS_TRIP",
    "BUSINESS_QUOTA_MIN",
    "WORKTIME_RATIO_FACTOR",
    "FUEL_TOLERANCE",
    "FUEL_MIN_INTERVAL_KM",
    "GHOST_TRIP_WINDOW_DAYS",
    "GHOST_TRIP_MIN_KM",
    "check_chain_ascending",
    "check_distance_matches_columns",
    "check_vehicle_end_limit",
    "check_vehicle_end_reached",
    "check_empty_trips",
    "check_category_column_match",
    "check_weekend_business",
    "check_holiday_business",
    "check_blacklist_business",
    "check_worktime_trip_ratio",
    "check_business_quota",
    "check_fuel_tank_capacity",
    "check_fuel_consumption_range",
    "check_fuel_range_exceeded",
    "check_ghost_business_trips",
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
CAT_END_MISMATCH = "end_mismatch"
CAT_WEEKEND_BUSINESS = "weekend_business"
CAT_HOLIDAY_BUSINESS = "holiday_business"
CAT_BLACKLIST_BUSINESS = "blacklist_business"
CAT_NEGATIVE_DISTANCE = "negative_distance"
CAT_EMPTY_TRIP = "empty_trip"
CAT_CATEGORY_COLUMN_MISMATCH = "category_column_mismatch"
CAT_WORKTIME_RATIO = "worktime_ratio"
CAT_BUSINESS_QUOTA_LOW = "business_quota_low"
CAT_FUEL_OVER_TANK = "fuel_over_tank"
CAT_FUEL_CONSUMPTION = "fuel_consumption"
CAT_FUEL_RANGE_EXCEEDED = "fuel_range_exceeded"
CAT_GHOST_BUSINESS_TRIP = "ghost_business_trip"

# Schwellen: 50% Business-Quote pro Jahr (Finanzamt-Regel), 1.3x der
# Jahres-Durchschnittsrate bei Fahrten pro Arbeitsstunde.
BUSINESS_QUOTA_MIN = 0.50
WORKTIME_RATIO_FACTOR = 1.3

# Verbrauchs-Toleranz bei Full-to-Full-Intervallen: +/- 20 % um den in den
# Vehicle-Settings hinterlegten Durchschnittsverbrauch. Strecken kuerzer als
# FUEL_MIN_INTERVAL_KM liefern durch Messrauschen (Tank nicht exakt voll,
# Restluft) keine sinnvollen Quoten und werden ausgelassen.
FUEL_TOLERANCE = 0.20
FUEL_MIN_INTERVAL_KM = 50

# Im Winter (Nov-Maerz) sind Kaltstarts, Standheizung, Winterreifen und
# zaehes Oel gute Gruende fuer deutlich hoeheren Verbrauch. Wenn das Setting
# fuel_winter_tolerance aktiv ist, bekommt ein Intervall das in einem
# Winter-Monat endet zusaetzlich FUEL_WINTER_EXTRA oben drauf (also 0.35
# statt 0.20 Gesamt-Toleranz).
FUEL_WINTER_MONTHS = frozenset({11, 12, 1, 2, 3})
FUEL_WINTER_EXTRA = 0.15

# Ghost-Trip-Heuristik: zwei geschaeftliche Trips mit gleicher Destination
# und gleicher km-Summe innerhalb des Fensters sind verdaechtig. Minimum-km
# hebt typische Kurzstrecken-Routinen (Supermarkt, Post) aus dem Radar.
GHOST_TRIP_WINDOW_DAYS = 14
GHOST_TRIP_MIN_KM = 100


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
    """Laedt alle Trips aus der DB sortiert nach (date, id), ohne
    informationelle Trips (Anlieferung/Rueckgabe).

    Informationelle Trips tragen keine km und sind fuer keinen Plausi-Check
    relevant. Das Auslassen hier haelt alle Einzel-Checks frei von
    Sonderfaellen.
    """
    info_cats = get_informational_categories()
    return [
        t for t in database.get_all_trips_ordered()
        if t.category not in info_cats
    ]


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
    Zusaetzlich wird am Ende eine einzige Zusammenfassung mit der Gesamt-
    Ueberschreitung erzeugt, damit der User nicht selbst nachrechnen muss.
    """
    issues: list[PlausibilityIssue] = []
    vehicle = database.get_vehicle()
    if vehicle.end_km <= 0:
        return issues
    trips = _load_all_trips_ordered(database)
    last_over: Trip | None = None
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
            last_over = trip
    if last_over is not None:
        overshoot = last_over.km_end - vehicle.end_km
        d = _parse_trip_date(last_over)
        issues.append(PlausibilityIssue(
            severity=SEVERITY_ERROR,
            category=CAT_OVER_LIMIT,
            message=(
                f"Gesamt {overshoot} km zu viel eingetragen: letzte Fahrt "
                f"endet bei {last_over.km_end} km, erlaubt max {vehicle.end_km} km "
                f"— Trip-km um {overshoot} km nach unten korrigieren"
            ),
            trip_id=last_over.id,
            trip_date=last_over.date,
            year=d.year if d else None,
            month=d.month if d else None,
        ))
    return issues


def check_vehicle_end_reached(database: Database) -> list[PlausibilityIssue]:
    """Prueft ob die Fahrten-Summe den hinterlegten Endstand ergibt.

    Wenn vehicle.end_km > 0 gesetzt ist, wird erwartet dass der letzte
    Trip genau bei diesem km-Stand endet. Andernfalls bleibt eine Luecke
    — Hinweis dass noch Fahrten fehlen oder der Endstand falsch eingetragen
    ist. Die Ueberschreitung wird separat von check_vehicle_end_limit
    gemeldet, deshalb nur Unterdeckung hier.
    """
    issues: list[PlausibilityIssue] = []
    vehicle = database.get_vehicle()
    if vehicle.end_km <= 0:
        return issues
    trips = _load_all_trips_ordered(database)
    if not trips:
        return issues
    last = trips[-1]
    diff = vehicle.end_km - last.km_end
    if diff > 0:
        d = _parse_trip_date(last)
        issues.append(PlausibilityIssue(
            severity=SEVERITY_WARNING,
            category=CAT_END_MISMATCH,
            message=(
                f"Fahrten-Summe erreicht Endstand nicht: letzte Fahrt endet "
                f"bei {last.km_end} km, erwartet {vehicle.end_km} km "
                f"(Luecke {diff} km)"
            ),
            trip_id=last.id,
            trip_date=last.date,
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


def check_category_column_match(database: Database) -> list[PlausibilityIssue]:
    """Prueft ob die km-Spalte zur Kategorie passt.

    - Business-Kategorien (business, fuel, service, ...) muessen km in
      km_business haben, km_private muss 0 sein.
    - Alle anderen Kategorien (private, fuel_private, ...) muessen km in
      km_private haben, km_business muss 0 sein.

    Das faengt Bugs beim Kategoriewechsel in der Detail-Maske ab, bei denen
    die km nicht korrekt zwischen den Spalten umgebucht wurden. Ein solcher
    Trip kann zufaellig eine konsistente Distanz haben und wuerde von
    check_distance_matches_columns nicht erkannt.
    """
    issues: list[PlausibilityIssue] = []
    trips = _load_all_trips_ordered(database)
    business_cats = get_business_categories()
    for trip in trips:
        d = _parse_trip_date(trip)
        if trip.category in business_cats:
            # Business: km_private muss 0 sein
            if trip.km_private > 0:
                issues.append(PlausibilityIssue(
                    severity=SEVERITY_WARNING,
                    category=CAT_CATEGORY_COLUMN_MISMATCH,
                    message=(
                        f"Kategorie '{trip.category}' ist geschaeftlich, aber "
                        f"km_private={trip.km_private} km ist gesetzt"
                    ),
                    trip_id=trip.id,
                    trip_date=trip.date,
                    year=d.year if d else None,
                    month=d.month if d else None,
                ))
        else:
            # Nicht-Business: km_business muss 0 sein
            if trip.km_business > 0:
                issues.append(PlausibilityIssue(
                    severity=SEVERITY_WARNING,
                    category=CAT_CATEGORY_COLUMN_MISMATCH,
                    message=(
                        f"Kategorie '{trip.category}' ist privat, aber "
                        f"km_business={trip.km_business} km ist gesetzt"
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
    category='business'. Geschaeftsessen (per purpose erkannt) sind am
    Wochenende explizit zulaessig und werden uebersprungen.
    """
    issues: list[PlausibilityIssue] = []
    trips = _load_all_trips_ordered(database)
    for trip in trips:
        if trip.category != "business":
            continue
        if "geschaeftsessen" in trip.purpose.lower():
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
        if "geschaeftsessen" in trip.purpose.lower():
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


def check_worktime_trip_ratio(database: Database) -> list[PlausibilityIssue]:
    """Prueft ob Geschaeftsfahrten zur Arbeitszeit passen.

    Fuer jedes Jahr mit gepflegten Arbeitszeiten berechnet der Check die
    durchschnittliche Anzahl Geschaeftsfahrten pro Stunde. Monate, die
    deutlich ueber dieser Rate liegen (Faktor WORKTIME_RATIO_FACTOR),
    werden als Warnung gemeldet — typisches Szenario: Urlaubsmonat mit
    wenig Arbeitszeit, aber genauso viele Fahrten wie ein voller Monat.

    Monate ohne gepflegte Arbeitszeit werden uebersprungen (kein Vergleich
    moeglich). Jahre mit weniger als zwei gepflegten Monaten liefern keine
    sinnvolle Baseline und werden ebenfalls ignoriert.
    """
    issues: list[PlausibilityIssue] = []
    trips = _load_all_trips_ordered(database)
    if not trips:
        return issues

    business_cats = get_business_categories()

    # Business-Trip-Anzahl pro (year, month)
    trips_per_month: dict[tuple[int, int], int] = {}
    years_with_trips: set[int] = set()
    for trip in trips:
        if trip.category not in business_cats:
            continue
        d = _parse_trip_date(trip)
        if d is None:
            continue
        key = (d.year, d.month)
        trips_per_month[key] = trips_per_month.get(key, 0) + 1
        years_with_trips.add(d.year)

    for year in sorted(years_with_trips):
        worktimes = database.get_worktimes(year)
        hours_per_month: dict[int, float] = {}
        for wt in worktimes:
            month = int(wt.get("month", 0))
            hours = float(wt.get("hours", 0.0))
            if month and hours > 0:
                hours_per_month[month] = hours

        if len(hours_per_month) < 2:
            # Weniger als 2 Monate Arbeitszeit gepflegt — keine Baseline
            continue

        # Jahres-Durchschnittsrate: Gesamt-Business-Fahrten / Gesamt-Stunden
        total_trips = sum(
            trips_per_month.get((year, m), 0) for m in hours_per_month
        )
        total_hours = sum(hours_per_month.values())
        if total_trips == 0 or total_hours <= 0:
            continue
        avg_rate = total_trips / total_hours

        for month, hours in sorted(hours_per_month.items()):
            actual = trips_per_month.get((year, month), 0)
            expected = avg_rate * hours
            if expected <= 0 or actual == 0:
                continue
            if actual > expected * WORKTIME_RATIO_FACTOR:
                issues.append(PlausibilityIssue(
                    severity=SEVERITY_WARNING,
                    category=CAT_WORKTIME_RATIO,
                    message=(
                        f"{_MONTH_NAMES_DE[month - 1]} {year}: "
                        f"{actual} Geschaeftsfahrten bei nur {hours:.2f} h "
                        f"Arbeitszeit — erwartet ca. {expected:.1f} Fahrten "
                        f"(Jahresdurchschnitt {avg_rate:.2f}/h). "
                        f"Urlaub/Krankheit eingerechnet?"
                    ),
                    trip_id=None,
                    trip_date=f"{year:04d}-{month:02d}-01",
                    year=year,
                    month=month,
                ))

    return issues


def check_business_quota(database: Database) -> list[PlausibilityIssue]:
    """Prueft die Business-Quote pro Jahr (Finanzamt-Regel >=50%).

    Summe km_business / (km_business + km_private) muss pro Jahr
    mindestens BUSINESS_QUOTA_MIN betragen. Darunter gilt das Fahrtenbuch
    dem Finanzamt als nicht mehr ueberwiegend betrieblich — der gesamte
    Nachweis ist dann gefaehrdet.
    """
    issues: list[PlausibilityIssue] = []
    trips = _load_all_trips_ordered(database)
    if not trips:
        return issues

    sums_per_year: dict[int, tuple[int, int]] = {}
    for trip in trips:
        d = _parse_trip_date(trip)
        if d is None:
            continue
        biz, priv = sums_per_year.get(d.year, (0, 0))
        sums_per_year[d.year] = (biz + trip.km_business, priv + trip.km_private)

    for year in sorted(sums_per_year):
        biz, priv = sums_per_year[year]
        total = biz + priv
        if total <= 0:
            continue
        ratio = biz / total
        if ratio < BUSINESS_QUOTA_MIN:
            issues.append(PlausibilityIssue(
                severity=SEVERITY_WARNING,
                category=CAT_BUSINESS_QUOTA_LOW,
                message=(
                    f"Jahr {year}: nur {ratio * 100:.1f} % geschaeftlich "
                    f"({biz} von {total} km). Finanzamt verlangt "
                    f"mindestens {BUSINESS_QUOTA_MIN * 100:.0f} %."
                ),
                trip_id=None,
                trip_date=f"{year:04d}-01-01",
                year=year,
                month=1,
            ))

    return issues


def check_fuel_tank_capacity(database: Database) -> list[PlausibilityIssue]:
    """Prueft ob getankte Liter die Tankkapazitaet ueberschreiten.

    Loest aus, wenn fuel_liters > tank_capacity_l. Ist tank_capacity_l nicht
    gepflegt (0), wird der Check uebersprungen — sonst wuerde er bei neuen
    DBs permanent feuern.
    """
    issues: list[PlausibilityIssue] = []
    vehicle = database.get_vehicle()
    if vehicle.tank_capacity_l <= 0:
        return issues
    trips = _load_all_trips_ordered(database)
    for trip in trips:
        if trip.category not in ("fuel", "fuel_private"):
            continue
        if trip.fuel_liters <= 0:
            continue
        if trip.fuel_liters <= vehicle.tank_capacity_l + 0.5:
            # Kleine Toleranz fuer Messrauschen am Tankwart-Automat
            continue
        d = _parse_trip_date(trip)
        issues.append(PlausibilityIssue(
            severity=SEVERITY_ERROR,
            category=CAT_FUEL_OVER_TANK,
            message=(
                f"Tankfuellung {trip.fuel_liters:.2f} l ueberschreitet "
                f"Tankkapazitaet {vehicle.tank_capacity_l:.0f} l"
            ),
            trip_id=trip.id,
            trip_date=trip.date,
            year=d.year if d else None,
            month=d.month if d else None,
        ))
    return issues


def check_fuel_consumption_range(database: Database) -> list[PlausibilityIssue]:
    """Prueft den Verbrauch zwischen zwei Volltank-Events.

    Idee: Zwischen zwei Full-Tank-Tankungen entspricht die nachgetankte Menge
    genau dem Verbrauch der zurueckgelegten Strecke. Liegt der daraus errechnete
    Verbrauch (l/100km) ausserhalb von vehicle.consumption_l_100km +/-
    FUEL_TOLERANCE, ist entweder die km-Kette falsch, die Literangabe falsch
    oder der Fahrstil sehr ungewoehnlich.

    km-Basis: trip.km_end zum Tankzeitpunkt. Bei fuel_private ist der Trip
    nicht-business, aber fuer die Verbrauchsrechnung egal — Liter zwischen
    Volltanks zaehlen immer. Zur Strecke wird aber km_end des jeweiligen
    Tank-Trips genommen, nicht die getankten Liter in die Verbrauchsrechnung
    des eigenen Tankvorgangs eingehen (Liter tanken wir NACH dem Fahren).

    Intervalle kuerzer als FUEL_MIN_INTERVAL_KM werden uebersprungen, weil
    sie zu rauschanfaellig sind.
    """
    issues: list[PlausibilityIssue] = []
    vehicle = database.get_vehicle()
    if vehicle.consumption_l_100km <= 0:
        return issues

    trips = _load_all_trips_ordered(database)
    full_tanks: list[Trip] = [
        t for t in trips
        if t.category in ("fuel", "fuel_private")
        and t.fuel_full_tank
        and t.fuel_liters > 0
    ]
    if len(full_tanks) < 2:
        return issues

    partial_fills: list[Trip] = [
        t for t in trips
        if t.category in ("fuel", "fuel_private")
        and not t.fuel_full_tank
        and t.fuel_liters > 0
    ]

    target = vehicle.consumption_l_100km
    winter_enabled = database.get_setting("fuel_winter_tolerance", "1") == "1"

    for prev, curr in zip(full_tanks, full_tanks[1:]):
        distance_km = curr.km_end - prev.km_end
        if distance_km < FUEL_MIN_INTERVAL_KM:
            continue
        if distance_km <= 0:
            continue
        # Zwischen zwei Volltankungen nachgefuellte Liter (inkl. Teilbetankungen
        # im Intervall) entsprechen dem Gesamtverbrauch auf der Strecke.
        mid_liters = sum(
            p.fuel_liters for p in partial_fills
            if prev.km_end < p.km_end <= curr.km_end
        )
        total_liters = curr.fuel_liters + mid_liters
        consumption = total_liters * 100.0 / distance_km
        d = _parse_trip_date(curr)
        tolerance = FUEL_TOLERANCE
        if winter_enabled and d and d.month in FUEL_WINTER_MONTHS:
            tolerance += FUEL_WINTER_EXTRA
        low = target * (1 - tolerance)
        high = target * (1 + tolerance)
        if low <= consumption <= high:
            continue
        severity = SEVERITY_WARNING if consumption < target * 2 else SEVERITY_ERROR
        issues.append(PlausibilityIssue(
            severity=severity,
            category=CAT_FUEL_CONSUMPTION,
            message=(
                f"Verbrauch {consumption:.1f} l/100km zwischen Volltank "
                f"{prev.date} und {curr.date} ({distance_km} km, "
                f"{total_liters:.2f} l) — erwartet "
                f"{target:.1f} l/100km +/- {int(tolerance * 100)} %"
            ),
            trip_id=curr.id,
            trip_date=curr.date,
            year=d.year if d else None,
            month=d.month if d else None,
        ))
    return issues


def check_fuel_range_exceeded(database: Database) -> list[PlausibilityIssue]:
    """Prueft ob zwischen zwei Volltankungen mehr km gefahren wurden als
    der Tank physikalisch hergeben kann.

    Das ist der harte physikalische Partner zu check_fuel_consumption_range:
    Bei tank_capacity_l = 54 und consumption_l_100km = 7.5 (untere Toleranz
    6.0) reicht ein voller Tank fuer maximal 900 km. Laengere Intervalle
    sind physikalisch unmoeglich und weisen zwingend auf eine fehlende
    Tankung ODER einen ueberzaehligen Trip (Ghost) im Intervall hin.

    Severity ist ERROR — dieser Befund ist sicher falsch, nicht nur
    verdaechtig. Der Check laeuft nur, wenn tank_capacity_l und
    consumption_l_100km gepflegt sind.
    """
    issues: list[PlausibilityIssue] = []
    vehicle = database.get_vehicle()
    if vehicle.tank_capacity_l <= 0 or vehicle.consumption_l_100km <= 0:
        return issues

    # Maximale Reichweite bei optimalem (minimalem) Verbrauch — das ist
    # die physikalische Obergrenze, an der Messrauschen nichts mehr aendert.
    min_consumption = vehicle.consumption_l_100km * (1 - FUEL_TOLERANCE)
    if min_consumption <= 0:
        return issues
    max_range_km = vehicle.tank_capacity_l * 100.0 / min_consumption

    trips = _load_all_trips_ordered(database)
    full_tanks: list[Trip] = [
        t for t in trips
        if t.category in ("fuel", "fuel_private")
        and t.fuel_full_tank
        and t.fuel_liters > 0
    ]
    if len(full_tanks) < 2:
        return issues

    partial_fills: list[Trip] = [
        t for t in trips
        if t.category in ("fuel", "fuel_private")
        and not t.fuel_full_tank
        and t.fuel_liters > 0
    ]

    for prev, curr in zip(full_tanks, full_tanks[1:]):
        distance_km = curr.km_end - prev.km_end
        # Teilbetankungen im Intervall erweitern die effektive Reichweite:
        # eine Volltankfuellung plus jede Teilbetankung = zusaetzliche Liter,
        # jeweils bei minimalem Verbrauch in km umgerechnet.
        mid_liters = sum(
            p.fuel_liters for p in partial_fills
            if prev.km_end < p.km_end <= curr.km_end
        )
        effective_max_km = (vehicle.tank_capacity_l + mid_liters) * 100.0 / min_consumption
        if distance_km <= effective_max_km:
            continue
        d = _parse_trip_date(curr)
        issues.append(PlausibilityIssue(
            severity=SEVERITY_ERROR,
            category=CAT_FUEL_RANGE_EXCEEDED,
            message=(
                f"Zwischen Volltank {prev.date} und {curr.date} wurden "
                f"{distance_km} km gefahren — Tank "
                f"({vehicle.tank_capacity_l:.0f} l"
                + (f" + {mid_liters:.2f} l Teilbetankung" if mid_liters > 0 else "")
                + f") reicht maximal ca. {effective_max_km:.0f} km. "
                f"Eine Tankung fehlt oder ein Trip im Intervall ist ueberzaehlig."
            ),
            trip_id=curr.id,
            trip_date=curr.date,
            year=d.year if d else None,
            month=d.month if d else None,
        ))
    return issues


def check_ghost_business_trips(database: Database) -> list[PlausibilityIssue]:
    """Findet Verdachtsfaelle auf doppelt erfasste Geschaeftsfahrten.

    Ghost-Trips sind Geschaeftsfahrten, die im Log stehen, aber nie
    stattgefunden haben — typisches Muster: eine wiederkehrende Route
    (Kunde Nord, Musterstadt) wird aus Gewohnheit nochmal eingetragen. Die km
    stimmen, die Destination stimmt, aber der Tank sagt: "unmoeglich".

    Heuristik: zwei Trips mit
    - identischer normalisierter Destination (erste 50 Zeichen, lower)
    - identischer km_business-Summe
    - km_business >= GHOST_TRIP_MIN_KM (kein Kurzstrecken-Routine-Spam)
    - Abstand <= GHOST_TRIP_WINDOW_DAYS
    werden als INFO gemeldet. Severity INFO weil es legitim sein kann
    (woechentlicher Kundentermin), aber manuelle Pruefung verdient.

    Kombiniert mit check_fuel_range_exceeded ist das der diagnostische
    Hebel: Range-Verletzung = harte Evidenz, Ghost-Liste = Kandidaten.
    """
    issues: list[PlausibilityIssue] = []
    trips = _load_all_trips_ordered(database)
    business_cats = get_business_categories()

    # Nur echte business-Fahrten (ohne fuel/service) mit signifikanten km
    candidates: list[tuple[Trip, date]] = []
    for trip in trips:
        if trip.category != "business":
            continue
        if trip.km_business < GHOST_TRIP_MIN_KM:
            continue
        d = _parse_trip_date(trip)
        if d is None:
            continue
        candidates.append((trip, d))

    # Gruppieren nach (normalisierte destination, km_business)
    groups: dict[tuple[str, int], list[tuple[Trip, date]]] = {}
    for trip, d in candidates:
        key = (trip.destination.strip().lower()[:50], trip.km_business)
        groups.setdefault(key, []).append((trip, d))

    # Fuer jede Gruppe: aufeinanderfolgende Paare im Fenster melden
    reported_ids: set[int] = set()
    for key, entries in groups.items():
        if len(entries) < 2:
            continue
        entries_sorted = sorted(entries, key=lambda x: (x[1], x[0].id))
        for (prev_trip, prev_d), (curr_trip, curr_d) in zip(
            entries_sorted, entries_sorted[1:]
        ):
            delta_days = (curr_d - prev_d).days
            if delta_days <= 0 or delta_days > GHOST_TRIP_WINDOW_DAYS:
                continue
            if curr_trip.id in reported_ids:
                continue
            reported_ids.add(curr_trip.id)
            dest_short = curr_trip.destination.strip()[:40]
            issues.append(PlausibilityIssue(
                severity=SEVERITY_INFO,
                category=CAT_GHOST_BUSINESS_TRIP,
                message=(
                    f"Gleiche Strecke wie Trip am {prev_trip.date} "
                    f"({curr_trip.km_business} km, {dest_short}) — "
                    f"{delta_days} Tage Abstand. Bitte pruefen ob wirklich "
                    f"gefahren."
                ),
                trip_id=curr_trip.id,
                trip_date=curr_trip.date,
                year=curr_d.year,
                month=curr_d.month,
            ))

    return issues


_MONTH_NAMES_DE = [
    "Januar", "Februar", "Maerz", "April", "Mai", "Juni",
    "Juli", "August", "September", "Oktober", "November", "Dezember",
]


# ---------------------------------------------------------------------------
# Gesamt-Report
# ---------------------------------------------------------------------------


def run_all_checks(
    database: Database,
    holidays_by_date: dict[date, str] | None = None,
    skip_checks: set[str] | None = None,
) -> PlausibilityReport:
    """Fuehrt alle Plausi-Checks aus und liefert einen Report.

    Das ist der Einstiegspunkt fuer den "p"-Button in der UI.
    skip_checks: Menge von Check-Kategorie-Namen die uebersprungen werden.
    """
    skip = skip_checks or set()
    report = PlausibilityReport()
    report.issues.extend(check_chain_ascending(database))
    report.issues.extend(check_distance_matches_columns(database))
    report.issues.extend(check_empty_trips(database))
    report.issues.extend(check_category_column_match(database))
    report.issues.extend(check_vehicle_end_limit(database))
    report.issues.extend(check_vehicle_end_reached(database))
    report.issues.extend(check_weekend_business(database))
    if holidays_by_date:
        report.issues.extend(check_holiday_business(database, holidays_by_date))
    report.issues.extend(check_blacklist_business(database))
    report.issues.extend(check_worktime_trip_ratio(database))
    report.issues.extend(check_business_quota(database))
    report.issues.extend(check_fuel_tank_capacity(database))
    report.issues.extend(check_fuel_consumption_range(database))
    report.issues.extend(check_fuel_range_exceeded(database))
    if CAT_GHOST_BUSINESS_TRIP not in skip:
        report.issues.extend(check_ghost_business_trips(database))
    return report


_WEEKDAY_NAMES_DE = [
    "Montag", "Dienstag", "Mittwoch", "Donnerstag",
    "Freitag", "Samstag", "Sonntag",
]


def _weekday_de(d: date) -> str:
    return _WEEKDAY_NAMES_DE[d.weekday()]
