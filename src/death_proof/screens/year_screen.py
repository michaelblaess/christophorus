"""Jahresuebersicht mit 12 Monatskacheln."""

from rich.text import Text
from textual.app import ComposeResult, RenderResult
from textual.binding import Binding
from textual.containers import Horizontal, VerticalScroll
from textual.screen import ModalScreen
from textual.widget import Widget
from textual.widgets import Static

from death_proof.models.trip import MonthData
from death_proof.services.formatting import format_km

_MONTH_NAMES = [
    "Januar",
    "Februar",
    "Maerz",
    "April",
    "Mai",
    "Juni",
    "Juli",
    "August",
    "September",
    "Oktober",
    "November",
    "Dezember",
]
_QUARTER_NAMES = ["Q1", "Q2", "Q3", "Q4"]


class MonthTile(Widget):
    """Kachel fuer einen Monat in der Jahresuebersicht."""

    DEFAULT_CSS = """
    MonthTile {
        width: 1fr;
        height: 7;
        padding: 0 1;
        border: solid $surface-lighten-1;
        margin: 0 1;
    }
    """

    def __init__(
        self,
        month: int,
        km_total: int = 0,
        km_business: int = 0,
        km_private: int = 0,
        lease_km: int = 1500,
        trip_count: int = 0,
        **kwargs: object,
    ) -> None:
        super().__init__(**kwargs)
        self._month = month
        self._km_total = km_total
        self._km_business = km_business
        self._km_private = km_private
        self._lease_km = lease_km
        self._trip_count = trip_count

    def render(self) -> RenderResult:
        """Rendert die Monatskachel mit Progressbar."""
        text = Text()
        name = _MONTH_NAMES[self._month - 1]

        if self._km_total == 0:
            text.append(f"{name}\n", style="bold dim")
            text.append("keine Daten", style="dim")
            return text

        pct = min(self._km_total / self._lease_km * 100, 150) if self._lease_km > 0 else 0
        biz_pct = self._km_business / self._km_total * 100 if self._km_total > 0 else 0

        # Reduziertes Farbschema: gruen wenn gut, rot wenn kritisch, sonst neutral
        if pct <= 100:
            bar_style = "green"
        elif pct > 110:
            bar_style = "red"
        else:
            bar_style = ""

        biz_style = "green" if biz_pct >= 70 else ("red" if biz_pct < 50 else "")

        text.append(f"{name}", style="bold")
        text.append(f"  {pct:.0f}%\n", style=f"bold {bar_style}")

        bar_len = 20
        filled = int(min(pct, 100) / 100 * bar_len)
        text.append("\u2588" * filled, style=bar_style)
        text.append("\u2591" * (bar_len - filled), style="dim")
        text.append("\n")

        text.append(f"{format_km(self._km_total)} km", style="bold")
        text.append(f" / {format_km(self._lease_km)}", style="dim")
        text.append("\n")

        text.append(f"gesch.: {biz_pct:.0f}%", style=biz_style)
        text.append(f"  |  {self._trip_count} Fahrten", style="dim")

        return text


class QuarterRow(Horizontal):
    """Zeile mit 3 Monatskacheln + Quartalslabel."""

    DEFAULT_CSS = """
    QuarterRow {
        height: 8;
        width: 1fr;
        margin-bottom: 1;
    }
    QuarterRow .quarter-label {
        width: 4;
        padding: 1 0;
        text-style: bold;
    }
    """


class YearScreen(ModalScreen[None]):
    """Jahresuebersicht mit km-Statistiken pro Monat."""

    DEFAULT_CSS = """
    YearScreen {
        align: center middle;
    }
    YearScreen > VerticalScroll {
        width: 90;
        height: 42;
        background: $surface;
        border: thick $accent;
        padding: 1 2;
    }
    YearScreen #title {
        text-align: center;
        text-style: bold;
        margin-bottom: 1;
    }
    YearScreen #year-summary {
        height: auto;
        padding: 1;
        margin-top: 1;
        border-top: solid $accent;
    }
    """

    BINDINGS = [
        Binding("escape", "close", "Schliessen"),
    ]

    def __init__(
        self,
        year: int,
        month_data: dict[int, MonthData],
        lease_km: int = 1500,
        **kwargs: object,
    ) -> None:
        super().__init__(**kwargs)
        self._year = year
        self._month_data = month_data
        self._lease_km = lease_km

    def compose(self) -> ComposeResult:
        """Erstellt die Jahresuebersicht."""
        with VerticalScroll():
            yield Static(f"Jahresuebersicht {self._year}", id="title")

            for q in range(4):
                with QuarterRow():
                    yield Static(_QUARTER_NAMES[q], classes="quarter-label")
                    for m_offset in range(3):
                        month = q * 3 + m_offset + 1
                        md = self._month_data.get(month)
                        yield MonthTile(
                            month=month,
                            km_total=md.km_total if md else 0,
                            km_business=md.km_business if md else 0,
                            km_private=md.km_private if md else 0,
                            lease_km=self._lease_km,
                            trip_count=len(md.trips) if md else 0,
                        )

            yield self._build_summary()

    def _build_summary(self) -> Static:
        """Erstellt die Jahreszusammenfassung."""
        total_km = sum(md.km_total for md in self._month_data.values())
        total_biz = sum(md.km_business for md in self._month_data.values())
        total_priv = sum(md.km_private for md in self._month_data.values())
        total_lease = self._lease_km * 12
        biz_pct = total_biz / total_km * 100 if total_km > 0 else 0

        text = Text()
        text.append("Jahresgesamt\n", style="bold")
        text.append(f"km gesamt: {format_km(total_km)}", style="bold")
        text.append(f"  |  Leasing: {format_km(total_lease)}", style="dim")

        diff = total_km - total_lease
        diff_style = "bold red" if diff > 0 else "bold green"
        diff_sign = "+" if diff > 0 else ""
        text.append(f"  |  Differenz: {diff_sign}{format_km(abs(diff))} km", style=diff_style)
        text.append("\n")

        biz_style = "bold green" if biz_pct >= 70 else ("bold red" if biz_pct < 50 else "bold")
        text.append(f"geschaeftl.: {format_km(total_biz)} km ({biz_pct:.1f}%)", style=biz_style)
        text.append(f"  |  privat: {format_km(total_priv)} km ({100 - biz_pct:.1f}%)", style="bold")

        return Static(text, id="year-summary")

    def action_close(self) -> None:
        """Schliesst die Jahresuebersicht."""
        self.dismiss(None)
