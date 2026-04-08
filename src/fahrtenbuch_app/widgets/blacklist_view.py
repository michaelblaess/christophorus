"""Blacklist-Ansicht als einbettbares Widget."""

from datetime import date

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.message import Message
from textual.widgets import DataTable

_WEEKDAYS = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]


class BlacklistView(Vertical):
    """Tabelle aller Blacklist-Eintraege."""

    DEFAULT_CSS = """
    BlacklistView {
        height: 1fr;
        min-height: 10;
        border: solid $accent;
    }
    BlacklistView DataTable {
        height: 1fr;
    }
    """

    class EntrySelected(Message):
        """Wird gesendet wenn ein Eintrag ausgewaehlt wird (Enter / Klick)."""

        def __init__(self, entry_id: int, date_str: str, reason: str) -> None:
            super().__init__()
            self.entry_id = entry_id
            self.date_str = date_str
            self.reason = reason

    def __init__(self, **kwargs: object) -> None:
        super().__init__(**kwargs)
        self._row_entries: dict[str, dict[str, object]] = {}

    def compose(self) -> ComposeResult:
        yield DataTable(id="blacklist-data", cursor_type="row", zebra_stripes=True)

    def on_mount(self) -> None:
        """Spalten anlegen."""
        table = self.query_one("#blacklist-data", DataTable)
        table.add_columns("#", "Datum", "Tag", "Grund / Anlass")

    def load_data(self, entries: list[dict[str, object]]) -> None:
        """Laedt die Blacklist-Eintraege in die Tabelle."""
        table = self.query_one("#blacklist-data", DataTable)
        table.clear()
        self._row_entries.clear()

        for idx, entry in enumerate(entries):
            entry_id = str(entry.get("id", ""))
            date_str = str(entry.get("date", ""))
            reason = str(entry.get("reason", ""))

            date_de = date_str
            weekday = ""
            is_weekend = False
            try:
                parts = date_str.split("-")
                d = date(int(parts[0]), int(parts[1]), int(parts[2]))
                date_de = d.strftime("%d.%m.%Y")
                weekday = _WEEKDAYS[d.weekday()]
                is_weekend = d.weekday() >= 5
            except (ValueError, IndexError):
                pass

            date_style = "dim" if is_weekend else "bold red"
            row_key = str(idx)
            self._row_entries[row_key] = entry

            table.add_row(
                Text(entry_id, style="dim"),
                Text(date_de, style=date_style),
                Text(weekday, style="dim"),
                Text(reason, style="bold" if not is_weekend else "dim"),
                key=row_key,
            )

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Oeffnet Detail-Ansicht beim Auswaehlen einer Zeile (Enter / Doppelklick)."""
        row_key = str(event.row_key.value) if event.row_key else ""
        entry = self._row_entries.get(row_key)
        if entry is None:
            return
        self.post_message(self.EntrySelected(
            entry_id=int(entry.get("id", 0)),
            date_str=str(entry.get("date", "")),
            reason=str(entry.get("reason", "")),
        ))
