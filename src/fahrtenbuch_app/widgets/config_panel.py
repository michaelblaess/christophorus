"""Konfigurationspanel mit Monatswahl und Fahrzeug-Info."""

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.message import Message
from textual.widgets import Static

from fahrtenbuch_app.models.vehicle import Vehicle

_MONTH_NAMES = [
    "Januar", "Februar", "Maerz", "April", "Mai", "Juni",
    "Juli", "August", "September", "Oktober", "November", "Dezember",
]


class ConfigPanel(Vertical):
    """Zeigt Fahrzeug-Info, Leasingdaten und Monat/Jahr-Navigation."""

    DEFAULT_CSS = """
    ConfigPanel {
        height: auto;
        padding: 0 1;
        background: $surface;
        border: solid $accent;
    }
    ConfigPanel .config-row {
        height: 1;
        layout: horizontal;
    }
    ConfigPanel .config-label {
        width: 14;
        color: $text-muted;
    }
    ConfigPanel .config-value {
        color: $text;
    }
    ConfigPanel .config-spacer {
        width: 1fr;
    }
    ConfigPanel .config-right {
        color: $text-muted;
    }
    ConfigPanel .nav-hint {
        color: $text-muted;
    }
    ConfigPanel #month-display {
        color: $accent;
    }
    """

    class MonthChanged(Message):
        """Wird gesendet wenn der Monat gewechselt wird."""

        def __init__(self, year: int, month: int) -> None:
            super().__init__()
            self.year = year
            self.month = month

    def __init__(
        self,
        vehicle: Vehicle | None,
        year: int,
        month: int,
        fb_path: str = "",
        **kwargs: object,
    ) -> None:
        super().__init__(**kwargs)
        self._vehicle = vehicle
        self._year = year
        self._month = month
        self._fb_path = fb_path

    @property
    def year(self) -> int:
        return self._year

    @property
    def month(self) -> int:
        return self._month

    def compose(self) -> ComposeResult:
        """Erstellt das Layout mit Zeilen fuer Fahrzeug, Leasing und Zeitraum."""
        vehicle = self._vehicle

        # Zeile 1: Fahrzeug
        vehicle_str = f"{vehicle.name}  ({vehicle.plate})" if vehicle and vehicle.name else "[kein Fahrzeug]"
        contract_str = f"Vertrag:  {vehicle.contract_number}" if vehicle and vehicle.contract_number else ""
        with Horizontal(classes="config-row"):
            yield Static("  Fahrzeug:   ", classes="config-label")
            yield Static(vehicle_str, classes="config-value", id="vehicle-display")
            yield Static("", classes="config-spacer")
            yield Static(contract_str, classes="config-right", id="contract-display")

        # Zeile 2: Leasing
        lease_dates = self._format_lease_dates(vehicle)
        km_str = f"{vehicle.lease_km_per_month:,} km/Monat  |  {vehicle.lease_months} Monate".replace(",", ".") if vehicle else ""
        with Horizontal(classes="config-row"):
            yield Static("  Leasing:    ", classes="config-label")
            yield Static(lease_dates, classes="config-value", id="lease-dates-display")
            yield Static("", classes="config-spacer")
            yield Static(km_str, classes="config-right", id="lease-km-display")

        # Zeile 3: Zeitraum
        with Horizontal(classes="config-row"):
            yield Static("  Zeitraum:   ", classes="config-label")
            yield Static(self._format_month(), id="month-display")
            yield Static("", classes="config-spacer")
            yield Static("   [<] Prev  [>] Next", classes="nav-hint")
            if self._fb_path:
                yield Static(f"   {self._fb_path}", classes="config-right", id="path-display")

    def update_vehicle(self, vehicle: Vehicle | None, fb_path: str = "") -> None:
        """Aktualisiert die Fahrzeug-Anzeige."""
        self._vehicle = vehicle
        self._fb_path = fb_path
        try:
            vehicle_str = f"{vehicle.name}  ({vehicle.plate})" if vehicle and vehicle.name else "[kein Fahrzeug]"
            self.query_one("#vehicle-display", Static).update(vehicle_str)

            contract_str = f"Vertrag:  {vehicle.contract_number}" if vehicle and vehicle.contract_number else ""
            self.query_one("#contract-display", Static).update(contract_str)

            self.query_one("#lease-dates-display", Static).update(self._format_lease_dates(vehicle))

            km_str = f"{vehicle.lease_km_per_month:,} km/Monat  |  {vehicle.lease_months} Monate".replace(",", ".") if vehicle else ""
            self.query_one("#lease-km-display", Static).update(km_str)

            try:
                self.query_one("#path-display", Static).update(f"   {fb_path}" if fb_path else "")
            except Exception:
                pass
        except Exception:
            self.refresh()

    def update_month(self, year: int, month: int) -> None:
        """Aktualisiert Jahr und Monat in der Anzeige."""
        self._year = year
        self._month = month
        try:
            self.query_one("#month-display", Static).update(self._format_month())
        except Exception:
            self.refresh()

    def prev_month(self) -> None:
        """Wechselt zum vorherigen Monat."""
        if self._month == 1:
            self._month = 12
            self._year -= 1
        else:
            self._month -= 1
        self._post_month_changed()

    def next_month(self) -> None:
        """Wechselt zum naechsten Monat."""
        if self._month == 12:
            self._month = 1
            self._year += 1
        else:
            self._month += 1
        self._post_month_changed()

    def _post_month_changed(self) -> None:
        """Aktualisiert die Anzeige und sendet MonthChanged."""
        try:
            self.query_one("#month-display", Static).update(self._format_month())
        except Exception:
            self.refresh()
        self.post_message(self.MonthChanged(self._year, self._month))

    def _format_month(self) -> str:
        """Formatiert den aktuellen Monat fuer die Anzeige."""
        return f"< {_MONTH_NAMES[self._month - 1]} {self._year} >"

    def _format_lease_dates(self, vehicle: Vehicle | None) -> str:
        """Formatiert Leasingbeginn und -ende."""
        if not vehicle:
            return ""
        start = self._format_date(vehicle.start_date)
        end = self._format_date(vehicle.end_date)
        if start and end:
            return f"{start} \u2014 {end}"
        if start:
            return f"ab {start}"
        return ""

    def _format_date(self, date_str: str) -> str:
        """Wandelt ISO-Datum (YYYY-MM-DD) in deutsches Format (DD.MM.YYYY) um."""
        if not date_str:
            return ""
        try:
            parts = date_str.split("-")
            if len(parts) == 3:
                return f"{parts[2]}.{parts[1]}.{parts[0]}"
        except Exception:
            pass
        return date_str
