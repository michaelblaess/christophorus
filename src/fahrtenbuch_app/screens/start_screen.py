"""Start-Screen — Fahrtenbuch oeffnen oder neu anlegen."""

from pathlib import Path

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Static

from fahrtenbuch_app.models.settings import GlobalConfig


class StartScreen(ModalScreen[str | None]):
    """Startbildschirm zum Oeffnen oder Erstellen eines Fahrtenbuchs.

    Gibt den gewaehlten Pfad zurueck oder None bei Abbruch.
    """

    DEFAULT_CSS = """
    StartScreen {
        align: center middle;
    }
    StartScreen > Vertical {
        width: 70;
        height: auto;
        max-height: 30;
        background: $surface;
        border: thick $accent;
        padding: 1 2;
    }
    StartScreen #title {
        text-align: center;
        text-style: bold;
        margin-bottom: 1;
    }
    StartScreen #subtitle {
        text-align: center;
        color: $text-muted;
        margin-bottom: 1;
    }
    StartScreen .section-title {
        text-style: bold;
        margin-top: 1;
        margin-bottom: 0;
        padding: 0 1;
    }
    StartScreen .form-row {
        height: auto;
        margin-bottom: 1;
    }
    StartScreen Label {
        width: 20;
        padding: 0 1;
    }
    StartScreen Input {
        width: 1fr;
    }
    StartScreen .button-row {
        height: auto;
        margin-top: 1;
        align: center middle;
    }
    StartScreen Button {
        margin: 0 1;
    }
    StartScreen .recent-item {
        padding: 0 2;
        height: auto;
        margin-bottom: 0;
    }
    """

    BINDINGS = [
        Binding("escape", "cancel", "Abbrechen"),
    ]

    def __init__(self, config: GlobalConfig, **kwargs: object) -> None:
        super().__init__(**kwargs)
        self._config = config

    def compose(self) -> ComposeResult:
        """Erstellt den Startbildschirm."""
        default_base = str(Path.home() / "Fahrtenbuecher")

        with Vertical():
            yield Static("Fahrtenbuch", id="title")
            yield Static(
                "Finanzamt-konforme Fahrtenbuecher fuer Leasing-Fahrzeuge",
                id="subtitle",
            )

            with VerticalScroll():
                # Zuletzt geoeffnet
                if self._config.recent_paths:
                    yield Static("Zuletzt geoeffnet:", classes="section-title")
                    for path_str in self._config.recent_paths[:5]:
                        p = Path(path_str)
                        yield Button(
                            f"  {p.name}  ({path_str})",
                            variant="default",
                            id=f"btn-recent-{hash(path_str) & 0xFFFFFFFF}",
                            classes="recent-item",
                        )

                # Neues Fahrtenbuch
                yield Static("Neues Fahrtenbuch anlegen:", classes="section-title")
                with Horizontal(classes="form-row"):
                    yield Label("Basisverzeichnis:")
                    yield Input(
                        value=default_base,
                        placeholder="z.B. C:\\Users\\Michael\\Fahrtenbuecher",
                        id="input-base-dir",
                    )
                with Horizontal(classes="form-row"):
                    yield Label("Name:")
                    yield Input(
                        value="",
                        placeholder="z.B. Audi A5 2024",
                        id="input-fb-name",
                    )

            with Horizontal(classes="button-row"):
                yield Button(
                    "Neu anlegen", variant="primary", id="btn-create"
                )
                yield Button(
                    "Pfad oeffnen...", variant="success", id="btn-open"
                )
                yield Button(
                    "Abbrechen (Esc)", variant="default", id="btn-cancel"
                )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Reagiert auf Button-Klicks."""
        btn_id = event.button.id or ""

        if btn_id == "btn-create":
            self._create_new()
        elif btn_id == "btn-open":
            self._open_existing()
        elif btn_id == "btn-cancel":
            self.action_cancel()
        elif btn_id.startswith("btn-recent-"):
            self._open_recent(event.button)

    def _create_new(self) -> None:
        """Erstellt ein neues Fahrtenbuch."""
        base_dir = self.query_one("#input-base-dir", Input).value.strip()
        fb_name = self.query_one("#input-fb-name", Input).value.strip()

        if not base_dir:
            self.notify("Basisverzeichnis ist erforderlich", severity="error")
            return
        if not fb_name:
            self.notify("Name ist erforderlich", severity="error")
            return

        path = Path(base_dir) / fb_name
        self.dismiss(str(path))

    def _open_existing(self) -> None:
        """Oeffnet ein bestehendes Fahrtenbuch ueber Pfadeingabe."""
        base_dir = self.query_one("#input-base-dir", Input).value.strip()
        fb_name = self.query_one("#input-fb-name", Input).value.strip()

        if not base_dir:
            self.notify("Basisverzeichnis ist erforderlich", severity="error")
            return

        path = Path(base_dir) / fb_name if fb_name else Path(base_dir)

        if not path.exists():
            self.notify(
                f"Verzeichnis existiert nicht: {path}", severity="error"
            )
            return

        self.dismiss(str(path))

    def _open_recent(self, button: Button) -> None:
        """Oeffnet ein zuletzt verwendetes Fahrtenbuch."""
        label = button.label
        label_text = str(label)
        # Pfad steht in Klammern am Ende
        start = label_text.rfind("(")
        end = label_text.rfind(")")
        if start >= 0 and end > start:
            path_str = label_text[start + 1:end]
            if Path(path_str).exists():
                self.dismiss(path_str)
            else:
                self.notify(
                    f"Verzeichnis existiert nicht mehr: {path_str}",
                    severity="warning",
                )

    def action_cancel(self) -> None:
        """Bricht ab."""
        self.dismiss(None)
