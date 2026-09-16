"""Internationalisierung — leichtgewichtige JSON-basierte Sprachpakete.

Die Sprache wird einmalig beim App-Start ueber load_locale() gesetzt
(CLI --lang oder gespeicherte Einstellung). Sprachwechsel zur Laufzeit
erfordert einen App-Neustart.
"""

import json
import logging
from datetime import datetime
from importlib import resources

logger = logging.getLogger(__name__)

_strings: dict[str, str] = {}
_current_lang: str = "de"

SUPPORTED_LANGUAGES: tuple[str, ...] = ("de", "en")
DEFAULT_LANGUAGE: str = "de"


def load_locale(lang: str) -> None:
    """Laedt eine Sprachdatei (z.B. 'de', 'en')."""
    global _strings, _current_lang

    if lang not in SUPPORTED_LANGUAGES:
        logger.warning("Sprache '%s' nicht unterstuetzt, verwende '%s'", lang, DEFAULT_LANGUAGE)
        lang = DEFAULT_LANGUAGE

    try:
        locale_file = resources.files("christo") / "locale" / f"{lang}.json"
        raw = locale_file.read_text(encoding="utf-8")
        _strings = json.loads(raw)
        _current_lang = lang
    except Exception:
        logger.exception("Fehler beim Laden der Sprachdatei '%s'", lang)
        _strings = {}
        _current_lang = lang


def current_language() -> str:
    """Gibt die aktuell geladene Sprache zurueck."""
    return _current_lang


def t(key: str, **kwargs: object) -> str:
    """Uebersetzt einen Schluessel. Platzhalter via {name} und kwargs."""
    template = _strings.get(key, key)
    if kwargs:
        try:
            return template.format(**kwargs)
        except (KeyError, IndexError, ValueError):
            return template
    return template


def format_datetime(timestamp: str, lang: str | None = None) -> str:
    """Formatiert einen ISO-Timestamp culture-abhaengig (Datum + Uhrzeit).

    DE: dd.MM.yyyy HH:mm, EN/Fallback: yyyy-MM-dd HH:mm.
    Leere/ungueltige Eingabe wird durchgereicht.
    """
    if not timestamp:
        return "?"
    if lang is None:
        lang = _current_lang
    try:
        dt = datetime.fromisoformat(timestamp.replace(" ", "T"))
    except (ValueError, TypeError):
        return timestamp[:16].replace("T", " ")
    if lang == "de":
        return dt.strftime("%d.%m.%Y %H:%M")
    return dt.strftime("%Y-%m-%d %H:%M")


def format_date(timestamp: str, lang: str | None = None) -> str:
    """Nur Datum, ohne Uhrzeit (DE: TT.MM.JJJJ, EN: ISO)."""
    if not timestamp:
        return ""
    if lang is None:
        lang = _current_lang
    try:
        date_part = timestamp.split(" ")[0].split("T")[0]
        parts = date_part.split("-")
        if len(parts) != 3:
            return timestamp
        y, m, d = parts
    except (ValueError, IndexError):
        return timestamp
    if lang == "de":
        return f"{d}.{m}.{y}"
    return f"{y}-{m}-{d}"


def month_name(month: int, lang: str | None = None) -> str:
    """Sprachabhaengiger Monatsname (1-12)."""
    if month < 1 or month > 12:
        return ""
    if lang is None:
        lang = _current_lang
    de_names = [
        "Januar",
        "Februar",
        "März",
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
    en_names = [
        "January",
        "February",
        "March",
        "April",
        "May",
        "June",
        "July",
        "August",
        "September",
        "October",
        "November",
        "December",
    ]
    if lang == "de":
        return de_names[month - 1]
    return en_names[month - 1]


def weekday_short(weekday: int, lang: str | None = None) -> str:
    """Sprachabhaengiger Wochentag-Kurzname (0=Mo .. 6=So)."""
    if weekday < 0 or weekday > 6:
        return ""
    if lang is None:
        lang = _current_lang
    de = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]
    en = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    return (de if lang == "de" else en)[weekday]


def weekday_long(weekday: int, lang: str | None = None) -> str:
    """Sprachabhaengiger ausgeschriebener Wochentag (0=Montag .. 6=Sonntag)."""
    if weekday < 0 or weekday > 6:
        return ""
    if lang is None:
        lang = _current_lang
    de = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"]
    en = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    return (de if lang == "de" else en)[weekday]
