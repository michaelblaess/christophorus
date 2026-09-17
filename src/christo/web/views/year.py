"""Die Jahresuebersicht: zwoelf Monatskacheln mit Leasing-Fortschritt.

Gleiche Aussage wie die Kacheln der TUI - wie voll ist der Monat gegenueber den
Inklusivkilometern, wie hoch ist der geschaeftliche Anteil, gibt es Befunde.
"""

from __future__ import annotations

from typing import Any

from fasthtml.common import A, Div, Span

from christo.i18n import month_name
from christo.models.trip import MonthData
from christo.services.formatting import format_km
from christo.web.context import Context, Monat

FT = Any


def _stufe(prozent: float) -> str:
    """Die Farbrolle des Balkens: gruen im Rahmen, warnend knapp darueber, rot deutlich."""
    if prozent <= 100:
        return "gut"
    return "warnung" if prozent <= 110 else "schlecht"


def _kachel(jahr: int, monat: int, daten: MonthData | None, leasing_km: int, befunde: int) -> FT:
    km = daten.km_total if daten else 0
    fahrten = len(daten.trips) if daten else 0
    prozent = min(km / leasing_km * 100, 150) if leasing_km > 0 else 0.0
    anteil = daten.business_percentage if daten and km else 0.0
    return A(
        Div(
            Span(month_name(monat), cls="kachel-monat"),
            Span(f"▲ {befunde}", cls="kachel-befunde") if befunde else None,
            Span(f"{prozent:.0f} %" if km else "", cls=f"kachel-prozent stufe-{_stufe(prozent)}"),
            cls="kachel-kopf",
        ),
        Div(
            Div(cls=f"balken-fuellung stufe-{_stufe(prozent)}", style=f"width: {min(prozent, 100):.0f}%"),
            cls="balken",
        ),
        Div(
            Span(f"{format_km(km)} km", cls="kachel-km") if km else Span("keine Fahrten", cls="gedaempft"),
            Span(f"von {format_km(leasing_km)}", cls="gedaempft") if km else None,
            cls="kachel-zeile",
        ),
        Div(
            Span(f"geschäftlich {anteil:.0f} %", cls="gruen" if anteil >= 70 else "gedaempft") if km else None,
            Span(f"{fahrten} Fahrten", cls="gedaempft") if km else None,
            cls="kachel-zeile",
        ),
        href=f"/fahrten?jahr={jahr}&monat={monat}",
        cls="kachel",
    )


def ansicht(ctx: Context, monat: Monat) -> FT:
    """Die zwoelf Kacheln und die Jahressumme."""
    db = ctx.db()
    monatsdaten = db.get_all_month_data(monat.jahr)
    leasing_km = ctx.vehicle.lease_km_per_month or 1500
    befunde = ctx.befunde_je_monat(monat.jahr)
    km_gesamt = sum(md.km_total for md in monatsdaten.values())
    km_geschaeftlich = sum(md.km_business for md in monatsdaten.values())
    km_privat = sum(md.km_private for md in monatsdaten.values())
    jahresleasing = leasing_km * 12
    anteil = km_geschaeftlich / km_gesamt * 100 if km_gesamt else 0.0
    rest = jahresleasing - km_gesamt
    return Div(
        Div(
            Span(f"Jahr {monat.jahr}", cls="legende"),
            Div(
                *[_kachel(monat.jahr, m, monatsdaten.get(m), leasing_km, befunde.get(m, 0)) for m in range(1, 13)],
                cls="kachelraster",
            ),
            cls="panel kachelpanel",
        ),
        Div(
            Span(f"km gesamt: {format_km(km_gesamt)}"),
            Span("|", cls="trenner"),
            Span(f"geschäftlich: {format_km(km_geschaeftlich)} ({anteil:.0f} %)", cls="gruen"),
            Span("|", cls="trenner"),
            Span(f"privat: {format_km(km_privat)}"),
            Span("|", cls="trenner"),
            Span(f"Leasing: {format_km(jahresleasing)} km"),
            Span("|", cls="trenner"),
            Span(
                f"{'noch' if rest >= 0 else 'darüber'}: {format_km(abs(rest))} km",
                cls="gruen" if rest >= 0 else "schwere-error",
            ),
            cls="panel summe",
        ),
    )
