"""Fahrten-Tabelle (Hauptansicht)."""

from datetime import date

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.message import Message
from textual.widgets import DataTable

from fahrtenbuch_app.models.trip import MonthData, Trip

_WEEKDAYS = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]

_CATEGORY_STYLES: dict[str, str] = {
    "business": "green",
    "fuel": "yellow",
    "service": "magenta",
    "private": "blue",
}


class TripTable(Vertical):
    """DataTable mit allen Fahrten eines Monats."""

    DEFAULT_CSS = """
    TripTable {
        height: 1fr;
    }
    TripTable DataTable {
        height: 1fr;
    }
    """

    class TripSelected(Message):
        """Wird gesendet wenn eine Fahrt ausgewaehlt wird."""

        def __init__(self, trip: Trip | None, index: int) -> None:
            super().__init__()
            self.trip = trip
            self.index = index

    def __init__(self, **kwargs: object) -> None:
        super().__init__(**kwargs)
        self._row_trips: dict[str, tuple[Trip | None, int]] = {}

    def compose(self) -> ComposeResult:
        yield DataTable(id="trip-data", cursor_type="row", zebra_stripes=True)

    def on_mount(self) -> None:
        """Tabellenspalten erstellen."""
        table = self.query_one("#trip-data", DataTable)
        table.add_columns(
            "Datum", "Tag", "Fahrzeit", "Ziel", "Reisezweck",
            "km Anfang", "km Ende", "geschaeftl.", "privat",
        )

    def load_data(
        self,
        month_data: MonthData,
        holidays_map: dict[date, str] | None = None,
    ) -> None:
        """Laedt die Fahrten in die Tabelle."""
        table = self.query_one("#trip-data", DataTable)
        table.clear()
        self._row_trips.clear()
        if holidays_map is None:
            holidays_map = {}

        row_idx = 0
        for idx, trip in enumerate(month_data.trips):
            try:
                parts = trip.date.split("-")
                d = date(int(parts[0]), int(parts[1]), int(parts[2]))
                date_str = d.strftime("%d.%m.%Y")
                weekday = _WEEKDAYS[d.weekday()]
            except (ValueError, IndexError):
                date_str = trip.date
                weekday = ""
                d = None

            time_str = ""
            if trip.time_from and trip.time_to:
                time_str = f"{trip.time_from} - {trip.time_to}"
            elif trip.time_from:
                time_str = trip.time_from

            dest_short = trip.destination.split("\n")[0] if trip.destination else ""
            if len(dest_short) > 40:
                dest_short = f"{dest_short[:37]}..."

            style = _CATEGORY_STYLES.get(trip.category, "")

            # Warnung: geschaeftliche Fahrt an Feiertag oder Wochenende
            warning = ""
            if d is not None and trip.is_business_km:
                holiday_name = holidays_map.get(d, "")
                if holiday_name:
                    warning = f"FEIERTAG: {holiday_name}"
                    style = "bold red"
                elif d.weekday() >= 5:
                    warning = "WOCHENENDE"
                    style = "bold red"

            purpose_text = trip.purpose
            if warning:
                purpose_text = f"{trip.purpose} [{warning}]"

            row_key = str(row_idx)
            table.add_row(
                Text(date_str, style=style),
                Text(weekday, style="dim" if not warning else "bold red"),
                Text(time_str, style="dim"),
                Text(dest_short),
                Text(purpose_text, style=style),
                Text(str(trip.km_start), style="dim"),
                Text(str(trip.km_end), style="dim"),
                Text(str(trip.km_business) if trip.km_business > 0 else "", style="green" if not warning else "bold red"),
                Text(str(trip.km_private) if trip.km_private > 0 else "", style="blue"),
                key=row_key,
            )
            self._row_trips[row_key] = (trip, idx)
            row_idx += 1

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Sendet TripSelected wenn eine Zeile ausgewaehlt wird."""
        row_key = str(event.row_key.value) if event.row_key else ""
        trip_data = self._row_trips.get(row_key, (None, -1))
        self.post_message(self.TripSelected(trip_data[0], trip_data[1]))
