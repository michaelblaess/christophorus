"""Export der Fahrten als Excel, JSON oder Markdown.

Denselben Auftrag wie die TUI, nur ohne Speichern-Dialog: die Datei entsteht in einem
temporaeren Verzeichnis und geht als Download an den Browser. Die Arbeitskopie bleibt sauber.
"""

from __future__ import annotations

import tempfile
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote

from christo.i18n import month_name
from christo.models.export_format import EXPORT_FORMATS, ExportFormat, format_for_key
from christo.models.export_job import ExportJob
from christo.services.exporters import write_export
from christo.services.formatting import format_km
from christo.web.context import Context, Monat

# Die Kennungen, die die Auswahl im Formular schickt
FORMAT_NACH_WAHL = {"xlsx": "excel", "json": "json", "md": "markdown"}
MEDIENTYPEN = {
    "excel": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "json": "application/json; charset=utf-8",
    "markdown": "text/markdown; charset=utf-8",
}


@dataclass(frozen=True)
class Ausgabe:
    """Eine fertige Exportdatei im Speicher."""

    inhalt: bytes
    dateiname: str
    medientyp: str

    @property
    def headers(self) -> dict[str, str]:
        """Der Download-Kopf, Umlaute nach RFC 5987 kodiert."""
        return {"Content-Disposition": f"attachment; filename*=UTF-8''{quote(self.dateiname)}"}


def format_aus_wahl(wahl: str) -> ExportFormat:
    """Das Ausgabeformat zur Auswahl im Formular, im Zweifel Excel."""
    return format_for_key(FORMAT_NACH_WAHL.get(wahl, "excel")) or EXPORT_FORMATS[0]


def baue(ctx: Context, monat: Monat, jahresexport: bool) -> tuple[ExportJob, str] | None:
    """Stellt den Auftrag zusammen, wie `_build_export_job` in der TUI.

    Returns:
        Auftrag und Namensstamm, oder None wenn es im Zeitraum nichts zu exportieren gibt.
    """
    db = ctx.db()
    vehicle = ctx.vehicle
    if vehicle.name and vehicle.plate:
        titel = f"Fahrtenbuch {vehicle.name} ({vehicle.plate})"
        kennzeichen = f" ({vehicle.name} - {vehicle.plate})"
    elif vehicle.name:
        titel = f"Fahrtenbuch {vehicle.name}"
        kennzeichen = f" ({vehicle.name})"
    else:
        titel, kennzeichen = "Fahrtenbuch", ""
    leasing = f"{format_km(vehicle.lease_km_per_month)} km / Monat Leasing"

    if jahresexport:
        fahrten = db.get_trips_for_year(monat.jahr)
        # Dezember des Vorjahrs zeigt der Steuerberatung den Kettenstart
        if db.get_setting("export_include_prev_december", "0") == "1":
            vorjahr = db.get_trips_for_month(monat.jahr - 1, 12)
            if vorjahr:
                fahrten = vorjahr + fahrten
        untertitel = f"{monat.jahr} - {leasing}"
        stamm = f"Fahrtenbuch {monat.jahr}{kennzeichen}"
    else:
        fahrten = db.get_trips_for_month(monat.jahr, monat.monat)
        untertitel = f"{month_name(monat.monat, lang='de')} {monat.jahr} - {leasing}"
        stamm = f"Fahrtenbuch {monat.jahr}-{monat.monat:02d}{kennzeichen}"

    if not fahrten:
        return None

    auftrag = ExportJob(
        trips=fahrten,
        title=titel,
        subtitle=untertitel,
        year=monat.jahr,
        month=None if jahresexport else monat.monat,
        group_by_month=jahresexport,
        category_labels={code: label for label, code in ctx.kategorien()},
        vehicle_name=vehicle.name,
        vehicle_plate=vehicle.plate,
    )
    return auftrag, stamm


def schreibe(auftrag: ExportJob, stamm: str, ausgabeformat: ExportFormat) -> Ausgabe:
    """Schreibt den Auftrag und gibt die fertige Datei zurueck."""
    with tempfile.TemporaryDirectory(prefix="christo-web-") as ordner:
        ziel = Path(ordner) / f"{stamm}{ausgabeformat.suffix}"
        write_export(ausgabeformat, auftrag, ziel)
        inhalt = ziel.read_bytes()
    return Ausgabe(
        inhalt=inhalt,
        dateiname=ziel.name,
        medientyp=MEDIENTYPEN.get(ausgabeformat.key, "application/octet-stream"),
    )
