"""Konfigurationspanel mit Monatswahl und Fahrzeug-Info."""

from rich.text import Text
from textual.app import RenderResult
from textual.message import Message
from textual.widget import Widget

from fahrtenbuch_app.models.vehicle import Vehicle


class ConfigPanel(Widget):
    """Zeigt Fahrzeug-Info, Fahrtenbuch-Pfad und Monat/Jahr-Navigation."""

    DEFAULT_CSS = """
    ConfigPanel {
        height: 3;
        padding: 0 1;
        background: $surface;
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

    def update_vehicle(self, vehicle: Vehicle | None, fb_path: str = "") -> None:
        """Aktualisiert die Fahrzeug-Anzeige."""
        self._vehicle = vehicle
        self._fb_path = fb_path
        self.refresh()

    def prev_month(self) -> None:
        """Wechselt zum vorherigen Monat."""
        if self._month == 1:
            self._month = 12
            self._year -= 1
        else:
            self._month -= 1
        self.refresh()
        self.post_message(self.MonthChanged(self._year, self._month))

    def next_month(self) -> None:
        """Wechselt zum naechsten Monat."""
        if self._month == 12:
            self._month = 1
            self._year += 1
        else:
            self._month += 1
        self.refresh()
        self.post_message(self.MonthChanged(self._year, self._month))

    def render(self) -> RenderResult:
        """Rendert das Konfigurationspanel."""
        _MONTH_NAMES = [
            "Januar", "Februar", "Maerz", "April", "Mai", "Juni",
            "Juli", "August", "September", "Oktober", "November", "Dezember",
        ]

        text = Text()
        vehicle = self._vehicle
        if vehicle:
            text.append(f"  {vehicle.name}", style="bold")
            text.append(f"  ({vehicle.plate})", style="dim")
            text.append("  |  ", style="dim")
        text.append("< ", style="bold")
        text.append(
            f"{_MONTH_NAMES[self._month - 1]} {self._year}",
            style="bold cyan",
        )
        text.append(" >", style="bold")

        if vehicle:
            text.append("  |  ", style="dim")
            text.append(f"Leasing: {vehicle.lease_km_per_month} km/Monat", style="dim")

        if self._fb_path:
            text.append("  |  ", style="dim")
            text.append(self._fb_path, style="dim italic")

        return text
