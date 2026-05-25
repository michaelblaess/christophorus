"""Detail-Ansicht fuer einen Blacklist-Eintrag: bearbeiten, neu anlegen, loeschen."""

import contextlib
import os
from pathlib import Path

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Static

from death_proof.i18n import t
from death_proof.services.database import Database


def _iso_to_de(iso: str) -> str:
    """YYYY-MM-DD -> DD.MM.YYYY."""
    if not iso:
        return ""
    parts = iso.split("-")
    if len(parts) == 3:
        return f"{parts[2]}.{parts[1]}.{parts[0]}"
    return iso


def _de_to_iso(de: str) -> str:
    """DD.MM.YYYY -> YYYY-MM-DD (leer bei ungueltigem Format)."""
    if not de:
        return ""
    parts = de.strip().split(".")
    if len(parts) != 3:
        return ""
    try:
        day = int(parts[0])
        month = int(parts[1])
        year = int(parts[2])
        return f"{year:04d}-{month:02d}-{day:02d}"
    except ValueError:
        return ""


class BlacklistDetailScreen(ModalScreen[bool | None]):
    """Zeigt Details eines Blacklist-Eintrags zum Bearbeiten / Loeschen / Neuanlegen.

    Dismiss-Wert:
      * True  → Eintrag wurde hinzugefuegt, geaendert oder geloescht (App refresht)
      * None  → Dialog abgebrochen, nichts aendern
    """

    DEFAULT_CSS = """
    BlacklistDetailScreen {
        align: center middle;
    }
    BlacklistDetailScreen > Vertical {
        width: 80;
        height: auto;
        max-height: 32;
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
    BlacklistDetailScreen .date-row {
        height: 3;
        layout: horizontal;
    }
    BlacklistDetailScreen #input-date {
        width: 1fr;
    }
    BlacklistDetailScreen #btn-date-picker {
        width: 5;
        min-width: 5;
    }
    BlacklistDetailScreen #input-reason {
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
        Binding("escape", "cancel", "close"),
    ]

    def __init__(
        self,
        database: Database,
        entry_id: int = 0,
        date_str: str = "",
        reason: str = "",
        **kwargs: object,
    ) -> None:
        super().__init__(**kwargs)
        self._database = database
        self._entry_id = entry_id
        self._date_str = date_str
        self._reason = reason
        self._is_new = entry_id <= 0

    def compose(self) -> ComposeResult:
        title = t("blacklist_detail.title_new") if self._is_new else t("blacklist_detail.title_edit")
        date_de = _iso_to_de(self._date_str)
        with Vertical():
            yield Static(title, classes="detail-title")
            yield Static(t("blacklist_detail.label.date"), classes="detail-label")
            with Horizontal(classes="date-row"):
                yield Input(
                    value=date_de,
                    placeholder=t("blacklist_detail.placeholder.date"),
                    id="input-date",
                )
                yield Button("...", id="btn-date-picker")
            yield Static(t("blacklist_detail.label.reason"), classes="detail-label")
            yield Input(
                value=self._reason,
                placeholder=t("blacklist_detail.placeholder.reason"),
                id="input-reason",
            )
            yield Static(t("trip.docs_title"), id="docs-title")
            yield Vertical(id="docs-list")
            with Horizontal(classes="button-row"):
                yield Button(t("trip.btn_add_doc"), variant="success", id="btn-add-doc")
                yield Button(t("blacklist_detail.btn_save"), variant="primary", id="btn-save")
                if not self._is_new:
                    yield Button(t("blacklist_detail.btn_delete"), variant="error", id="btn-delete")
                yield Button(t("blacklist_detail.btn_cancel"), id="btn-cancel")

    def on_mount(self) -> None:
        self._refresh_docs()
        # Wenn neuer Eintrag: Fokus aufs Datumsfeld
        if self._is_new:
            self.query_one("#input-date", Input).focus()
        else:
            self.query_one("#input-reason", Input).focus()

    def _refresh_docs(self) -> None:
        """Aktualisiert die Belegliste. Belege sind nur an bestehende Eintraege moeglich."""
        docs_list = self.query_one("#docs-list", Vertical)
        for child in list(docs_list.children):
            child.remove()

        if self._is_new or self._entry_id <= 0:
            docs_list.mount(Static(f"  {t('blacklist_detail.docs_after_save')}", classes="doc-name"))
            # Beleg-Button deaktivieren bis gespeichert
            with contextlib.suppress(Exception):
                self.query_one("#btn-add-doc", Button).disabled = True
            return

        with contextlib.suppress(Exception):
            self.query_one("#btn-add-doc", Button).disabled = False

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
            docs_list.mount(Static(f"  {t('blacklist_detail.docs_empty')}", classes="doc-name"))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        btn_id = event.button.id or ""
        if btn_id == "btn-save":
            self._save()
        elif btn_id == "btn-delete":
            self._delete()
        elif btn_id == "btn-cancel":
            self.dismiss(None)
        elif btn_id == "btn-date-picker":
            self._open_date_picker()
        elif btn_id == "btn-add-doc":
            self._open_file_picker()
        elif btn_id.startswith("btn-del-doc-"):
            self._delete_document(btn_id)

    def _save(self) -> None:
        """Speichert den Eintrag (neu oder Update)."""
        date_de = self.query_one("#input-date", Input).value.strip()
        reason = self.query_one("#input-reason", Input).value.strip()

        iso = _de_to_iso(date_de)
        if not iso:
            self.app.notify(t("blacklist_detail.notify.date_invalid"), severity="error")
            return
        if not reason:
            self.app.notify(t("blacklist_detail.notify.reason_required"), severity="error")
            return

        try:
            if self._is_new:
                self._entry_id = self._database.add_blacklist_entry(iso, reason)
                self._is_new = False
                self._date_str = iso
                self._reason = reason
                self.app.notify(t("blacklist_detail.notify.created"), severity="information")
                self.dismiss(True)
            else:
                self._database.update_blacklist_entry(self._entry_id, iso, reason)
                self.app.notify(t("blacklist_detail.notify.updated"), severity="information")
                self.dismiss(True)
        except Exception as exc:
            self.app.notify(t("blacklist_detail.notify.save_failed", error=exc), severity="error")

    def _delete(self) -> None:
        """Loescht den aktuellen Eintrag."""
        if self._is_new or self._entry_id <= 0:
            return
        try:
            self._database.delete_blacklist_entry(self._entry_id)
            self.app.notify(t("blacklist_detail.notify.deleted"), severity="warning")
            self.dismiss(True)
        except Exception as exc:
            self.app.notify(t("blacklist_detail.notify.delete_failed", error=exc), severity="error")

    def _open_date_picker(self) -> None:
        """Oeffnet den Kalender-Dialog zur Datumsauswahl."""
        from death_proof.screens.date_picker_screen import DatePickerScreen

        current_de = self.query_one("#input-date", Input).value.strip()
        current_iso = _de_to_iso(current_de) if current_de else self._date_str
        self.app.push_screen(
            DatePickerScreen(initial_date=current_iso),
            callback=self._on_date_selected,
        )

    def _on_date_selected(self, selected: str | None) -> None:
        """Callback nach Datumsauswahl aus dem Kalender."""
        if selected is not None:
            self.query_one("#input-date", Input).value = _iso_to_de(selected)

    def _open_file_picker(self) -> None:
        """Oeffnet den File-Picker-Screen."""
        if self._is_new or self._entry_id <= 0:
            self.app.notify(t("blacklist_detail.notify.save_before_docs"), severity="warning")
            return
        from death_proof.screens.file_picker_screen import FilePickerScreen

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
