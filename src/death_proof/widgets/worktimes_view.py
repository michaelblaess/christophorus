"""Arbeitsstunden-Ansicht als einbettbares Widget."""

from typing import Any

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.message import Message
from textual.widgets import Button, DataTable, Input, Label, Static

from death_proof.i18n import month_name, t


class WorktimesView(Vertical):
    """Tabelle der monatlichen Arbeitsstunden mit Inline-Bearbeitung."""

    DEFAULT_CSS = """
    WorktimesView {
        height: 1fr;
        min-height: 10;
        border: solid $accent;
    }
    WorktimesView DataTable {
        height: 1fr;
    }
    WorktimesView .edit-row {
        height: auto;
        padding: 0 1;
        dock: bottom;
        background: $surface;
    }
    WorktimesView .edit-row Label {
        width: 14;
        padding: 0 1;
    }
    WorktimesView .edit-row Input {
        width: 24;
    }
    WorktimesView .edit-row Button {
        margin-left: 1;
    }
    WorktimesView #wt-year-label {
        width: 1fr;
        text-align: right;
        color: $text-muted;
        padding: 0 1;
    }
    """

    class WorktimeChanged(Message):
        """Wird gesendet wenn Arbeitsstunden gespeichert werden."""

        def __init__(self, year: int, month: int, hours: float) -> None:
            super().__init__()
            self.year = year
            self.month = month
            self.hours = hours

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._year = 0
        self._worktimes: dict[int, float] = {}
        self._selected_month: int = 0

    def compose(self) -> ComposeResult:
        yield DataTable(id="wt-data", cursor_type="row", zebra_stripes=True)
        with Horizontal(classes="edit-row"):
            yield Label(t("worktimes.label.hours_input"))
            yield Input(placeholder=t("worktimes.placeholder.hours"), id="wt-hours-input")
            yield Button(t("worktimes.btn_save"), variant="primary", id="btn-wt-save")
            yield Static("", id="wt-year-label")

    def on_mount(self) -> None:
        """Spalten anlegen."""
        table = self.query_one("#wt-data", DataTable)
        table.add_columns(
            t("worktimes.col.month"),
            t("worktimes.col.hours"),
            t("worktimes.col.per_day"),
        )

    def load_data(self, year: int, worktimes: list[dict[str, Any]]) -> None:
        """Laedt die Arbeitsstunden fuer ein Jahr."""
        self._year = year
        self._worktimes.clear()

        for wt in worktimes:
            month = int(wt.get("month", 0))
            hours = float(wt.get("hours", 0.0))
            self._worktimes[month] = hours

        self._rebuild_table()
        self.query_one("#wt-year-label", Static).update(t("worktimes.year_label", year=year))

    def _rebuild_table(self) -> None:
        """Baut die Tabelle neu auf."""
        table = self.query_one("#wt-data", DataTable)
        table.clear()

        total_hours = 0.0
        for month_nr in range(1, 13):
            hours = self._worktimes.get(month_nr, 0.0)
            total_hours += hours
            hours_str = f"{hours:.2f}" if hours > 0 else "—"
            per_day = f"{hours / 22:.2f}" if hours > 0 else "—"

            style = "" if hours > 0 else "dim"
            table.add_row(
                Text(month_name(month_nr), style=style),
                Text(hours_str, style="bold" if hours > 0 else "dim"),
                Text(per_day, style=style),
                key=str(month_nr),
            )

        # Summenzeile
        avg = total_hours / 12 if total_hours > 0 else 0.0
        table.add_row(
            Text(t("worktimes.total_label"), style="bold"),
            Text(f"{total_hours:.2f}", style="bold"),
            Text(f"\u00d8 {avg:.2f}", style="bold"),
            key="total",
        )

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Zeigt den ausgewaehlten Monat im Eingabefeld."""
        row_key = str(event.row_key.value) if event.row_key else ""
        if row_key == "total":
            return
        try:
            month_nr = int(row_key)
        except ValueError:
            return
        self._selected_month = month_nr
        hours = self._worktimes.get(month_nr, 0.0)
        hours_input = self.query_one("#wt-hours-input", Input)
        hours_input.value = f"{hours:.2f}" if hours > 0 else ""
        hours_input.placeholder = f"{month_name(month_nr)} {self._year}"

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Speichert die Arbeitsstunden."""
        if event.button.id != "btn-wt-save":
            return
        if self._selected_month == 0 or self._year == 0:
            return

        hours_input = self.query_one("#wt-hours-input", Input)
        try:
            hours = float(hours_input.value.strip().replace(",", "."))
        except ValueError:
            return

        self._worktimes[self._selected_month] = hours
        self._rebuild_table()
        self.post_message(
            self.WorktimeChanged(self._year, self._selected_month, hours),
        )
