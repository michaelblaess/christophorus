"""Uebersicht der aktuell geltenden Tastenbelegung.

Die Seite liest nichts eigenes - sie stellt dar, was `keymap.resolve()` aus
Stil, Vim-Schalter und eigenen Belegungen gemacht hat. Damit stimmt sie
zwangslaeufig mit dem ueberein, was die Anwendung tatsaechlich gebunden hat,
statt eine gepflegte Liste danebenzustellen, die irgendwann abweicht.
"""

from __future__ import annotations

from typing import Any

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, DataTable, Static

from death_proof.i18n import t
from death_proof.keymap import LABEL_KEYS, key_display


class KeymapScreen(ModalScreen[None]):
    """Zeigt Taste und Aktion der aktiven Belegung."""

    DEFAULT_CSS = """
    KeymapScreen {
        align: center middle;
    }

    KeymapScreen > Vertical {
        width: 72;
        max-width: 90%;
        height: auto;
        max-height: 80%;
        background: $surface;
        border: thick $primary;
        padding: 1 2;
    }

    KeymapScreen #keymap-title {
        text-align: center;
        text-style: bold;
        color: $primary;
    }

    KeymapScreen #keymap-mode {
        text-align: center;
        color: $text-muted;
        margin-bottom: 1;
    }

    KeymapScreen DataTable {
        height: auto;
        max-height: 20;
    }

    KeymapScreen #keymap-close {
        margin-top: 1;
        width: 100%;
    }
    """

    BINDINGS = [
        Binding("escape", "dismiss", "Esc"),
        Binding("q,Q", "dismiss", "q", show=False),
    ]

    def __init__(self, resolved: Any, style: Any, vim: bool) -> None:
        """Merkt sich die fertig aufgeloeste Belegung.

        Args:
            resolved: Das Ergebnis von `keymap.resolve()` (ResolvedKeymap).
            style: Der angewendete Stil (KeymapStyle).
            vim: Ob die Vim-Navigation eingeschaltet ist.
        """
        super().__init__()
        self._resolved = resolved
        self._style = style
        self._vim = vim

    def compose(self) -> ComposeResult:
        """Baut Titel, Modus-Zeile, Tabelle und den Schliessen-Knopf."""
        stil_text = t(f"keymap.style_{self._style.value}")
        vim_text = t("keymap.vim_on") if self._vim else t("keymap.vim_off")

        with Vertical():
            yield Static(t("keymap.title"), id="keymap-title")
            yield Static(f"{stil_text} - {vim_text}", id="keymap-mode")
            with VerticalScroll():
                yield DataTable(id="keymap-table", cursor_type="row", zebra_stripes=True)
            yield Button(t("keymap.close"), variant="primary", id="keymap-close")

    def on_mount(self) -> None:
        """Fuellt die Tabelle aus der aufgeloesten Belegung."""
        table: DataTable[Any] = self.query_one("#keymap-table", DataTable)
        table.add_column(t("keymap.column_keys"), width=22)
        table.add_column(t("keymap.column_action"))

        for action, binding in self._resolved.bindings.items():
            tasten = " / ".join(key_display(key) for key in binding.keys if not ist_grossschreibung(key))
            beschriftung = t(LABEL_KEYS.get(action, action))
            if not binding.show:
                beschriftung = f"{beschriftung}  ({t('keymap.hidden')})"
            table.add_row(tasten, beschriftung)

        self.set_focus(self.query_one("#keymap-close", Button))

    @on(Button.Pressed, "#keymap-close")
    def _on_close(self) -> None:
        """Schliesst die Uebersicht."""
        self.dismiss(None)


def ist_grossschreibung(key: str) -> bool:
    """Prueft, ob eine Taste nur die Grossschreibung einer anderen ist.

    Die Belegung fuehrt Buchstaben doppelt (``q`` und ``Q``), damit sie
    unabhaengig von der Umschalttaste wirken. In der Uebersicht waere das
    Rauschen - dort genuegt die Kleinschreibung.

    Args:
        key: Der Tastenname.

    Returns:
        True, wenn es ein einzelner Grossbuchstabe ist.
    """
    return len(key) == 1 and key.isupper()
