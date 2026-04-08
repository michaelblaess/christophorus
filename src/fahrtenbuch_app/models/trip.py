"""Fahrt-Modelle fuer das Fahrtenbuch."""

from dataclasses import dataclass, field
from datetime import date

# Konfigurierbare Kategorien die als geschaeftliche Kilometer zaehlen.
# Wird beim Oeffnen eines Fahrtenbuchs aus der DB gesetzt.
_business_categories: set[str] = {"business", "fuel", "service"}


def set_business_categories(categories: set[str]) -> None:
    """Setzt die Kategorien die als geschaeftlich zaehlen.

    Wird beim Oeffnen eines Fahrtenbuchs aus der DB geladen.
    """
    global _business_categories
    _business_categories = categories


def get_business_categories() -> set[str]:
    """Gibt die aktuell konfigurierten Business-Kategorien zurueck."""
    return _business_categories


@dataclass
class Trip:
    """Einzelne Fahrt im Fahrtenbuch."""

    id: int = 0
    date: str = ""
    time_from: str = ""
    time_to: str = ""
    destination: str = ""
    purpose: str = ""
    km_start: int = 0
    km_end: int = 0
    km_business: int = 0
    km_private: int = 0
    category: str = "business"
    round_trip: bool = False

    @property
    def km_total(self) -> int:
        """Gesamte gefahrene Kilometer dieser Fahrt."""
        return self.km_business + self.km_private

    @property
    def is_business_km(self) -> bool:
        """Ob die km dieser Fahrt als geschaeftlich zaehlen.

        Prueft gegen die aus der DB konfigurierten Kategorien.
        """
        return self.category in _business_categories


@dataclass
class TripDay:
    """Alle Fahrten an einem Tag."""

    day: date
    trips: list[Trip] = field(default_factory=list)

    @property
    def km_business(self) -> int:
        """Geschaeftliche Kilometer an diesem Tag."""
        return sum(t.km_business for t in self.trips if t.is_business_km)

    @property
    def km_private(self) -> int:
        """Private Kilometer an diesem Tag."""
        return sum(t.km_private for t in self.trips) + sum(
            t.km_business for t in self.trips if not t.is_business_km
        )

    @property
    def km_total(self) -> int:
        """Gesamte Kilometer an diesem Tag."""
        return sum(t.km_total for t in self.trips)

    @property
    def has_business(self) -> bool:
        """Gibt es geschaeftliche Fahrten an diesem Tag."""
        return any(t.category == "business" for t in self.trips)

    @property
    def has_fuel(self) -> bool:
        """Gibt es Tankfahrten an diesem Tag."""
        return any(t.category == "fuel" for t in self.trips)

    @property
    def has_service(self) -> bool:
        """Gibt es Service-Fahrten an diesem Tag."""
        return any(t.category == "service" for t in self.trips)

    @property
    def primary_type(self) -> str:
        """Haupttyp des Tages (fuer Farbcodierung)."""
        if self.has_business:
            return "business"
        if self.has_service:
            return "service"
        if self.has_fuel:
            return "fuel"
        return "private"


@dataclass
class MonthData:
    """Zusammenfassung fuer einen Monat."""

    year: int
    month: int
    trips: list[Trip] = field(default_factory=list)

    @property
    def km_business(self) -> int:
        """Geschaeftliche Kilometer im Monat (business + fuel + service)."""
        return sum(t.km_business for t in self.trips if t.is_business_km)

    @property
    def km_private(self) -> int:
        """Private Kilometer im Monat."""
        return sum(t.km_private for t in self.trips) + sum(
            t.km_business for t in self.trips if not t.is_business_km
        )

    @property
    def km_total(self) -> int:
        """Gesamte Kilometer im Monat."""
        return sum(t.km_total for t in self.trips)

    @property
    def business_percentage(self) -> float:
        """Geschaeftlicher Anteil in Prozent."""
        if self.km_total == 0:
            return 0.0
        return self.km_business / self.km_total * 100

    @property
    def trip_days(self) -> list[TripDay]:
        """Gruppiert Fahrten nach Datum."""
        days: dict[str, list[Trip]] = {}
        for trip in self.trips:
            if trip.date not in days:
                days[trip.date] = []
            days[trip.date].append(trip)

        result = []
        for date_str in sorted(days.keys()):
            try:
                parts = date_str.split("-")
                d = date(int(parts[0]), int(parts[1]), int(parts[2]))
            except (ValueError, IndexError):
                continue
            result.append(TripDay(day=d, trips=days[date_str]))
        return result
