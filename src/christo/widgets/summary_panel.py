"""Zusammenfassung der km-Statistiken als Statusleiste."""

from typing import Any

from textual_widgets import StatusBar, StatusItem

from christo.i18n import t
from christo.models.trip import MonthData
from christo.services.formatting import format_km


class SummaryPanel(StatusBar):  # type: ignore[misc]
    """km gesamt, geschaeftlich, privat und Leasing fuer den Monat.

    Rahmen und Trenner kommen aus der StatusBar in textual-widgets - damit
    sieht die Leiste in allen Anwendungen gleich aus. Hier steht nur, welche
    Zahlen erscheinen.
    """

    def __init__(self, hint: str = "", **kwargs: Any) -> None:
        # Den Hinweis liefert die App: welche Taste darin steht, weiss nur die
        # aufgeloeste Tastenbelegung, und die kennt das Widget nicht.
        super().__init__(hint=hint, **kwargs)
        self._month_data: MonthData | None = None
        self._lease_km: int = 1500

    def update_data(self, month_data: MonthData, lease_km: int = 1500) -> None:
        """Aktualisiert die Zusammenfassung."""
        self._month_data = month_data
        self._lease_km = lease_km
        if month_data is None or not month_data.trips:
            self.clear()
            return
        self.set_items(self._items_bauen(month_data))

    def _items_bauen(self, md: MonthData) -> list[StatusItem]:
        biz_pct = md.business_percentage
        # Gruen fuer gute Quote, rot fuer kritisch - alles andere neutral.
        biz_style = "bold green" if biz_pct >= 70 else ("bold red" if biz_pct < 50 else "bold")
        priv_pct = 100 - biz_pct if md.km_total > 0 else 0
        lease_pct = md.km_total / self._lease_km * 100 if self._lease_km > 0 else 0
        lease_style = "bold red" if lease_pct > 110 else "bold"

        return [
            StatusItem(t("summary.km_total"), format_km(md.km_total)),
            StatusItem(
                t("summary.business"),
                t("summary.percent_of", km=format_km(md.km_business), pct=biz_pct),
                value_style=biz_style,
            ),
            StatusItem(
                t("summary.private"),
                t("summary.percent_of", km=format_km(md.km_private), pct=priv_pct),
            ),
            StatusItem(
                t("summary.leasing"),
                t("summary.percent_of", km=format_km(self._lease_km), pct=lease_pct),
                value_style=lease_style,
            ),
        ]
