"""Generischer Ja/Nein-Bestaetigungsdialog."""

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Static


class ConfirmScreen(ModalScreen[bool]):
    """Bestaetigt eine Aktion mit Ja/Nein. Gibt True bei Zustimmung zurueck."""

    DEFAULT_CSS = """
    ConfirmScreen {
        align: center middle;
    }
    ConfirmScreen > VerticalScroll {
        width: 70;
        height: auto;
        max-height: 22;
        background: $surface;
        border: thick $warning;
        padding: 1 2;
    }
    ConfirmScreen #title {
        text-align: center;
        text-style: bold;
        margin-bottom: 1;
    }
    ConfirmScreen #message {
        margin-bottom: 1;
    }
    ConfirmScreen Horizontal {
        align: center middle;
        height: auto;
    }
    ConfirmScreen Button {
        margin: 0 2;
        min-width: 14;
    }
    """

    BINDINGS = [
        Binding("escape", "cancel", "Abbrechen"),
        Binding("y", "confirm", "Ja"),
        Binding("n", "cancel", "Nein"),
        Binding("enter", "confirm", "Bestaetigen"),
    ]

    def __init__(
        self,
        title: str,
        message: str,
        confirm_label: str = "Loeschen",
        cancel_label: str = "Abbrechen",
    ) -> None:
        super().__init__()
        self._title = title
        self._message = message
        self._confirm_label = confirm_label
        self._cancel_label = cancel_label

    def compose(self) -> ComposeResult:
        with VerticalScroll():
            yield Static(self._title, id="title")
            yield Static(self._message, id="message")
            with Horizontal():
                yield Button(self._confirm_label, id="confirm", variant="error")
                yield Button(self._cancel_label, id="cancel", variant="primary")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "confirm":
            self.dismiss(True)
        else:
            self.dismiss(False)

    def action_confirm(self) -> None:
        self.dismiss(True)

    def action_cancel(self) -> None:
        self.dismiss(False)
