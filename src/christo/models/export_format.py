"""Die Ausgabeformate des Fahrtenbuch-Exports.

Ein Format ist hier nur seine Kennung, seine Dateiendung und die
i18n-Schluessel seiner Beschriftungen. Welcher Dienst schreibt, steht bewusst
NICHT hier - so kennen Oberflaeche und Dienste dieselbe Liste, ohne dass das
Modell von den Exportern abhaengt.

Aufbau uebernommen aus jira-timesheet (models/export_format.py, v1.22.1),
ohne PDF - das Fahrtenbuch hatte nie einen PDF-Export.

Public API:
    - `ExportFormat` - ein Format.
    - `EXCEL` / `JSON` / `MARKDOWN` - die einzelnen Formate.
    - `EXPORT_FORMATS` - alle Formate in der Reihenfolge des Dialogs.
    - `DEFAULT_FORMAT` - das vorausgewaehlte Format.
    - `format_for_suffix()` / `format_for_path()` / `format_for_key()`.
    - `suggested_name()` - der vorgeschlagene Dateiname.
    - `swap_suffix()` - Dateiname auf ein anderes Format umstellen.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


@dataclass(frozen=True)
class ExportFormat:
    """Ein Ausgabeformat des Exports.

    Attributes:
        key: Interne Kennung, taucht in Tests auf.
        suffix: Die Dateiendung mit fuehrendem Punkt, immer klein.
        filter_key: i18n-Schluessel des Eintrags im Filter-Auswahlfeld.
        name_key: i18n-Schluessel des kurzen Namens fuer Meldungen.
    """

    key: str
    suffix: str
    filter_key: str
    name_key: str


EXCEL = ExportFormat("excel", ".xlsx", "save_dialog.filter_excel", "format.excel")
JSON = ExportFormat("json", ".json", "save_dialog.filter_json", "format.json")
MARKDOWN = ExportFormat("markdown", ".md", "save_dialog.filter_markdown", "format.markdown")

EXPORT_FORMATS: tuple[ExportFormat, ...] = (EXCEL, JSON, MARKDOWN)
"""Alle Formate in der Reihenfolge, in der sie im Dialog stehen.

Erst das Format zum Abgeben (Excel fuer die Steuerberatung), dann die beiden
zum Weiterverarbeiten.
"""

DEFAULT_FORMAT: ExportFormat = EXPORT_FORMATS[0]
"""Das beim Oeffnen des Dialogs vorausgewaehlte Format."""

_BY_SUFFIX: dict[str, ExportFormat] = {f.suffix: f for f in EXPORT_FORMATS}
_BY_KEY: dict[str, ExportFormat] = {f.key: f for f in EXPORT_FORMATS}


def format_for_suffix(suffix: str) -> ExportFormat | None:
    """Sucht das Format zu einer Dateiendung.

    Args:
        suffix: Die Endung, mit oder ohne fuehrenden Punkt, Gross-/Kleinschreibung egal.

    Returns:
        Das Format, oder None wenn die Endung zu keinem gehoert.
    """
    raw = suffix.strip().lower()
    if raw and not raw.startswith("."):
        raw = f".{raw}"
    return _BY_SUFFIX.get(raw)


def format_for_path(path: Path | str) -> ExportFormat | None:
    """Sucht das Format zur Endung eines Pfades.

    Args:
        path: Der Pfad oder Dateiname.

    Returns:
        Das Format, oder None wenn die Endung zu keinem gehoert.
    """
    return format_for_suffix(Path(path).suffix)


def format_for_key(key: str) -> ExportFormat | None:
    """Sucht das Format zu seiner Kennung.

    Args:
        key: Die Kennung, z.B. "excel".

    Returns:
        Das Format, oder None bei unbekannter Kennung.
    """
    return _BY_KEY.get(key.strip().lower())


def suggested_name(target: ExportFormat, stem: str, now: datetime | None = None) -> str:
    """Baut den vorgeschlagenen Dateinamen fuer ein Format.

    Der Zeitstempel bleibt aus dem frueheren Excel-Export: eine vorherige
    Datei, die noch in Excel offen ist, wuerde sonst beim Ueberschreiben mit
    "Permission denied" scheitern.

    Args:
        target: Das Ausgabeformat, es liefert die Endung.
        stem: Der sprechende Teil, z.B. "Fahrtenbuch 2024-05 (Audi A5 - B-XX 1)".
        now: Zeitpunkt fuer den Zeitstempel. None nimmt die aktuelle Zeit -
            ein Test setzt ihn fest, statt gegen die Uhr zu pruefen.

    Returns:
        Der Dateiname, ohne Verzeichnis.
    """
    stempel = now if now is not None else datetime.now()
    return f"{stem} {stempel:%Y%m%d-%H%M%S}{target.suffix}"


def swap_suffix(filename: str, target: ExportFormat) -> str:
    """Stellt einen Dateinamen auf ein anderes Format um.

    Traegt der Name schon die Endung eines bekannten Formats, wird sie
    ersetzt. Jede andere Endung bleibt stehen und die neue tritt dahinter -
    aus "Fahrtenbuch v1.2" wird also "Fahrtenbuch v1.2.md" und nicht
    "Fahrtenbuch v1.md". Was der Anwender getippt hat, geht dabei nie verloren.

    Args:
        filename: Der aktuelle Dateiname ohne Verzeichnis.
        target: Das Format, auf das umgestellt wird.

    Returns:
        Der Dateiname mit der Endung des Zielformats.
    """
    name = filename.strip()
    if not name:
        return name
    current = Path(name).suffix
    if current.lower() == target.suffix:
        return name
    if current.lower() in _BY_SUFFIX:
        return f"{name[: -len(current)]}{target.suffix}"
    return f"{name}{target.suffix}"
