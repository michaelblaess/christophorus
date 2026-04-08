"""Fahrten-Tabelle (Hauptansicht)."""

from datetime import date

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.message import Message
from textual.widgets import DataTable

from fahrtenbuch_app.models.trip import MonthData, Trip

_WEEKDAYS = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]

_DEFAULT_CATEGORY_STYLES: dict[str, str] = {
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

    class BlacklistEntryActivated(Message):
        """Wird gesendet wenn eine Blacklist-Nur-Zeile ausgewaehlt wird."""

        def __init__(self, entry_id: int, date_str: str, reason: str) -> None:
            super().__init__()
            self.entry_id = entry_id
            self.date_str = date_str
            self.reason = reason

    def __init__(self, **kwargs: object) -> None:
        super().__init__(**kwargs)
        self._row_trips: dict[str, tuple[Trip | None, int]] = {}
        self._bl_only_rows: dict[str, tuple[int, str, str]] = {}  # row_key → (id, date_str, reason)
        self._last_month_data: MonthData | None = None
        self._last_holidays_map: dict[date, str] = {}
        self._last_category_colors: dict[str, str] | None = None
        self._blacklist_map: dict[date, str] = {}
        self._blacklist_entries_by_date: dict[date, dict[str, object]] = {}
        self._show_blacklist: bool = False

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
        category_colors: dict[str, str] | None = None,
        blacklist_map: dict[date, str] | None = None,
        blacklist_entries: list[dict[str, object]] | None = None,
    ) -> None:
        """Laedt die Fahrten in die Tabelle."""
        self._last_month_data = month_data
        self._last_holidays_map = holidays_map if holidays_map is not None else {}
        self._last_category_colors = category_colors
        if blacklist_map is not None:
            self._blacklist_map = blacklist_map
        if blacklist_entries is not None:
            self._blacklist_entries_by_date = {}
            for entry in blacklist_entries:
                date_str = str(entry.get("date", ""))
                try:
                    parts = date_str.split("-")
                    d = date(int(parts[0]), int(parts[1]), int(parts[2]))
                    self._blacklist_entries_by_date[d] = entry
                except (ValueError, IndexError):
                    pass
        self._build_rows()

    def toggle_blacklist(self) -> bool:
        """Schaltet Blacklist-Markierung ein/aus. Gibt neuen Status zurueck."""
        self._show_blacklist = not self._show_blacklist
        self._build_rows()
        return self._show_blacklist

    @property
    def blacklist_visible(self) -> bool:
        return self._show_blacklist

    def _build_rows(self) -> None:
        """Baut alle Tabellenzeilen neu auf."""
        table = self.query_one("#trip-data", DataTable)
        table.clear()
        self._row_trips.clear()
        self._bl_only_rows.clear()

        if self._last_month_data is None:
            return

        month_data = self._last_month_data
        holidays_map = self._last_holidays_map
        styles = self._last_category_colors if self._last_category_colors else _DEFAULT_CATEGORY_STYLES
        active_blacklist = self._blacklist_map if self._show_blacklist else {}

        # Sammle Trip-Daten mit Datum fuer spaeters Sortieren
        trip_dates: set[date] = set()
        trip_rows: list[tuple[date, str, Trip, int]] = []  # (date, date_str, trip, original_idx)
        for idx, trip in enumerate(month_data.trips):
            try:
                parts = trip.date.split("-")
                d = date(int(parts[0]), int(parts[1]), int(parts[2]))
                trip_rows.append((d, trip.date, trip, idx))
                trip_dates.add(d)
            except (ValueError, IndexError):
                trip_rows.append((date(9999, 1, 1), trip.date, trip, idx))

        # Blacklist-Nur-Eintraege fuer den aktuellen Monat (Tage ohne Trip)
        bl_only_rows: list[tuple[date, dict[str, object]]] = []
        if self._show_blacklist:
            for d, entry in self._blacklist_entries_by_date.items():
                if d.year == month_data.year and d.month == month_data.month:
                    if d not in trip_dates:
                        bl_only_rows.append((d, entry))

        # Kombiniert sortieren nach Datum
        combined: list[tuple[date, str, str, Trip | None, int, dict[str, object] | None]] = []
        for d, date_str, trip, idx in trip_rows:
            combined.append((d, date_str, "trip", trip, idx, None))
        for d, entry in bl_only_rows:
            combined.append((d, str(entry.get("date", "")), "blacklist", None, -1, entry))
        combined.sort(key=lambda x: x[0])

        row_idx = 0
        for d, date_str, row_type, trip, orig_idx, entry in combined:
            date_de = d.strftime("%d.%m.%Y") if d.year != 9999 else date_str
            weekday = _WEEKDAYS[d.weekday()] if d.year != 9999 else ""
            row_key = str(row_idx)

            if row_type == "blacklist" and entry is not None:
                # Blacklist-Nur-Zeile: kein Trip, nur Grund
                reason = str(entry.get("reason", ""))
                entry_id = int(entry.get("id", 0))
                table.add_row(
                    Text(date_de, style="bold red"),
                    Text(weekday, style="bold red"),
                    Text("", style="dim"),
                    Text("", style="dim"),
                    Text(f"[GESPERRT: {reason}]", style="bold red"),
                    Text("", style="dim"),
                    Text("", style="dim"),
                    Text("", style="dim"),
                    Text("", style="dim"),
                    key=row_key,
                )
                self._bl_only_rows[row_key] = (entry_id, date_str, reason)
            else:
                # Normaler Trip
                assert trip is not None
                time_str = ""
                if trip.time_from and trip.time_to:
                    time_str = f"{trip.time_from} - {trip.time_to}"
                elif trip.time_from:
                    time_str = trip.time_from

                dest_short = trip.destination.split("\n")[0] if trip.destination else ""
                if len(dest_short) > 40:
                    dest_short = f"{dest_short[:37]}..."

                style = styles.get(trip.category, "")
                warning = ""

                # Blacklist-Tag pruefen
                bl_reason = active_blacklist.get(d, "")
                if bl_reason:
                    warning = f"GESPERRT: {bl_reason}"
                    style = "bold red"

                # Feiertag / Wochenende (nur wenn kein Blacklist-Eintrag)
                if not warning and trip.is_business_km:
                    holiday_name = holidays_map.get(d, "")
                    if holiday_name:
                        warning = f"FEIERTAG: {holiday_name}"
                        style = "bold red"
                    elif d.weekday() >= 5:
                        warning = "WOCHENENDE"
                        style = "bold red"

                purpose_text = f"{trip.purpose} [{warning}]" if warning else trip.purpose

                table.add_row(
                    Text(date_de, style=style),
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
                self._row_trips[row_key] = (trip, orig_idx)

            row_idx += 1

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Sendet TripSelected oder BlacklistEntryActivated je nach Zeilentyp."""
        row_key = str(event.row_key.value) if event.row_key else ""

        # Blacklist-Nur-Zeile?
        if row_key in self._bl_only_rows:
            entry_id, date_str, reason = self._bl_only_rows[row_key]
            self.post_message(self.BlacklistEntryActivated(entry_id, date_str, reason))
            return

        # Normaler Trip
        trip_data = self._row_trips.get(row_key, (None, -1))
        self.post_message(self.TripSelected(trip_data[0], trip_data[1]))
