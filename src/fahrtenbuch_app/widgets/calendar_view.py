"""Kalenderansicht mit farbigen Tageskacheln."""

import calendar
from datetime import date

from rich.text import Text
from textual.app import ComposeResult, RenderResult
from textual.containers import Horizontal, Vertical
from textual.events import Click
from textual.message import Message
from textual.widget import Widget

from fahrtenbuch_app.models.trip import MonthData, Trip, TripDay
from fahrtenbuch_app.services.formatting import format_km

_WEEKDAYS = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]

# Reduziertes Farbschema: gruen fuer geschaeftlich, rot fuer Blacklist /
# Warnungen, alles andere neutral.
_STYLE_BUSINESS = "green"
_STYLE_ERROR = "bold red"
_STYLE_MUTED = "dim"
_STYLE_HOLIDAY = "yellow"
_STYLE_HOLIDAY_BOLD = "bold yellow"


class DayTile(Widget):
    """Einzelne Tageskachel im Kalender."""

    DEFAULT_CSS = """
    DayTile {
        width: 1fr;
        height: 7;
        padding: 0 1;
        border: solid $surface;
    }
    DayTile.weekend {
        background: $surface-darken-2;
        border: solid $surface-darken-1;
    }
    DayTile.holiday {
        background: $surface-darken-2;
        border: solid yellow;
    }
    DayTile.business {
        border: solid green;
    }
    DayTile.fuel {
        border: solid yellow;
    }
    DayTile.outside {
        background: $surface-darken-2;
    }
    DayTile.today {
        border: double $accent;
    }
    DayTile.blacklisted {
        border: double red;
        background: $surface-darken-3;
    }
    """

    def __init__(
        self,
        day: date,
        trip_day: TripDay | None = None,
        is_outside: bool = False,
        holiday_name: str = "",
        blacklist_reason: str = "",
        **kwargs: object,
    ) -> None:
        super().__init__(**kwargs)
        self._date = day
        self._trip_day = trip_day
        self._is_outside = is_outside
        self._holiday_name = holiday_name
        self._blacklist_reason = blacklist_reason

    def on_mount(self) -> None:
        """Setzt CSS-Klassen basierend auf Tagtyp."""
        if self._is_outside:
            self.add_class("outside")
        elif self._blacklist_reason:
            self.add_class("blacklisted")
        elif self._date.weekday() >= 5:
            self.add_class("weekend")
        elif self._holiday_name:
            self.add_class("holiday")
        elif self._trip_day and self._trip_day.has_business:
            self.add_class("business")

        # Tanktage gelb markieren — unabhaengig von weekend/holiday/business,
        # damit auch Samstags-Tankungen sichtbar sind.
        if not self._is_outside and self._trip_day and self._trip_day.has_fuel:
            self.add_class("fuel")

        if self._date == date.today():
            self.add_class("today")

    def render(self) -> RenderResult:
        """Rendert den Inhalt der Tageskachel."""
        text = Text()
        day_num = str(self._date.day)
        weekday = _WEEKDAYS[self._date.weekday()]

        if self._is_outside:
            text.append(f"{day_num} {weekday}", style="dim")
            return text

        # Blacklist: rot mit Grund anzeigen
        if self._blacklist_reason:
            text.append(f"{day_num} {weekday} ", style=_STYLE_ERROR)
            text.append("GESPERRT\n", style=_STYLE_ERROR)
            text.append(self._blacklist_reason, style="red italic")
            if self._trip_day and self._trip_day.has_business:
                text.append(f"\n{format_km(self._trip_day.km_total)} km gesch.!", style=_STYLE_ERROR)
            elif self._trip_day and self._trip_day.trips:
                text.append(f"\n{format_km(self._trip_day.km_total)} km", style=_STYLE_MUTED)
            return text

        is_weekend = self._date.weekday() >= 5

        if self._holiday_name and self._trip_day and self._trip_day.has_business:
            text.append(f"{day_num} {weekday} ", style=_STYLE_ERROR)
            text.append("WARNUNG", style=_STYLE_ERROR)
            text.append(f"\n{self._holiday_name[:22]}", style="red italic")
            text.append(f"\n{format_km(self._trip_day.km_total)} km gesch.!", style=_STYLE_ERROR)
            return text

        if is_weekend and self._trip_day and self._trip_day.has_business:
            text.append(f"{day_num} {weekday} ", style=_STYLE_ERROR)
            text.append("WARNUNG", style=_STYLE_ERROR)
            text.append(f"\n{format_km(self._trip_day.km_total)} km gesch.!", style=_STYLE_ERROR)
            return text

        if self._holiday_name:
            text.append(f"{day_num} {weekday}", style=_STYLE_HOLIDAY_BOLD)
            text.append(f"\n{self._holiday_name[:22]}", style=_STYLE_HOLIDAY)
            if self._trip_day and self._trip_day.trips:
                text.append(f"\n{format_km(self._trip_day.km_total)} km privat", style=_STYLE_MUTED)
                if self._trip_day.fuel_liters > 0:
                    text.append(f"  {self._trip_day.fuel_liters:.0f}L", style="bold yellow")
            return text

        if is_weekend:
            text.append(f"{day_num} {weekday}", style=_STYLE_MUTED)
            if self._trip_day and self._trip_day.trips:
                text.append(f"\n{format_km(self._trip_day.km_total)} km privat", style=_STYLE_MUTED)
                if self._trip_day.fuel_liters > 0:
                    text.append(f"  {self._trip_day.fuel_liters:.0f}L", style="bold yellow")
            return text

        if self._trip_day and self._trip_day.trips:
            td = self._trip_day
            # Gruen nur bei geschaeftlich, sonst neutral
            km_style = _STYLE_BUSINESS if td.has_business else _STYLE_MUTED
            text.append(f"{day_num} {weekday} ", style="bold")
            text.append(f"{format_km(td.km_total)} km", style=f"bold {km_style}")
            if td.fuel_liters > 0:
                text.append(f"  {td.fuel_liters:.0f}L", style="bold yellow")
            text.append("\n")
            for trip in td.trips[:2]:
                label = trip.purpose[:22] if trip.purpose else trip.category
                text.append(f"{label}\n", style=_STYLE_MUTED)
        else:
            text.append(f"{day_num} {weekday}", style=_STYLE_MUTED)

        return text

    def on_click(self, event: Click) -> None:
        """Klick: Trip bearbeiten. Doppelklick auf leere Kachel: neue Fahrt."""
        if self._is_outside:
            return
        if self._trip_day and self._trip_day.trips:
            self.post_message(CalendarView.TripEditRequested(self._trip_day.trips[0]))
        elif event.chain > 1:
            self.post_message(CalendarView.NewTripRequested(self._date))


