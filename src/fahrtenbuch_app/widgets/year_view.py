"""Jahresuebersicht als Widget (nicht Modal)."""

from rich.text import Text
from textual.app import ComposeResult, RenderResult
from textual.containers import Horizontal, VerticalScroll
from textual.widget import Widget
from textual.widgets import Static

from fahrtenbuch_app.models.trip import MonthData
from fahrtenbuch_app.services.formatting import format_km

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
        height: 9;
        padding: 1 2;
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
        self._problem_count: int = 0

    def render(self) -> RenderResult:
        """Rendert die Monatskachel mit Progressbar."""
        text = Text()
        name = _MONTH_NAMES[self._month - 1]
        problem_suffix = ""
        if self._problem_count > 0:
            problem_suffix = f"  !{self._problem_count}"

        if self._km_total == 0:
            text.append(f"{name}{problem_suffix}\n", style="bold dim")
            if self._problem_count > 0:
                text.append(f"{self._problem_count} Plausi-Befunde", style="bold red")
            else:
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
        if self._problem_count > 0:
            text.append(f"  !{self._problem_count}", style="bold red")
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
        height: auto;
        width: 1fr;
    }
    QuarterRow .quarter-label {
        width: 4;
        padding: 2 0;
        text-style: bold;
    }
    """


class YearView(VerticalScroll):
    """Jahresuebersicht als einbettbares Widget."""

    DEFAULT_CSS = """
    YearView {
        height: 1fr;
        min-height: 10;
        border: solid $accent;
    }
    YearView .year-title {
        text-align: center;
        text-style: bold;
        margin-bottom: 1;
    }
    YearView .year-summary {
        height: auto;
        padding: 1;
        margin-top: 1;
        border-top: solid $accent;
    }
    """

    def __init__(self, **kwargs: object) -> None:
        super().__init__(**kwargs)
        self._title_widget = Static("", classes="year-title")
        self._summary_widget = Static("", classes="year-summary")
        self._loaded_year: int = 0
        self._month_data: dict[int, MonthData] = {}
        self._lease_km: int = 1500

    def compose(self) -> ComposeResult:
        """Erstellt das statische Layout einmalig."""
        yield self._title_widget
        for q in range(4):
            with QuarterRow():
                yield Static(_QUARTER_NAMES[q], classes="quarter-label")
                for m_offset in range(3):
                    yield MonthTile(month=q * 3 + m_offset + 1)
        yield self._summary_widget

    def load_data(
        self,
        year: int,
        month_data: dict[int, MonthData],
        lease_km: int = 1500,
        problem_months: dict[int, int] | None = None,
    ) -> None:
        """Aktualisiert die Jahresuebersicht mit neuen Daten."""
        self._loaded_year = year
        self._month_data = month_data
        self._lease_km = lease_km
        self._title_widget.update(f"Jahresuebersicht {year}")
        problems = problem_months or {}

        # MonthTiles aktualisieren
        tiles = list(self.query(MonthTile))
        for tile in tiles:
            md = month_data.get(tile._month)
            tile._km_total = md.km_total if md else 0
            tile._km_business = md.km_business if md else 0
            tile._km_private = md.km_private if md else 0
            tile._lease_km = lease_km
            tile._trip_count = len(md.trips) if md else 0
            tile._problem_count = problems.get(tile._month, 0)
            tile.refresh()

        # Jahres-Zusammenfassung aktualisieren
        self._summary_widget.update(self._build_summary_text(month_data, lease_km, year))

    def set_problem_months(self, problem_months: dict[int, int]) -> None:
        """Setzt die Plausi-Befunde pro Monat und aktualisiert die Kacheln."""
        for tile in self.query(MonthTile):
            tile._problem_count = problem_months.get(tile._month, 0)
            tile.refresh()

    def _build_summary_text(
        self,
        month_data: dict[int, MonthData],
        lease_km: int,
        year: int,
    ) -> Text:
        """Erstellt den Zusammenfassungstext."""
        total_km = sum(md.km_total for md in month_data.values())
        total_biz = sum(md.km_business for md in month_data.values())
        total_priv = sum(md.km_private for md in month_data.values())
        total_lease = lease_km * 12
        biz_pct = total_biz / total_km * 100 if total_km > 0 else 0

        text = Text()
        text.append(f"Jahresgesamt {year}\n", style="bold")
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

        return text
