"""Info-Dialog."""

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Static

from fahrtenbuch_app import __author__, __version__, __year__


class InfoScreen(ModalScreen[None]):
    """About-Dialog."""

    DEFAULT_CSS = """
    InfoScreen {
        align: center middle;
    }
    InfoScreen > VerticalScroll {
        width: 60;
        height: auto;
        max-height: 20;
        background: $surface;
        border: thick $accent;
        padding: 1 2;
    }
    InfoScreen #title {
        text-align: center;
        text-style: bold;
        margin-bottom: 1;
    }
    InfoScreen #info-text {
        text-align: center;
    }
    InfoScreen #quote {
        text-align: center;
        margin-top: 1;
        color: $text-muted;
        text-style: italic;
    }
    InfoScreen #footer-text {
        text-align: center;
        margin-top: 1;
        color: $text-muted;
    }
    """

    BINDINGS = [
        Binding("escape", "close", "Schliessen"),
    ]

    def compose(self) -> ComposeResult:
        with VerticalScroll():
            yield Static(f"Fahrtenbuch v{__version__}", id="title")
            yield Static(
                f"von {__author__}\n"
                f"\n"
                f"Finanzamt-konforme Fahrtenbuecher\n"
                f"fuer Leasing-Fahrzeuge\n"
                f"\n"
                f"(c) {__year__}",
                id="info-text",
            )
            yield Static(
                "\u201eFreiheit wird vom Unterdr\u00fccker niemals\n"
                "freiwillig gegeben; sie muss vom\n"
                "Unterdr\u00fcckten gefordert werden.\u201c\n"
                "\u2014 Martin Luther King jr.",
                id="quote",
            )
            yield Static("ESC = Schliessen", id="footer-text")

    def action_close(self) -> None:
        self.dismiss(None)
