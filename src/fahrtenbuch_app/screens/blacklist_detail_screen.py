"""Detail-Ansicht fuer einen einzelnen Blacklist-Eintrag mit Loeschen-Button."""

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Static


class BlacklistDetailScreen(ModalScreen[int | None]):
    """Zeigt Details eines Blacklist-Eintrags und erlaubt das Loeschen."""

    DEFAULT_CSS = """
    BlacklistDetailScreen {
        align: center middle;
    }
    BlacklistDetailScreen > Vertical {
        width: 60;
        height: auto;
        max-height: 20;
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
        entry_id: int,
        date_str: str,
        reason: str,
        **kwargs: object,
    ) -> None:
        super().__init__(**kwargs)
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
            with Horizontal(classes="button-row"):
                yield Button("Schliessen", id="btn-close")
                yield Button("Loeschen", variant="error", id="btn-delete")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-delete":
            self.dismiss(self._entry_id)
        else:
            self.dismiss(None)

    def action_cancel(self) -> None:
        self.dismiss(None)

    def _format_date(self, date_str: str) -> str:
        """Wandelt ISO-Datum in deutsches Format um."""
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
