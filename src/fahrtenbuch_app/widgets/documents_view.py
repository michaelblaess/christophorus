"""Belege-Ansicht als einbettbares Widget."""

from pathlib import Path

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import DataTable


class DocumentsView(Vertical):
    """Tabelle aller Belege/Dokumente."""

    DEFAULT_CSS = """
    DocumentsView {
        height: 1fr;
        min-height: 10;
        border: solid $accent;
    }
    DocumentsView DataTable {
        height: 1fr;
    }
    """

    def compose(self) -> ComposeResult:
        yield DataTable(id="docs-data", cursor_type="row", zebra_stripes=True)

    def on_mount(self) -> None:
        """Spalten anlegen."""
        table = self.query_one("#docs-data", DataTable)
        table.add_columns("#", "Typ", "Datum", "Bezug", "Datei")

    def load_data(self, documents: list[dict[str, object]]) -> None:
        """Laedt die Dokumente in die Tabelle."""
        table = self.query_one("#docs-data", DataTable)
        table.clear()

        for idx, doc in enumerate(documents):
            doc_id = str(doc.get("id", ""))
            path = str(doc.get("path", ""))
            filename = Path(path).name or path

            trip_id = doc.get("trip_id")
            bl_id = doc.get("blacklist_id")

            if trip_id:
                typ = "Fahrt"
                trip_date = str(doc.get("trip_date", ""))
                purpose = str(doc.get("trip_purpose", ""))
                date_de = self._format_date(trip_date)
                bezug = purpose
            elif bl_id:
                typ = "Blacklist"
                bl_date = str(doc.get("bl_date", ""))
                reason = str(doc.get("bl_reason", ""))
                date_de = self._format_date(bl_date)
                bezug = reason
            else:
                typ = "—"
                date_de = ""
                bezug = ""

            table.add_row(
                Text(doc_id, style="dim"),
                Text(typ, style="green" if typ == "Fahrt" else "red" if typ == "Blacklist" else "dim"),
                Text(date_de),
                Text(bezug),
                Text(filename, style="dim"),
                key=str(idx),
            )

    @staticmethod
    def _format_date(date_str: str) -> str:
        """Wandelt ISO-Datum in deutsches Format."""
        try:
            parts = date_str.split("-")
            if len(parts) == 3:
                return f"{parts[2]}.{parts[1]}.{parts[0]}"
        except (ValueError, IndexError):
            pass
        return date_str
