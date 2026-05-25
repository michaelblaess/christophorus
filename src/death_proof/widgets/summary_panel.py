"""Zusammenfassungspanel mit km-Statistiken."""

from rich.text import Text
from textual.app import RenderResult
from textual.widget import Widget

from death_proof.i18n import t
from death_proof.models.trip import MonthData
from death_proof.services.formatting import format_km


class SummaryPanel(Widget):
    """Zeigt km-Zusammenfassung fuer den aktuellen Monat."""

    DEFAULT_CSS = """
    SummaryPanel {
        height: 1;
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
            return Text(t("summary.empty_hint"), style="dim")

        md = self._month_data
        text = Text()
        text.append(t("summary.km_total"), style="dim")
        text.append(format_km(md.km_total), style="bold")
        text.append("  |  ", style="dim")

        text.append(t("summary.business"), style="dim")
        biz_pct = md.business_percentage
        # Gruen fuer gute Quote, rot fuer kritisch — alles andere neutral
        biz_style = "bold green" if biz_pct >= 70 else ("bold red" if biz_pct < 50 else "bold")
        text.append(t("summary.percent_of", km=format_km(md.km_business), pct=biz_pct), style=biz_style)
        text.append("  |  ", style="dim")

        text.append(t("summary.private"), style="dim")
        priv_pct = 100 - biz_pct if md.km_total > 0 else 0
        text.append(t("summary.percent_of", km=format_km(md.km_private), pct=priv_pct), style="bold")
        text.append("  |  ", style="dim")

        text.append(t("summary.leasing"), style="dim")
        lease_pct = md.km_total / self._lease_km * 100 if self._lease_km > 0 else 0
        lease_style = "bold red" if lease_pct > 110 else "bold"
        text.append(t("summary.percent_of", km=format_km(self._lease_km), pct=lease_pct), style=lease_style)

        return text
