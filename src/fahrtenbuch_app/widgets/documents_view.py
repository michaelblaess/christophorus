"""Belege-Ansicht als einbettbares Widget."""

from pathlib import Path

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.message import Message
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

    class DocumentOpened(Message):
        """Wird gesendet wenn der Benutzer einen Beleg oeffnen will."""

        def __init__(self, path: Path) -> None:
            super().__init__()
            self.path = path

    def __init__(self, **kwargs: object) -> None:
        super().__init__(**kwargs)
        self._documents: list[dict[str, object]] = []
        self._base_path: Path = Path(".")
        self._show_id: bool = False

    def compose(self) -> ComposeResult:
        yield DataTable(id="docs-data", cursor_type="row", zebra_stripes=True)

    def on_mount(self) -> None:
        """Spalten anlegen."""
        self._setup_columns()

    def _setup_columns(self) -> None:
        """Legt die Spalten an (optional mit ID-Spalte am Anfang)."""
        table = self.query_one("#docs-data", DataTable)
        if self._show_id:
            table.add_column("ID", key="id", width=5)
        table.add_columns("Typ", "Datum", "Uhrzeit", "Bezug", "Bemerkung", "Datei")

    def set_show_id(self, value: bool) -> None:
        """Schaltet die ID-Spalte ein/aus."""
        if self._show_id == value:
            return
        self._show_id = value
        try:
            table = self.query_one("#docs-data", DataTable)
        except Exception:
            return
        table.clear(columns=True)
        self._setup_columns()
        if self._documents:
            self.load_data(self._documents, self._base_path)

    def load_data(
        self,
        documents: list[dict[str, object]],
        base_path: Path,
    ) -> None:
        """Laedt die Dokumente in die Tabelle, sortiert nach Datum (aufsteigend)."""
        self._base_path = base_path
        # Nach Datum sortieren: Trip-Datum oder Blacklist-Datum, ISO-Form sortiert lexikographisch
        def sort_key(doc: dict[str, object]) -> str:
            trip_date = str(doc.get("trip_date") or "")
            bl_date = str(doc.get("bl_date") or "")
            return trip_date or bl_date or ""

        self._documents = sorted(documents, key=sort_key)

        table = self.query_one("#docs-data", DataTable)
        table.clear()

        for idx, doc in enumerate(self._documents):
            doc_id = str(doc.get("id", ""))
            path = str(doc.get("path", ""))
            filename = Path(path).name or path

            trip_id = doc.get("trip_id")
            bl_id = doc.get("blacklist_id")

            uhrzeit = ""
            bemerkung = ""

            if trip_id:
                typ = "Fahrt"
                trip_date = str(doc.get("trip_date", ""))
                purpose = str(doc.get("trip_purpose", ""))
                date_de = self._format_date(trip_date)
                bezug = purpose
                uhrzeit = str(doc.get("trip_time_from") or "")[:5]
                category = str(doc.get("trip_category") or "")
                fuel_liters = doc.get("trip_fuel_liters")
                if category in ("fuel", "fuel_private") and fuel_liters:
                    try:
                        bemerkung = f"{float(fuel_liters):.2f} L"
                    except (TypeError, ValueError):
                        bemerkung = ""
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

            cells: list[Text] = []
            if self._show_id:
                cells.append(Text(doc_id, style="dim"))
            cells.extend([
                Text(typ, style="green" if typ == "Fahrt" else "red" if typ == "Blacklist" else "dim"),
                Text(date_de),
                Text(uhrzeit, style="dim"),
                Text(bezug),
                Text(bemerkung, style="cyan" if bemerkung else "dim"),
                Text(filename, style="dim"),
            ])
            table.add_row(*cells, key=str(idx))

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Oeffnet den Beleg bei Enter/Doppelklick auf einer Zeile."""
        try:
            idx = int(str(event.row_key.value))
        except (ValueError, TypeError):
            return
        if idx < 0 or idx >= len(self._documents):
            return
        path = str(self._documents[idx].get("path", ""))
        if not path:
            return
        file_path = Path(path)
        if not file_path.is_absolute():
            file_path = self._base_path / file_path
        self.post_message(self.DocumentOpened(file_path))

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
