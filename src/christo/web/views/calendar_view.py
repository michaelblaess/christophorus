"""Der Monatskalender: ein Feld je Tag mit Fahrten, Feiertag und Sperrtagen.

Dieselben Warnregeln wie in der TUI: geschaeftliche Fahrten an Feiertagen, an Wochenenden
und an gesperrten Tagen fallen auf. Ein Klick auf eine Fahrt oeffnet sie, das Pluszeichen
legt eine neue Fahrt an diesem Tag an.
"""

from __future__ import annotations

import calendar
from datetime import date, timedelta
from typing import Any

from fasthtml.common import Button, Div, Span

from christo.models.trip import Trip, TripDay
from christo.services.formatting import format_km
from christo.services.holiday_service import HolidayService
from christo.web.context import Context, Monat
from christo.web.views.trips import WOCHENTAGE

FT = Any


def _tage(ctx: Context, jahr: int, monat: int) -> dict[date, TripDay]:
    tage: dict[date, TripDay] = {}
    for trip in ctx.db().get_trips_for_month(jahr, monat):
        try:
            tag = date.fromisoformat(trip.date)
        except ValueError:
            continue
        tage.setdefault(tag, TripDay(day=tag)).trips.append(trip)
    return tage


def _sperrtage(ctx: Context) -> dict[date, str]:
    gesperrt: dict[date, str] = {}
    for eintrag in ctx.db().get_blacklist():
        try:
            gesperrt[date.fromisoformat(str(eintrag.get("date", "")))] = str(eintrag.get("reason", ""))
        except ValueError:
            continue
    return gesperrt


def _geschaeftlich_auffaellig(tag: TripDay) -> bool:
    """Geschaeftliche Fahrt, die an einem freien Tag erklaerungsbeduerftig ist.

    Geschaeftsessen bleiben aussen vor, wie in der TUI.
    """
    return any(
        trip.category == "business" and "geschaeftsessen" not in (trip.purpose or "").lower() for trip in tag.trips
    )


def _fahrt(ctx: Context, trip: Trip) -> FT:
    beschriftung = trip.purpose.strip() or trip.destination.split("\n")[0].strip() or ctx.kategoriename(trip.category)
    return Div(
        beschriftung,
        cls="kalendertag-fahrt" + ("" if trip.is_business_km else " privat"),
        title=beschriftung,
        hx_get=f"/fahrten/{trip.id}/bearbeiten",
        hx_target="#dialog",
        hx_swap="outerHTML",
    )


def _feld(ctx: Context, tag: date, im_monat: bool, daten: TripDay | None, feiertag: str, sperre: str) -> FT:
    if not im_monat:
        return Div(Span(f"{tag.day}", cls="kalendertag-nummer"), cls="kalendertag ausserhalb")

    wochenende = tag.weekday() >= 5
    auffaellig = daten is not None and _geschaeftlich_auffaellig(daten) and bool(wochenende or feiertag or sperre)
    klassen = ["kalendertag"]
    if wochenende or feiertag:
        klassen.append("frei")
    if sperre:
        klassen.append("gesperrt")
    if auffaellig:
        klassen.append("auffaellig")

    kopf = [
        Span(f"{tag.day}", cls="kalendertag-nummer"),
        Span(WOCHENTAGE[tag.weekday()], cls="kalendertag-wochentag"),
    ]
    if daten and daten.km_total:
        kopf.append(
            Span(
                f"{format_km(daten.km_total)} km",
                cls="kalendertag-km" + (" gruen" if daten.has_business and not auffaellig else ""),
            )
        )
    kopf.append(
        Button(
            "+",
            cls="kalendertag-neu",
            title=f"Neue Fahrt am {tag:%d.%m.%Y}",
            aria_label=f"Neue Fahrt am {tag:%d.%m.%Y}",
            hx_get=f"/fahrten/neu?datum={tag.isoformat()}",
            hx_target="#dialog",
            hx_swap="outerHTML",
        )
    )

    inhalt: list[FT] = [Div(*kopf, cls="kalendertag-kopf")]
    if sperre:
        inhalt.append(Div(f"gesperrt: {sperre}", cls="kalendertag-hinweis schwere-error"))
    elif feiertag:
        inhalt.append(Div(feiertag, cls="kalendertag-hinweis"))
    if auffaellig:
        inhalt.append(Div("▲ geschäftlich an einem freien Tag", cls="kalendertag-hinweis schwere-warning"))
    if daten:
        inhalt.extend(_fahrt(ctx, trip) for trip in daten.trips[:3])
        if len(daten.trips) > 3:
            inhalt.append(Div(f"+{len(daten.trips) - 3} weitere", cls="gedaempft"))
    return Div(*inhalt, cls=" ".join(klassen))


def ansicht(ctx: Context, monat: Monat) -> FT:
    """Das Monatsraster, Montag bis Sonntag."""
    daten = _tage(ctx, monat.jahr, monat.monat)
    feiertage = HolidayService(ctx.db().get_setting("federal_state", "BB")).get_holidays_in_month(
        monat.jahr, monat.monat
    )
    gesperrt = _sperrtage(ctx)

    erster = date(monat.jahr, monat.monat, 1)
    start = erster - timedelta(days=erster.weekday())
    letzter = date(monat.jahr, monat.monat, calendar.monthrange(monat.jahr, monat.monat)[1])
    wochen = ((letzter - start).days + 7) // 7

    felder = [Div(name, cls="kalender-kopf") for name in WOCHENTAGE]
    for versatz in range(wochen * 7):
        tag = start + timedelta(days=versatz)
        felder.append(
            _feld(
                ctx,
                tag,
                tag.month == monat.monat and tag.year == monat.jahr,
                daten.get(tag),
                feiertage.get(tag, ""),
                gesperrt.get(tag, ""),
            )
        )
    return Div(
        Span(monat.titel, cls="legende"),
        Div(*felder, cls="kalenderraster"),
        cls="panel kalenderpanel",
    )
