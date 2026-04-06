"""Kalenderansicht mit farbigen Tageskacheln."""

import calendar
from datetime import date

from rich.text import Text
from textual.app import ComposeResult, RenderResult
from textual.containers import Horizontal, Vertical
from textual.widget import Widget

from fahrtenbuch_app.models.trip import MonthData, TripDay

_WEEKDAYS = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]

_TYPE_STYLES: dict[str, str] = {
    "business": "green",
    "fuel": "yellow",
    "service": "magenta",
    "private": "blue",
}


class DayTile(Widget):
    """Einzelne Tageskachel im Kalender."""

    DEFAULT_CSS = """
    DayTile {
        width: 1fr;
        height: 5;
        padding: 0 1;
        border: solid $surface;
    }
    DayTile.weekend {
        background: $surface-darken-2;
        border: solid $surface-darken-1;
    }
    DayTile.holiday {
        background: $surface-darken-2;
        border: solid $warning;
    }
    DayTile.business {
        border: solid green;
    }
    DayTile.private {
        border: solid dodgerblue;
    }
    DayTile.fuel {
        border: solid yellow;
    }
    DayTile.service {
        border: solid magenta;
    }
    DayTile.outside {
        background: $surface-darken-2;
    }
    DayTile.today {
        border: double $accent;
    }
    """

    def __init__(
        self,
        day: date,
        trip_day: TripDay | None = None,
        is_outside: bool = False,
        holiday_name: str = "",
        **kwargs: object,
    ) -> None:
        super().__init__(**kwargs)
        self._date = day
        self._trip_day = trip_day
        self._is_outside = is_outside
        self._holiday_name = holiday_name

    def on_mount(self) -> None:
        """Setzt CSS-Klassen basierend auf Tagtyp."""
        if self._is_outside:
            self.add_class("outside")
        elif self._date.weekday() >= 5:
            self.add_class("weekend")
        elif self._holiday_name:
            self.add_class("holiday")
        elif self._trip_day and self._trip_day.trips:
            self.add_class(self._trip_day.primary_type)

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

        is_weekend = self._date.weekday() >= 5

        if self._holiday_name and self._trip_day and self._trip_day.has_business:
            # Warnung: geschaeftliche Fahrt an Feiertag
            text.append(f"{day_num} {weekday} ", style="bold red")
            text.append("WARNUNG", style="bold red")
            text.append(f"\n{self._holiday_name[:18]}", style="red italic")
            text.append(f"\n{self._trip_day.km_total} km gesch.!", style="bold red")
            return text

        if is_weekend and self._trip_day and self._trip_day.has_business:
            # Warnung: geschaeftliche Fahrt am Wochenende
            text.append(f"{day_num} {weekday} ", style="bold red")
            text.append("WARNUNG", style="bold red")
            text.append(f"\n{self._trip_day.km_total} km gesch.!", style="bold red")
            return text

        if self._holiday_name:
            text.append(f"{day_num} {weekday}", style="dim")
            text.append(f"\n{self._holiday_name[:18]}", style="dim italic")
            if self._trip_day and self._trip_day.trips:
                text.append(f"\n{self._trip_day.km_total} km privat", style="blue")
            return text

        if is_weekend:
            text.append(f"{day_num} {weekday}", style="dim")
            if self._trip_day and self._trip_day.trips:
                text.append(f"\n{self._trip_day.km_total} km privat", style="blue")
            return text

        if self._trip_day and self._trip_day.trips:
            td = self._trip_day
            type_style = _TYPE_STYLES.get(td.primary_type, "dim")
            text.append(f"{day_num} {weekday} ", style="bold")
            text.append(f"{td.km_total} km", style=f"bold {type_style}")
            text.append("\n")
            for trip in td.trips[:2]:
                label = trip.purpose[:18] if trip.purpose else trip.category
                text.append(f"{label}\n", style="dim")
        else:
            text.append(f"{day_num} {weekday}", style="dim")

        return text


class WeekRow(Horizontal):
    """Eine Wochenzeile mit 7 Tageskacheln."""

    DEFAULT_CSS = """
    WeekRow {
        height: 5;
        width: 1fr;
    }
    """


class CalendarView(Vertical):
    """Monatskalender mit farbigen Tageskacheln."""

    DEFAULT_CSS = """
    CalendarView {
        height: 1fr;
        min-height: 10;
        border: solid $accent;
        display: none;
    }
    CalendarView.visible {
        display: block;
    }
    """

    def __init__(self, **kwargs: object) -> None:
        super().__init__(**kwargs)

    def load_data(
        self,
        month_data: MonthData,
        holidays: dict[date, str] | None = None,
    ) -> None:
        """Baut den Kalender fuer den gegebenen Monat."""
        for widget in self.query("WeekRow"):
            widget.remove()

        if holidays is None:
            holidays = {}

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
                tile = DayTile(
                    day=d,
                    trip_day=td,
                    is_outside=is_outside,
                    holiday_name=holiday,
                )
                row.mount(tile)
