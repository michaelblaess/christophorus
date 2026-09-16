"""Generischer Ja/Nein-Bestaetigungsdialog."""

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Static

from christo.i18n import t


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
        Binding("escape", "cancel", "cancel"),
        Binding("y,Y", "confirm", "yes", key_display="y"),
        Binding("n,N", "cancel", "no", key_display="n"),
        Binding("enter", "confirm", "confirm"),
    ]

    def __init__(
        self,
        title: str,
        message: str,
        confirm_label: str | None = None,
        cancel_label: str | None = None,
    ) -> None:
        super().__init__()
        self._title = title
        self._message = message
        self._confirm_label = confirm_label or t("confirm.confirm_label_delete")
        self._cancel_label = cancel_label or t("confirm.cancel_label")

    def compose(self) -> ComposeResult:
        with VerticalScroll():
            yield Static(self._title, id="title")
            yield Static(self._message, id="message")
            with Horizontal():
                yield Button(self._confirm_label, id="confirm", variant="error")
                yield Button(self._cancel_label, id="cancel", variant="primary")

    def on_mount(self) -> None:
        # Bindings nach i18n uebersetzen (BINDINGS klassenweite Strings sind
        # leer geblieben, weil sie nur Action-Keys enthalten).
        import dataclasses

        labels = {
            "cancel": t("binding.cancel"),
            "confirm": t("binding.confirm"),
            "yes": t("binding.yes"),
            "no": t("binding.no"),
        }
        for key, lst in self._bindings.key_to_bindings.items():
            for i, b in enumerate(lst):
                lbl = labels.get(b.description)
                if lbl:
                    self._bindings.key_to_bindings[key][i] = dataclasses.replace(b, description=lbl)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "confirm":
            self.dismiss(True)
        else:
            self.dismiss(False)

    def action_confirm(self) -> None:
        self.dismiss(True)

    def action_cancel(self) -> None:
        self.dismiss(False)
