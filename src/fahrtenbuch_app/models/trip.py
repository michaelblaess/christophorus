"""Fahrt-Modelle fuer das Fahrtenbuch."""

from dataclasses import dataclass, field
from datetime import date

# Kategorien die als geschaeftliche Kilometer zaehlen
BUSINESS_CATEGORIES = frozenset({"business", "fuel", "service"})


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

    @property
    def km_total(self) -> int:
        """Gesamte gefahrene Kilometer dieser Fahrt."""
        return self.km_business + self.km_private

    @property
    def is_business_km(self) -> bool:
        """Ob die km dieser Fahrt als geschaeftlich zaehlen.

        business, fuel und service zaehlen als geschaeftliche Kilometer.
        """
        return self.category in BUSINESS_CATEGORIES


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
