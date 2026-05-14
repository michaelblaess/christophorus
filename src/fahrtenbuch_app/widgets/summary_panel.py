"""Zusammenfassungspanel mit km-Statistiken."""

from rich.text import Text
from textual.app import RenderResult
from textual.widget import Widget

from fahrtenbuch_app.models.trip import MonthData
from fahrtenbuch_app.services.formatting import format_km


class SummaryPanel(Widget):
    """Zeigt km-Zusammenfassung fuer den aktuellen Monat."""

    DEFAULT_CSS = """
    SummaryPanel {
        height: 3;
        padding: 0 1;
        background: $surface;
    }
    """

    def __init__(self, **kwargs: object) -> None:
        super().__init__(**kwargs)
        self._month_data: MonthData | None = None
        self._lease_km: int = 1500

    def update_data(self, month_data: MonthData, lease_km: int = 1500) -> None:
        """Aktualisiert die Zusammenfassung."""
        self._month_data = month_data
        self._lease_km = lease_km
        self.refresh()

    def render(self) -> RenderResult:
        """Rendert die Zusammenfassung."""
        if self._month_data is None or not self._month_data.trips:
            return Text("  Druecke [N] um eine neue Fahrt anzulegen", style="dim")

        md = self._month_data
        text = Text()
        text.append("  km gesamt: ", style="dim")
        text.append(format_km(md.km_total), style="bold")
        text.append("  |  ", style="dim")

        text.append("geschaeftl.: ", style="dim")
        biz_pct = md.business_percentage
        # Gruen fuer gute Quote, rot fuer kritisch — alles andere neutral
        biz_style = "bold green" if biz_pct >= 70 else ("bold red" if biz_pct < 50 else "bold")
        text.append(f"{format_km(md.km_business)} ({biz_pct:.0f}%)", style=biz_style)
        text.append("  |  ", style="dim")

        text.append("privat: ", style="dim")
        priv_pct = 100 - biz_pct if md.km_total > 0 else 0
        text.append(f"{format_km(md.km_private)} ({priv_pct:.0f}%)", style="bold")
        text.append("  |  ", style="dim")

        text.append("Leasing: ", style="dim")
        lease_pct = md.km_total / self._lease_km * 100 if self._lease_km > 0 else 0
        # Rot wenn das Leasing-Limit gerissen wird, sonst neutral
        lease_style = "bold red" if lease_pct > 110 else "bold"
        text.append(f"{format_km(self._lease_km)} ({lease_pct:.0f}%)", style=lease_style)

        return text
