"""Blacklist-Ansicht als einbettbares Widget."""

from datetime import date

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Vertical
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

    def __init__(self, **kwargs: object) -> None:
        super().__init__(**kwargs)

    def compose(self) -> ComposeResult:
        yield DataTable(id="blacklist-data", cursor_type="row", zebra_stripes=True)

    def on_mount(self) -> None:
        """Spalten anlegen."""
        table = self.query_one("#blacklist-data", DataTable)
        table.add_columns("#", "Datum", "Tag", "Grund / Anlass", "Privat ok")

    def load_data(self, entries: list[dict[str, object]]) -> None:
        """Laedt die Blacklist-Eintraege in die Tabelle."""
        table = self.query_one("#blacklist-data", DataTable)
        table.clear()

        for entry in entries:
            entry_id = str(entry.get("id", ""))
            date_str = str(entry.get("date", ""))
            reason = str(entry.get("reason", ""))
            allow_private = bool(entry.get("allow_private", 0))

            # Datum formatieren und Wochentag bestimmen
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
            allow_text = Text("ja", style="yellow") if allow_private else Text("nein", style="dim")

            table.add_row(
                Text(entry_id, style="dim"),
                Text(date_de, style=date_style),
                Text(weekday, style="dim"),
                Text(reason, style="bold" if not is_weekend else "dim"),
                allow_text,
            )