class WeekRow(Horizontal):
    """Eine Wochenzeile mit 7 Tageskacheln."""

    DEFAULT_CSS = """
    WeekRow {
        height: 7;
        width: 1fr;
    }
    """


class CalendarView(Vertical):
    """Monatskalender mit farbigen Tageskacheln."""

    class TripEditRequested(Message):
        """Wird gesendet wenn der Benutzer einen Trip im Kalender anklickt."""

        def __init__(self, trip: Trip) -> None:
            super().__init__()
            self.trip = trip

    class NewTripRequested(Message):
        """Wird gesendet bei Doppelklick auf eine leere Kalender-Kachel."""

        def __init__(self, day: date) -> None:
            super().__init__()
            self.day = day

    DEFAULT_CSS = """
    CalendarView {
        height: 1fr;
        min-height: 10;
        border: solid $accent;
    }
    """

    def __init__(self, **kwargs: object) -> None:
        super().__init__(**kwargs)
        self._last_month_data: MonthData | None = None
        self._last_holidays: dict[date, str] = {}
        self._blacklist_map: dict[date, str] = {}
        self._show_blacklist: bool = False

    def load_data(
        self,
        month_data: MonthData,
        holidays: dict[date, str] | None = None,
        category_colors: dict[str, str] | None = None,
        blacklist_map: dict[date, str] | None = None,
    ) -> None:
        """Baut den Kalender fuer den gegebenen Monat.

        Args:
            month_data: Monatsdaten mit Fahrten.
            holidays: Feiertage im Monat.
            category_colors: Unbenutzt (Legacy, bleibt fuer API-Kompatibilitaet).
            blacklist_map: Gesperrte Tage (date -> Grund). Aktualisiert internen Stand.
        """
        del category_colors
        self._last_month_data = month_data
        self._last_holidays = holidays if holidays is not None else {}
        if blacklist_map is not None:
            self._blacklist_map = blacklist_map
        self._build_tiles()

    def toggle_blacklist(self) -> bool:
        """Schaltet Blacklist-Markierung ein/aus. Gibt neuen Status zurueck."""
        self._show_blacklist = not self._show_blacklist
        self._build_tiles()
        return self._show_blacklist

    @property
    def blacklist_visible(self) -> bool:
        return self._show_blacklist

    def _build_tiles(self) -> None:
        """Baut alle Tageskacheln neu auf."""
        for widget in self.query("WeekRow"):
            widget.remove()

        if self._last_month_data is None:
            return

        month_data = self._last_month_data
        holidays = self._last_holidays
        active_blacklist = self._blacklist_map if self._show_blacklist else {}

        trip_days = {td.day: td for td in month_data.trip_days}
        year = month_data.year
        month = month_data.month
        cal = calendar.Calendar(firstweekday=0)
        weeks = cal.monthdatescalendar(year, month)

        for week in weeks:
            row = WeekRow()
            self.mount(row)
            for d in week:
                is_outside = d.month != month
                td = trip_days.get(d) if not is_outside else None
                holiday = holidays.get(d, "") if not is_outside else ""
                bl_reason = active_blacklist.get(d, "") if not is_outside else ""
                tile = DayTile(
                    day=d,
                    trip_day=td,
                    is_outside=is_outside,
                    holiday_name=holiday,
                    blacklist_reason=bl_reason,
                )
                row.mount(tile)
