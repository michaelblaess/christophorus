"""Start-Screen — Fahrtenbuch oeffnen, neu anlegen oder sichern."""

from collections.abc import Callable
from pathlib import Path

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Checkbox, Input, Label, Static

from death_proof.i18n import t
from death_proof.models.settings import GlobalConfig
from death_proof.services.database import Database

# Rueckgabe-Typ des StartScreen:
# - None           → Dialog abgebrochen
# - (path, None)   → Oeffnen oder leeres Neu-Anlegen
# - (path, source) → Neu-Anlegen mit Clone aus 'source'
StartResult = tuple[str, str | None]


class StartScreen(ModalScreen[StartResult | None]):
    """Startbildschirm zum Oeffnen, Erstellen oder Sichern eines Fahrtenbuchs.

    Gibt ein Tupel (ziel_pfad, clone_source_pfad_oder_None) zurueck, oder
    None bei Abbruch. Die Backup-Aktion wird ueber den on_backup-Callback
    direkt im Screen ausgefuehrt und schliesst den Dialog nicht.
    """

    DEFAULT_CSS = """
    StartScreen {
        align: center middle;
    }
    StartScreen > Vertical {
        width: 80%;
        max-width: 110;
        height: auto;
        max-height: 36;
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
    StartScreen .current-info {
        color: $text-muted;
        padding: 0 1;
        margin-bottom: 0;
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
    StartScreen Checkbox {
        margin-top: 0;
        margin-bottom: 0;
        padding: 0 1;
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
        width: 100%;
        padding: 0 2;
        height: auto;
        margin-bottom: 0;
    }
    """

    BINDINGS = [
        Binding("escape", "cancel", "cancel"),
    ]

    def __init__(
        self,
        config: GlobalConfig,
        current_path: str | None = None,
        on_backup: Callable[[], Path] | None = None,
        **kwargs: object,
    ) -> None:
        super().__init__(**kwargs)
        self._config = config
        self._current_path = current_path
        self._on_backup = on_backup
        # Map Button-ID → Recent-Pfad. Wird in compose() gefuellt. Noetig
        # weil Pfade selbst Klammern enthalten koennen (z.B. "Audi A5 (2024)")
        # und Label-Parsing daran scheitert.
        self._recent_path_by_id: dict[str, str] = {}

    def compose(self) -> ComposeResult:
        """Erstellt den Startbildschirm."""
        # Basisverzeichnis: zuletzt verwendetes oder Fallback auf Home
        default_base = self._config.last_base_dir or str(Path.home() / "Fahrtenbuecher")

        with Vertical():
            yield Static(t("start.title"), id="title")
            yield Static(t("start.subtitle"), id="subtitle")

            with VerticalScroll():
                # Aktuelles Fahrtenbuch + Sichern
                if self._current_path:
                    yield Static(t("start.current_open"), classes="section-title")
                    current_name = Path(self._current_path).name
                    yield Static(
                        f"  {current_name}  ({self._current_path})",
                        classes="current-info",
                    )
                    with Horizontal(classes="button-row"):
                        yield Button(
                            t("start.btn_backup"),
                            variant="warning",
                            id="btn-backup",
                        )

                # Zuletzt geoeffnet
                if self._config.recent_paths:
                    yield Static(t("start.recent"), classes="section-title")
                    for path_str in self._config.recent_paths[:5]:
                        p = Path(path_str)
                        btn_id = f"btn-recent-{hash(path_str) & 0xFFFFFFFF}"
                        self._recent_path_by_id[btn_id] = path_str
                        yield Button(
                            f"  {p.name}  ({path_str})",
                            variant="default",
                            id=btn_id,
                            classes="recent-item",
                        )

                # Neues Fahrtenbuch
                yield Static(t("start.new_section"), classes="section-title")
                with Horizontal(classes="form-row"):
                    yield Label(t("start.label.base_dir"))
                    yield Input(
                        value=default_base,
                        placeholder=t("start.placeholder.base"),
                        id="input-base-dir",
                    )
                with Horizontal(classes="form-row"):
                    yield Label(t("start.label.name"))
                    yield Input(
                        value="",
                        placeholder=t("start.placeholder.name"),
                        id="input-fb-name",
                    )
                yield Checkbox(
                    t("start.check_clone"),
                    value=False,
                    id="check-clone",
                )
                with Horizontal(classes="form-row"):
                    yield Label(t("start.label.source"))
                    yield Input(
                        value=self._current_path or "",
                        placeholder=t("start.placeholder.source"),
                        id="input-clone-source",
                        disabled=True,
                    )

            with Horizontal(classes="button-row"):
                yield Button(t("start.btn_create"), variant="primary", id="btn-create")
                yield Button(t("start.btn_open"), variant="success", id="btn-open")
                yield Button(t("start.btn_cancel"), variant="default", id="btn-cancel")

    def on_checkbox_changed(self, event: Checkbox.Changed) -> None:
        """Aktiviert/Deaktiviert das Quellpfad-Feld abhaengig von der Checkbox."""
        if event.checkbox.id == "check-clone":
            source_input = self.query_one("#input-clone-source", Input)
            source_input.disabled = not event.value

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Reagiert auf Button-Klicks."""
        btn_id = event.button.id or ""

        if btn_id == "btn-create":
            self._create_new()
        elif btn_id == "btn-open":
            self._open_existing()
        elif btn_id == "btn-backup":
            self._run_backup()
        elif btn_id == "btn-cancel":
            self.action_cancel()
        elif btn_id.startswith("btn-recent-"):
            self._open_recent(event.button)

    def _create_new(self) -> None:
        """Erstellt ein neues Fahrtenbuch, optional mit Clone aus Quelle."""
        base_dir = self.query_one("#input-base-dir", Input).value.strip()
        fb_name = self.query_one("#input-fb-name", Input).value.strip()

        if not base_dir:
            self.notify(t("start.notify.base_required"), severity="error")
            return
        if not fb_name:
            self.notify(t("start.notify.name_required"), severity="error")
            return

        target_path = Path(base_dir) / fb_name

        # Verhindern, dass "Neu anlegen" still ein bestehendes Fahrtenbuch
        # oeffnet — der User hat NEU gedrueckt, das ist eindeutig.
        if Database.has_logbook(target_path):
            self.notify(
                t("start.notify.exists_already", path=target_path),
                severity="error",
            )
            return

        # Basisverzeichnis merken fuer den naechsten Aufruf
        self._config.last_base_dir = base_dir
        self._config.save()

        clone_source: str | None = None
        clone_enabled = self.query_one("#check-clone", Checkbox).value
        if clone_enabled:
            source_str = self.query_one("#input-clone-source", Input).value.strip()
            if not source_str:
                self.notify(t("start.notify.source_required"), severity="error")
                return
            source_path = Path(source_str)
            if not Database.has_logbook(source_path):
                self.notify(
                    t("start.notify.no_logbook_source", path=source_path),
                    severity="error",
                )
                return
            if source_path.resolve() == target_path.resolve():
                self.notify(t("start.notify.source_eq_target"), severity="error")
                return
            clone_source = str(source_path)

        self.dismiss((str(target_path), clone_source))

    def _open_existing(self) -> None:
        """Oeffnet ein bestehendes Fahrtenbuch ueber Pfadeingabe."""
        base_dir = self.query_one("#input-base-dir", Input).value.strip()
        fb_name = self.query_one("#input-fb-name", Input).value.strip()

        if not base_dir:
            self.notify(t("start.notify.base_required"), severity="error")
            return

        path = Path(base_dir) / fb_name if fb_name else Path(base_dir)

        if not path.exists():
            self.notify(t("start.notify.dir_missing", path=path), severity="error")
            return
        if not Database.has_logbook(path):
            self.notify(t("start.notify.no_logbook", path=path), severity="error")
            return

        # Basisverzeichnis merken fuer den naechsten Aufruf
        self._config.last_base_dir = base_dir
        self._config.save()

        self.dismiss((str(path), None))

    def _open_recent(self, button: Button) -> None:
        """Oeffnet ein zuletzt verwendetes Fahrtenbuch."""
        btn_id = button.id or ""
        path_str = self._recent_path_by_id.get(btn_id, "")
        if not path_str:
            return
        if not Path(path_str).exists():
            self.notify(t("start.notify.recent_missing", path=path_str), severity="warning")
            return
        self.dismiss((path_str, None))

    def _run_backup(self) -> None:
        """Fuehrt das Backup des aktuellen Fahrtenbuchs durch."""
        if self._on_backup is None:
            self.notify(t("start.notify.backup_none"), severity="warning")
            return
        try:
            backup_path = self._on_backup()
            self.notify(t("start.notify.backup_done", name=backup_path.name), severity="information")
        except Exception as e:
            self.notify(t("start.notify.backup_failed", error=e), severity="error")

    def action_cancel(self) -> None:
        """Bricht ab."""
        self.dismiss(None)
