"""Konfigurationspanel mit Monatswahl und Fahrzeug-Info.

Duenner Wrapper um ``textual_widgets.InfoHeader`` — der eigentliche
Render-Code lebt in der Library.
"""

import os
import subprocess
import sys
from typing import Any

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.message import Message
from textual_widgets import InfoAction, InfoHeader, InfoItem

from christo.i18n import month_name, t
from christo.models.vehicle import Vehicle
from christo.services.formatting import format_km


class ConfigPanel(Vertical):
    """Zeigt Fahrzeug-Info, Leasingdaten, Monat/Jahr-Navigation und Verzeichnis.

    Auf zwei InfoHeader gemappt:
    - ``cfg-info``: Fahrzeug + Leasing + km + Zeitraum (4 Zeilen)
    - ``cfg-path``: Verzeichnis + Oeffnen-Action (1 Zeile)
    """

    DEFAULT_CSS = """
    ConfigPanel {
        height: auto;
    }
    ConfigPanel InfoHeader {
        margin-bottom: 0;
    }
    """

    class MonthChanged(Message):
        """Wird gesendet wenn der Monat gewechselt wird."""

        def __init__(self, year: int, month: int) -> None:
            super().__init__()
            self.year = year
            self.month = month

    def __init__(
        self,
        vehicle: Vehicle | None,
        year: int,
        month: int,
        fb_path: str = "",
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self._vehicle = vehicle
        self._year = year
        self._month = month
        self._fb_path = fb_path

    @property
    def year(self) -> int:
        return self._year

    @property
    def month(self) -> int:
        return self._month

    def compose(self) -> ComposeResult:
        yield InfoHeader(
            self._build_items(),
            columns=1,
            actions=[InfoAction("open_dir", t("config.open_dir"))],
            id="cfg-info",
        )

    def _build_items(self) -> list[InfoItem]:
        v = self._vehicle
        vehicle_str = f"{v.name}  ({v.plate})" if v and v.name else t("config.no_vehicle")
        contract = t("config.contract", number=v.contract_number) if v and v.contract_number else ""
        lease_dates = self._format_lease_dates(v)
        km_per_month = t("config.km_per_month", km=format_km(v.lease_km_per_month), months=v.lease_months) if v else ""
        km_range = self._format_km_range(v)
        km_total = self._format_km_total(v)

        # Pro Zeile zwei "Spalten" als ein Wert mit Padding zusammensetzen —
        # InfoHeader rendert ein striktes Label/Value-Raster, daher packen wir
        # rechte Zusatz-Infos hinter ein paar Leerzeichen.
        def join_two(left: str, right: str) -> str:
            if not right:
                return left
            return f"{left}    {right}"

        period_value = self._format_month()

        return [
            InfoItem("vehicle", t("config.label.vehicle"), join_two(vehicle_str, contract)),
            InfoItem("leasing", t("config.label.leasing"), join_two(lease_dates, km_per_month)),
            InfoItem("km_state", t("config.label.km_state"), join_two(km_range, km_total)),
            InfoItem("period", t("config.label.period"), period_value, navigable=True),
            InfoItem("path", t("config.label.directory"), self._fb_path or ""),
        ]

    def update_vehicle(self, vehicle: Vehicle | None, fb_path: str = "") -> None:
        """Aktualisiert die Fahrzeug-Anzeige."""
        self._vehicle = vehicle
        self._fb_path = fb_path
        try:
            info = self.query_one("#cfg-info", InfoHeader)
            info.set_items(self._build_items())
        except Exception:
            self.refresh()

    def update_month(self, year: int, month: int) -> None:
        """Aktualisiert Jahr und Monat in der Anzeige."""
        self._year = year
        self._month = month
        try:
            info = self.query_one("#cfg-info", InfoHeader)
            info.set_value("period", self._format_month())
        except Exception:
            self.refresh()

    def prev_month(self) -> None:
        if self._month == 1:
            self._month = 12
            self._year -= 1
        else:
            self._month -= 1
        self._post_month_changed()

    def next_month(self) -> None:
        if self._month == 12:
            self._month = 1
            self._year += 1
        else:
            self._month += 1
        self._post_month_changed()

    def _post_month_changed(self) -> None:
        try:
            info = self.query_one("#cfg-info", InfoHeader)
            info.set_value("period", self._format_month())
        except Exception:
            self.refresh()
        self.post_message(self.MonthChanged(self._year, self._month))

    def _format_month(self) -> str:
        return f"{month_name(self._month)} {self._year}"

    def _format_km_range(self, vehicle: Vehicle | None) -> str:
        if not vehicle:
            return ""
        return t("config.km_range", start=format_km(vehicle.start_km), end=format_km(vehicle.end_km))

    def _format_km_total(self, vehicle: Vehicle | None) -> str:
        if not vehicle:
            return ""
        return t("config.km_total", total=format_km(vehicle.total_driven_km))

    def _format_lease_dates(self, vehicle: Vehicle | None) -> str:
        if not vehicle:
            return ""
        start = self._format_date(vehicle.start_date)
        end = self._format_date(vehicle.end_date)
        if start and end:
            return t("config.lease_range", start=start, end=end)
        if start:
            return t("config.lease_from", start=start)
        return ""

    def _format_date(self, date_str: str) -> str:
        if not date_str:
            return ""
        try:
            parts = date_str.split("-")
            if len(parts) == 3:
                return f"{parts[2]}.{parts[1]}.{parts[0]}"
        except Exception:
            pass
        return date_str

    # ------------------------------------------------------------------
    # InfoHeader event handlers
    # ------------------------------------------------------------------
    def on_info_header_navigated(self, event: InfoHeader.Navigated) -> None:
        """Pfeil-Klick auf die Periode-Zeile schaltet Monat."""
        if event.key != "period":
            return
        event.stop()
        if event.direction == "prev":
            self.prev_month()
        else:
            self.next_month()

    def on_info_header_action_pressed(self, event: InfoHeader.ActionPressed) -> None:
        """Klick auf "Oeffnen" oeffnet das Fahrtenbuch-Verzeichnis."""
        if event.key != "open_dir" or not self._fb_path:
            return
        event.stop()
        _open_directory(self._fb_path)


def _open_directory(path: str) -> None:
    """Oeffnet ein Verzeichnis im nativen Datei-Explorer."""
    try:
        if sys.platform == "win32":
            os.startfile(path)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", path])
        else:
            subprocess.Popen(["xdg-open", path])
    except Exception:
        pass
