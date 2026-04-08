"""Kalender-basierter Datums-Picker mit deutschen Monatsnamen."""

import calendar
from datetime import date

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.events import Click
from textual.message import Message
from textual.screen import ModalScreen
from textual.widgets import Button, Static

_MONTH_NAMES = [
    "Januar", "Februar", "Maerz", "April", "Mai", "Juni",
    "Juli", "August", "September", "Oktober", "November", "Dezember",
]


class _CalendarGrid(Static):
    """Kalender-Grid mit Rich-Text-Rendering und Klick-Erkennung."""

    CELL_WIDTH = 4

    class DayClicked(Message):
        """Wird gesendet wenn ein Tag angeklickt wird."""

        def __init__(self, day: int) -> None:
            super().__init__()
            self.day = day

    def __init__(
        self,
        year: int,
        month: int,
        selected_day: int = 0,
        **kwargs: object,
    ) -> None:
        super().__init__(**kwargs)
        self._year = year
        self._month = month
        self._today = date.today()
        self._selected_day = selected_day
        self._selected_year = year
        self._selected_month = month
        self._weeks: list[list[int]] = []
        self._rebuild_weeks()

    def _rebuild_weeks(self) -> None:
        """Berechnet die Wochen-Matrix fuer den aktuellen Monat."""
        cal = calendar.Calendar(firstweekday=0)
        self._weeks = cal.monthdayscalendar(self._year, self._month)

    def set_month(self, year: int, month: int) -> None:
        """Setzt Monat und Jahr und aktualisiert die Anzeige."""
        self._year = year
        self._month = month
        self._rebuild_weeks()
        self.refresh()

    def render(self) -> Text:
        """Rendert den Kalender als Rich Text."""
        text = Text()
        headers = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]
        for i, wd in enumerate(headers):
            style = "bold #cc8800" if i >= 5 else "bold dim"
            text.append(f" {wd} ", style=style)
        text.append("\n")

        is_today_month = (self._year == self._today.year
                          and self._month == self._today.month)
        show_selected = (self._selected_day > 0
                         and self._year == self._selected_year
                         and self._month == self._selected_month)

        for week in self._weeks:
            for i, day in enumerate(week):
                if day == 0:
                    text.append("    ")
                else:
                    if show_selected and day == self._selected_day:
                        style = "bold reverse"
                    elif is_today_month and day == self._today.day:
                        style = "bold underline #00cccc"
                    elif i >= 5:
                        style = "#cc8800"
                    else:
                        style = ""
                    text.append(f" {day:>2} ", style=style)
            text.append("\n")

        return text

    def on_click(self, event: Click) -> None:
        """Erkennt welcher Tag angeklickt wurde."""
        col = event.x // self.CELL_WIDTH
        row = event.y - 1
        if 0 <= col < 7 and 0 <= row < len(self._weeks):
            day = self._weeks[row][col]
            if day > 0:
                self.post_message(self.DayClicked(day))


class DatePickerScreen(ModalScreen[str | None]):
    """Kalender-Dialog zur Datumsauswahl. Gibt YYYY-MM-DD zurueck."""

    DEFAULT_CSS = """
    DatePickerScreen {
        align: center middle;
    }
    DatePickerScreen > Vertical {
        width: 38;
        height: auto;
        max-height: 20;
        background: $surface;
        border: double $accent;
        padding: 1 2;
    }
    DatePickerScreen #picker-title {
        text-style: bold;
        color: $accent;
        text-align: center;
    }
    DatePickerScreen .nav-row {
        height: 1;
        margin-bottom: 1;
    }
    DatePickerScreen .nav-btn {
        min-width: 3;
        height: 1;
        border: none;
        background: transparent;
        color: $accent;
        padding: 0;
    }
    DatePickerScreen .nav-btn:hover {
        background: $accent 30%;
    }
    DatePickerScreen #month-label {
        width: 1fr;
        text-align: center;
        color: $text;
        text-style: bold;
    }
    DatePickerScreen #cal-grid {
        height: auto;
    }
    DatePickerScreen .today-hint {
        text-align: center;
        color: $text-muted;
        margin-top: 1;
    }
    DatePickerScreen .button-row {
        height: auto;
        align: center middle;
    }
    DatePickerScreen .button-row Button {
        margin: 0 1;
    }
    """

    BINDINGS = [
        Binding("escape", "cancel", "Abbrechen"),
    ]

    def __init__(self, initial_date: str = "", **kwargs: object) -> None:
        super().__init__(**kwargs)
        today = date.today()
        self._today = today
        self._selected_day = 0
        if initial_date:
            try:
                parts = initial_date.split("-")
                self._year = int(parts[0])
                self._month = int(parts[1])
                if len(parts) >= 3 and parts[2]:
                    self._selected_day = int(parts[2])
            except (ValueError, IndexError):
                self._year = today.year
                self._month = today.month
        else:
            self._year = today.year
            self._month = today.month

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static("Datum auswaehlen", id="picker-title")
            with Horizontal(classes="nav-row"):
                yield Button("<<", id="btn-prev-year", classes="nav-btn")
                yield Button("<", id="btn-prev-month", classes="nav-btn")
                yield Static(self._format_month(), id="month-label")
                yield Button(">", id="btn-next-month", classes="nav-btn")
                yield Button(">>", id="btn-next-year", classes="nav-btn")
            yield _CalendarGrid(
                self._year, self._month,
                selected_day=self._selected_day,
                id="cal-grid",
            )
            yield Static(
                f"Heute: {self._today.strftime('%d.%m.%Y')}",
                classes="today-hint",
            )
            with Horizontal(classes="button-row"):
                yield Button("Heute", variant="primary", id="btn-today")
                yield Button("Abbrechen", id="btn-cancel")

    def _format_month(self) -> str:
        """Formatiert Monat und Jahr fuer die Anzeige."""
        return f"{_MONTH_NAMES[self._month - 1]} {self._year}"

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Reagiert auf Navigation."""
        btn_id = event.button.id or ""
        if btn_id == "btn-prev-month":
            if self._month == 1:
                self._month = 12
                self._year -= 1
            else:
                self._month -= 1
            self._update_calendar()
        elif btn_id == "btn-next-month":
            if self._month == 12:
                self._month = 1
                self._year += 1
            else:
                self._month += 1
            self._update_calendar()
        elif btn_id == "btn-prev-year":
            self._year -= 1
            self._update_calendar()
        elif btn_id == "btn-next-year":
            self._year += 1
            self._update_calendar()
        elif btn_id == "btn-today":
            self.dismiss(self._today.strftime("%Y-%m-%d"))
        elif btn_id == "btn-cancel":
            self.dismiss(None)

    def _update_calendar(self) -> None:
        """Aktualisiert Kalender und Monatslabel."""
        self.query_one("#month-label", Static).update(self._format_month())
        self.query_one("#cal-grid", _CalendarGrid).set_month(
            self._year, self._month,
        )

    def on__calendar_grid_day_clicked(self, event: _CalendarGrid.DayClicked) -> None:
        """Reagiert auf Klick auf einen Tag."""
        selected = f"{self._year}-{self._month:02d}-{event.day:02d}"
        self.dismiss(selected)

    def action_cancel(self) -> None:
        """Bricht ab."""
        self.dismiss(None)
