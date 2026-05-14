"""Fahrten-Tabelle (Hauptansicht)."""

from datetime import date

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.message import Message
from textual.widgets import DataTable

from fahrtenbuch_app.models.trip import MonthData, Trip
from fahrtenbuch_app.services.formatting import format_km

_WEEKDAYS = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]

# Reduziertes Farbschema: ausschliesslich Gruen (geschaeftlich) und Rot
# (Blacklist / Feiertag / Wochenende). Alles andere bleibt neutral.
_STYLE_BUSINESS = "green"
_STYLE_ERROR = "bold red"
_STYLE_MUTED = "dim"
_STYLE_DEFAULT = ""


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
        self._year_mode: bool = False
        self._problem_trip_ids: set[int] = set()
        self._show_id: bool = False
        self._show_code: bool = False
        self._show_fuel: bool = False
        self._category_codes: dict[str, str] = {}

    def compose(self) -> ComposeResult:
        yield DataTable(id="trip-data", cursor_type="row", zebra_stripes=True)

    def on_mount(self) -> None:
        """Tabellenspalten erstellen."""
        self._setup_columns()

    def _setup_columns(self) -> None:
        """Legt die Spalten an (optional mit ID-Spalte am Anfang).

        Ziel-Spalte hat eine feste Breite, damit lange Adressen sichtbar
        bleiben.
        """
        table = self.query_one("#trip-data", DataTable)
        if self._show_id:
            table.add_column("ID", key="id", width=5)
        if self._show_code:
            table.add_column("Kat", key="code", width=4)
        table.add_column("Datum", key="date")
        table.add_column("Tag", key="weekday")
        table.add_column("Fahrzeit", key="time")
        table.add_column("Ziel", key="destination", width=80)
        table.add_column("Reisezweck", key="purpose")
        if self._show_fuel:
            table.add_column("Liter", key="fuel", width=8)
        table.add_column("km Anfang", key="km_start")
        table.add_column("km Ende", key="km_end")
        table.add_column("geschaeftl.", key="km_business")
        table.add_column("privat", key="km_private")

    def set_show_id(self, value: bool) -> None:
        """Schaltet die ID-Spalte ein/aus. Spalten werden neu aufgebaut."""
        if self._show_id == value:
            return
        self._show_id = value
        try:
            table = self.query_one("#trip-data", DataTable)
        except Exception:
            return
        table.clear(columns=True)
        self._setup_columns()
        if self._last_month_data is not None:
            self._build_rows()

    def set_show_code(self, value: bool) -> None:
        """Schaltet die Kategorie-Code-Spalte ein/aus."""
        if self._show_code == value:
            return
        self._show_code = value
        try:
            table = self.query_one("#trip-data", DataTable)
        except Exception:
            return
        table.clear(columns=True)
        self._setup_columns()
        if self._last_month_data is not None:
            self._build_rows()

    def set_show_fuel(self, value: bool) -> None:
        """Schaltet die Tankliter-Spalte ein/aus."""
        if self._show_fuel == value:
            return
        self._show_fuel = value
        try:
            table = self.query_one("#trip-data", DataTable)
        except Exception:
            return
        table.clear(columns=True)
        self._setup_columns()
        if self._last_month_data is not None:
            self._build_rows()

    def set_category_codes(self, codes: dict[str, str]) -> None:
        """Setzt das Mapping Kategorie-Name -> Code (G/P/T)."""
        self._category_codes = codes

    def load_data(
        self,
        month_data: MonthData,
        holidays_map: dict[date, str] | None = None,
        category_colors: dict[str, str] | None = None,
        blacklist_map: dict[date, str] | None = None,
        blacklist_entries: list[dict[str, object]] | None = None,
        year_mode: bool = False,
    ) -> None:
        """Laedt die Fahrten in die Tabelle.

        year_mode=True: Alle Fahrten eines Jahres anzeigen, Blacklist-Filter
        greift auf das ganze Jahr statt nur einen Monat.
        """
        self._year_mode = year_mode
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

    def set_problem_trip_ids(self, ids: set[int]) -> None:
        """Setzt die Trip-IDs, die nach der Plausibilitaetspruefung als
        fehlerhaft markiert werden sollen. Leere Menge entfernt die Markierung.
        """
        self._problem_trip_ids = set(ids)
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

        # Blacklist-Nur-Eintraege fuer den aktuellen Monat/Jahr (Tage ohne Trip)
        bl_only_rows: list[tuple[date, dict[str, object]]] = []
        if self._show_blacklist:
            for d, entry in self._blacklist_entries_by_date.items():
                if d in trip_dates:
                    continue
                if self._year_mode:
                    if d.year == month_data.year:
                        bl_only_rows.append((d, entry))
                else:
                    if d.year == month_data.year and d.month == month_data.month:
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
                # Blacklist-Nur-Zeile: kein Trip, nur Grund — ausschliesslich rot
                reason = str(entry.get("reason", ""))
                entry_id = int(entry.get("id", 0))
                cells: list[Text] = []
                if self._show_id:
                    cells.append(Text("", style=_STYLE_MUTED))
                if self._show_code:
                    cells.append(Text("", style=_STYLE_MUTED))
                bl_cells = [
                    Text(date_de, style=_STYLE_ERROR),
                    Text(weekday, style=_STYLE_ERROR),
                    Text("", style=_STYLE_MUTED),
                    Text("", style=_STYLE_MUTED),
                    Text(f"[GESPERRT: {reason}]", style=_STYLE_ERROR),
                ]
                if self._show_fuel:
                    bl_cells.append(Text("", style=_STYLE_MUTED))
                bl_cells.extend(
                    [
                        Text("", style=_STYLE_MUTED),
                        Text("", style=_STYLE_MUTED),
                        Text("", style=_STYLE_MUTED),
                        Text("", style=_STYLE_MUTED),
                    ]
                )
                cells.extend(bl_cells)
                table.add_row(*cells, key=row_key)
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
                if len(dest_short) > 80:
                    dest_short = f"{dest_short[:77]}..."

                warning = ""

                # Plausi-Check hat diesen Trip als problematisch markiert.
                # Setzt direkt eine Fehler-Warnung, sodass die bestehende
                # rote Row-Styling-Logik greift.
                is_problem = trip.id in self._problem_trip_ids
                if is_problem:
                    warning = "PLAUSI"

                # Blacklist-Tag pruefen
                if not warning:
                    bl_reason = active_blacklist.get(d, "")
                    if bl_reason:
                        warning = f"GESPERRT: {bl_reason}"

                # Feiertag / Wochenende nur fuer reine business-Fahrten
                # (Tanken und Service sind auch am Sonntag unkritisch).
                # Geschaeftsessen sind am Wochenende explizit zulaessig.
                is_geschaeftsessen = "geschaeftsessen" in (trip.purpose or "").lower()
                if not warning and trip.category == "business" and not is_geschaeftsessen:
                    holiday_name = holidays_map.get(d, "")
                    if holiday_name:
                        warning = f"FEIERTAG: {holiday_name}"
                    elif d.weekday() >= 5:
                        warning = "WOCHENENDE"

                # WICHTIG: Reisezweck NIE modifizieren — der Wert wird exportiert.
                purpose_text = trip.purpose

                # Stil-Logik:
                # - rot nur bei Warnung (Blacklist/Feiertag/Wochenende)
                # - gruen fuer Datum, Ziel, Zweck und km-geschaeftlich,
                #   wenn der Trip geschaeftlich ist
                # - alles andere neutral / dim
                is_business = trip.is_business_km
                if warning:
                    row_style = _STYLE_ERROR
                elif is_business:
                    row_style = _STYLE_BUSINESS
                else:
                    row_style = _STYLE_DEFAULT
                purpose_style = row_style
                km_business_style = _STYLE_ERROR if warning else _STYLE_BUSINESS

                cells = []
                if self._show_id:
                    cells.append(Text(str(trip.id) if trip.id else "", style=_STYLE_MUTED))
                if self._show_code:
                    code = self._category_codes.get(trip.category, "")
                    code_style = "bold yellow" if code == "T" else _STYLE_MUTED
                    cells.append(Text(code, style=code_style))
                cells.extend(
                    [
                        Text(date_de, style=row_style),
                        Text(weekday, style=_STYLE_ERROR if warning else _STYLE_MUTED),
                        Text(time_str, style=_STYLE_MUTED),
                        Text(dest_short, style=row_style),
                        Text(purpose_text, style=purpose_style),
                    ]
                )
                if self._show_fuel:
                    fuel_text = ""
                    if trip.category in ("fuel", "fuel_private") and trip.fuel_liters > 0:
                        fuel_text = f"{trip.fuel_liters:.1f} L"
                    cells.append(Text(fuel_text, style="bold yellow" if fuel_text else _STYLE_MUTED))
                cells.extend(
                    [
                        Text(format_km(trip.km_start), style=_STYLE_MUTED),
                        Text(format_km(trip.km_end), style=_STYLE_MUTED),
                        Text(
                            format_km(trip.km_business) if trip.km_business > 0 else "",
                            style=km_business_style,
                        ),
                        Text(
                            format_km(trip.km_private) if trip.km_private > 0 else "",
                            style=_STYLE_MUTED,
                        ),
                    ]
                )
                table.add_row(*cells, key=row_key)
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
