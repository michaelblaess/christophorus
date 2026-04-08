"""File-Picker-Screen mit DirectoryTree."""

from pathlib import Path

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, DirectoryTree, Input, Label, Static


class FilePickerScreen(ModalScreen[Path | None]):
    """Dateiauswahl-Dialog auf Basis von DirectoryTree."""

    DEFAULT_CSS = """
    FilePickerScreen {
        align: center middle;
    }
    FilePickerScreen > Vertical {
        width: 80;
        height: 30;
        background: $surface;
        border: double $accent;
        padding: 1 2;
    }
    FilePickerScreen #picker-title {
        text-style: bold;
        color: $accent;
        margin-bottom: 1;
    }
    FilePickerScreen #dir-tree {
        height: 1fr;
        border: solid $surface-lighten-1;
        margin-bottom: 1;
    }
    FilePickerScreen #path-row {
        height: auto;
        margin-bottom: 1;
    }
    FilePickerScreen #path-row Label {
        width: 10;
        padding: 0 1;
    }
    FilePickerScreen #path-row Input {
        width: 1fr;
    }
    FilePickerScreen .button-row {
        height: auto;
        align: right middle;
    }
    FilePickerScreen Button {
        margin-left: 1;
    }
    """

    BINDINGS = [
        Binding("escape", "cancel", "Abbrechen"),
    ]

    def __init__(self, start_path: Path, **kwargs: object) -> None:
        super().__init__(**kwargs)
        self._start_path = start_path
        self._selected: Path | None = None

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static("Datei auswaehlen", id="picker-title")
            yield DirectoryTree(str(self._start_path), id="dir-tree")
            with Horizontal(id="path-row"):
                yield Label("Ausgewaehlt:")
                yield Input(
                    placeholder="(noch keine Datei ausgewaehlt)",
                    id="selected-path",
                )
            with Horizontal(classes="button-row"):
                yield Button("Auswaehlen", variant="primary", id="btn-select", disabled=True)
                yield Button("Abbrechen", id="btn-cancel")

    def on_directory_tree_file_selected(
        self, event: DirectoryTree.FileSelected
    ) -> None:
        """Zeigt den gewaehlten Pfad an und aktiviert den Auswaehlen-Button."""
        self._selected = event.path
        self.query_one("#selected-path", Input).value = str(event.path)
        self.query_one("#btn-select", Button).disabled = False

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-select":
            self.dismiss(self._selected)
        else:
            self.dismiss(None)

    def action_cancel(self) -> None:
        self.dismiss(None)
