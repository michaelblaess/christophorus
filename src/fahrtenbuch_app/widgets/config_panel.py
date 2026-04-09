"""Konfigurationspanel mit Monatswahl und Fahrzeug-Info."""

import os
import subprocess
import sys

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.message import Message
from textual.widgets import Button, Static

from fahrtenbuch_app.models.vehicle import Vehicle
from fahrtenbuch_app.services.formatting import format_km

_MONTH_NAMES = [
    "Januar", "Februar", "Maerz", "April", "Mai", "Juni",
    "Juli", "August", "September", "Oktober", "November", "Dezember",
]


class ConfigPanel(Vertical):
    """Zeigt Fahrzeug-Info, Leasingdaten, Monat/Jahr-Navigation und Verzeichnis."""

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
    ConfigPanel #path-display {
        width: 1fr;
        color: $text-muted;
    }
    ConfigPanel #btn-open-dir {
        height: 1;
        min-width: 10;
        border: none;
        background: transparent;
        color: $accent;
        padding: 0 1;
    }
    ConfigPanel #btn-open-dir:hover {
        background: $accent 20%;
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
        """Erstellt das Layout mit Zeilen fuer Fahrzeug, Leasing, Zeitraum und Verzeichnis."""
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
        km_str = f"{format_km(vehicle.lease_km_per_month)} km/Monat  |  {vehicle.lease_months} Monate" if vehicle else ""
        with Horizontal(classes="config-row"):
            yield Static("  Leasing:    ", classes="config-label")
            yield Static(lease_dates, classes="config-value", id="lease-dates-display")
            yield Static("", classes="config-spacer")
            yield Static(km_str, classes="config-right", id="lease-km-display")

        # Zeile 3: Kilometerstand (vehicle.start_km -> vehicle.end_km)
        km_range = self._format_km_range(vehicle)
        km_total = self._format_km_total(vehicle)
        with Horizontal(classes="config-row"):
            yield Static("  km-Stand:   ", classes="config-label")
            yield Static(km_range, classes="config-value", id="km-range-display")
            yield Static("", classes="config-spacer")
            yield Static(km_total, classes="config-right", id="km-total-display")

        # Zeile 4: Zeitraum
        with Horizontal(classes="config-row"):
            yield Static("  Zeitraum:   ", classes="config-label")
            yield Static(self._format_month(), id="month-display")
            yield Static("", classes="config-spacer")
            yield Static("   [<] Prev  [>] Next", classes="nav-hint")

        # Zeile 4: Verzeichnis
        with Horizontal(classes="config-row"):
            yield Static("  Verzeichnis:", classes="config-label")
            yield Static(self._fb_path or "", id="path-display")
            yield Button("\u2197 Oeffnen", id="btn-open-dir", disabled=not bool(self._fb_path))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Oeffnet das Fahrtenbuch-Verzeichnis im Datei-Explorer."""
        if event.button.id != "btn-open-dir" or not self._fb_path:
            return
        event.stop()
        _open_directory(self._fb_path)

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

            km_str = f"{format_km(vehicle.lease_km_per_month)} km/Monat  |  {vehicle.lease_months} Monate" if vehicle else ""
            self.query_one("#lease-km-display", Static).update(km_str)

            self.query_one("#km-range-display", Static).update(self._format_km_range(vehicle))
            self.query_one("#km-total-display", Static).update(self._format_km_total(vehicle))

            self.query_one("#path-display", Static).update(fb_path or "")
            btn = self.query_one("#btn-open-dir", Button)
            btn.disabled = not bool(fb_path)
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

    def _format_km_range(self, vehicle: Vehicle | None) -> str:
        """Formatiert Anfangs- und Endkilometerstand des Fahrzeugs."""
        if not vehicle:
            return ""
        return f"{format_km(vehicle.start_km)} km \u2014 {format_km(vehicle.end_km)} km"

    def _format_km_total(self, vehicle: Vehicle | None) -> str:
        """Formatiert die Gesamt-Laufleistung (end_km - start_km)."""
        if not vehicle:
            return ""
        return f"{format_km(vehicle.total_driven_km)} km gesamt"

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


def _open_directory(path: str) -> None:
    """Oeffnet ein Verzeichnis im nativen Datei-Explorer."""
    try:
        if sys.platform == "win32":
            os.startfile(path)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", path])
        else:
            subprocess.Popen(["xdg-open", path])
    except Exception:
        pass
