"""Zellwerte einer Fahrt, geteilt von Excel- und Markdown-Export.

Die Regeln standen bisher nur im Excel-Export. Mit dem Markdown-Export waeren
sie ein zweites Mal entstanden und beim naechsten Wunsch auseinandergelaufen.
"""

from datetime import datetime

from christo.i18n import month_name
from christo.models.trip import Trip


def iso_to_date(iso: str) -> datetime | None:
    """Konvertiert YYYY-MM-DD zu datetime, None bei Fehler."""
    try:
        return datetime.strptime(iso, "%Y-%m-%d")
    except (ValueError, TypeError):
        return None


def format_time_range(time_from: str, time_to: str) -> str:
    """Formatiert Fahrzeit als 'HH:MM - HH:MM' oder einzeln."""
    if time_from and time_to:
        return f"{time_from} - {time_to}"
    if time_from:
        return time_from
    if time_to:
        return time_to
    return ""


def is_untimed_private(trip: Trip) -> bool:
    """Privater Sammeleintrag ohne Zeit UND ohne Ziel — Mehrtages-Aggregat.

    Wird im Export ohne Datum ausgegeben (Vorlage zeigt nur den Reisezweck
    plus km), weil das exakte Startdatum bei solchen Fahrten nicht sinnvoll
    ist. Privatfahrten mit konkretem Ziel (z.B. Supermarkt) behalten ihr
    Datum, auch wenn die Uhrzeit fehlt.
    """
    return trip.category == "private" and not trip.time_from.strip() and not trip.destination.strip()


def month_label(year: int, month: int) -> str:
    """Gibt 'Mai 2024' fuer (2024, 5) zurueck, auf Deutsch wie die Excel-Vorlage."""
    if 1 <= month <= 12:
        return f"{month_name(month, lang='de')} {year}"
    return f"{year}-{month:02d}"
