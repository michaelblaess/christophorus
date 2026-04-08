"""Detail-Ansicht fuer einen einzelnen Blacklist-Eintrag mit Loeschen-Button."""

import os
from pathlib import Path

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Static

from fahrtenbuch_app.services.database import Database


class BlacklistDetailScreen(ModalScreen[int | None]):
    """Zeigt Details eines Blacklist-Eintrags und erlaubt das Loeschen."""

    DEFAULT_CSS = """
    BlacklistDetailScreen {
        align: center middle;
    }
    BlacklistDetailScreen > Vertical {
        width: 60;
        height: auto;
        max-height: 30;
        border: double $accent;
        background: $surface;
        padding: 1 2;
    }
    BlacklistDetailScreen .detail-title {
        text-style: bold;
        color: $accent;
        margin-bottom: 1;
    }
    BlacklistDetailScreen .detail-label {
        color: $text-muted;
        margin-top: 1;
    }
    BlacklistDetailScreen .detail-value {
        margin-bottom: 1;
    }
    BlacklistDetailScreen .detail-reason {
        color: $text;
        margin-bottom: 1;
    }
    BlacklistDetailScreen #docs-title {
        text-style: bold;
        color: $accent;
        margin-top: 1;
        margin-bottom: 0;
    }
    BlacklistDetailScreen #docs-list {
        height: auto;
        margin-bottom: 1;
    }
    BlacklistDetailScreen .doc-row {
        height: 1;
        layout: horizontal;
    }
    BlacklistDetailScreen .doc-name {
        width: 1fr;
        color: $text-muted;
    }
    BlacklistDetailScreen .doc-del {
        width: 5;
        color: $error;
    }
    BlacklistDetailScreen .button-row {
        height: 3;
        margin-top: 1;
        align: right middle;
    }
    BlacklistDetailScreen Button {
        margin-left: 1;
    }
    """

    BINDINGS = [
        Binding("escape", "cancel", "Schliessen"),
    ]

    def __init__(
        self,
        database: Database,
        entry_id: int,
        date_str: str,
        reason: str,
        **kwargs: object,
    ) -> None:
        super().__init__(**kwargs)
        self._database = database
        self._entry_id = entry_id
        self._date_str = date_str
        self._reason = reason

    def compose(self) -> ComposeResult:
        date_de = self._format_date(self._date_str)
        with Vertical():
            yield Static("Blacklist-Eintrag", classes="detail-title")
            yield Static("Datum:", classes="detail-label")
            yield Static(f"  {date_de}", classes="detail-value")
            yield Static("Grund / Anlass:", classes="detail-label")
            yield Static(f"  {self._reason}", classes="detail-reason")
            yield Static("Belege:", id="docs-title")
            yield Vertical(id="docs-list")
            with Horizontal(classes="button-row"):
                yield Button("+ Beleg", variant="success", id="btn-add-doc")
                yield Button("Schliessen", id="btn-close")
                yield Button("Loeschen", variant="error", id="btn-delete")

    def on_mount(self) -> None:
        self._refresh_docs()

    def _refresh_docs(self) -> None:
        """Aktualisiert die Belegliste."""
        docs_list = self.query_one("#docs-list", Vertical)
        for child in list(docs_list.children):
            child.remove()

        docs = self._database.get_documents(blacklist_id=self._entry_id)
        for doc in docs:
            doc_id = int(doc.get("id", 0))
            path = str(doc.get("path", ""))
            name = Path(path).name or path
            desc = str(doc.get("description", ""))
            label_text = f"{name}  {desc}" if desc else name
            row = Horizontal(classes="doc-row")
            docs_list.mount(row)
            row.mount(
                Static(label_text, classes="doc-name"),
                Button("\u00d7", classes="doc-del", id=f"btn-del-doc-{doc_id}"),
            )

        if not docs:
            docs_list.mount(Static("  (keine Belege)", classes="doc-name"))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        btn_id = event.button.id or ""
        if btn_id == "btn-delete":
            self.dismiss(self._entry_id)
        elif btn_id == "btn-close":
            self.dismiss(None)
        elif btn_id == "btn-add-doc":
            self._open_file_picker()
        elif btn_id.startswith("btn-del-doc-"):
            self._delete_document(btn_id)

    def _open_file_picker(self) -> None:
        """Oeffnet den File-Picker-Screen."""
        from fahrtenbuch_app.screens.file_picker_screen import FilePickerScreen

        self.app.push_screen(
            FilePickerScreen(start_path=self._database.path),
            callback=self._on_file_selected,
        )

    def _on_file_selected(self, selected: Path | None) -> None:
        """Callback nach Dateiauswahl — speichert Dokument in DB."""
        if selected is None:
            return
        try:
            rel_path = os.path.relpath(str(selected), str(self._database.path))
        except ValueError:
            rel_path = str(selected)
        self._database.add_document(rel_path, blacklist_id=self._entry_id)
        self._refresh_docs()

    def _delete_document(self, btn_id: str) -> None:
        """Loescht ein Dokument anhand der Button-ID."""
        try:
            doc_id = int(btn_id.replace("btn-del-doc-", ""))
        except ValueError:
            return
        self._database.delete_document(doc_id)
        self._refresh_docs()

    def action_cancel(self) -> None:
        self.dismiss(None)

    def _format_date(self, date_str: str) -> str:
        try:
            parts = date_str.split("-")
            if len(parts) == 3:
                from datetime import date
                d = date(int(parts[0]), int(parts[1]), int(parts[2]))
                weekdays = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]
                return f"{weekdays[d.weekday()]}, {d.strftime('%d.%m.%Y')}"
        except (ValueError, IndexError):
            pass
        return date_str
