"""Die Arbeitszeit je Monat.

Anders als in der TUI stehen alle zwoelf Monate gleichzeitig zum Bearbeiten da - im Browser
ist ein Formular billiger als ein Dialog je Zeile. Ein leeres Feld loescht den Monat.
Die Spalte je Arbeitstag rechnet mit den echten Arbeitstagen des Monats, Feiertage des
eingestellten Bundeslands abgezogen.
"""

from __future__ import annotations

from typing import Any

from fasthtml.common import Button, Div, Form, Input, Span

from christo.i18n import month_name
from christo.services.formatting import format_km
from christo.services.holiday_service import HolidayService
from christo.web.context import Context, Monat

FT = Any


def _stunden(wert: float) -> str:
    return f"{wert:.2f}".replace(".", ",") if wert > 0 else ""


def ansicht(ctx: Context, monat: Monat, gespeichert: bool = False) -> FT:
    """Die Tabelle mit den zwoelf Monaten als Formular."""
    db = ctx.db()
    stunden = {int(w.get("month", 0)): float(w.get("hours", 0.0)) for w in db.get_worktimes(monat.jahr)}
    monatsdaten = db.get_all_month_data(monat.jahr)
    feiertage = HolidayService(db.get_setting("federal_state", "BB"))

    zeilen = []
    summe = 0.0
    erfasst = 0
    for nr in range(1, 13):
        wert = stunden.get(nr, 0.0)
        summe += wert
        erfasst += 1 if wert > 0 else 0
        arbeitstage = feiertage.count_workdays_in_month(monat.jahr, nr)
        je_tag = f"{wert / arbeitstage:.2f}".replace(".", ",") if wert > 0 and arbeitstage else "-"
        daten = monatsdaten.get(nr)
        zeilen.append(
            Div(
                Span(month_name(nr), cls="wz-monat"),
                Span(f"{arbeitstage}", cls="wz-zahl gedaempft"),
                Input(
                    name=f"monat_{nr}",
                    value=_stunden(wert),
                    inputmode="decimal",
                    placeholder="-",
                    aria_label=f"Stunden {month_name(nr)}",
                    cls="form-control form-control-sm wz-eingabe",
                ),
                Span(je_tag, cls="wz-zahl gedaempft"),
                Span(format_km(daten.km_business) if daten and daten.km_business else "-", cls="wz-zahl gruen"),
                cls="wz-zeile",
            )
        )

    return Div(
        Form(
            Div(
                Span(f"Arbeitszeit {monat.jahr}", cls="legende"),
                Div(
                    Span("Monat", cls="wz-monat"),
                    Span("Arbeitstage", cls="wz-zahl"),
                    Span("Stunden", cls="wz-eingabe"),
                    Span("je Arbeitstag", cls="wz-zahl"),
                    Span("km geschäftlich", cls="wz-zahl"),
                    cls="wz-zeile wz-kopf",
                ),
                *zeilen,
                Div(
                    Span("Summe", cls="wz-monat"),
                    Span(f"{erfasst} erfasst", cls="wz-zahl gedaempft"),
                    Span(_stunden(summe) or "-", cls="wz-eingabe wz-summe"),
                    Span(
                        f"Ø {summe / erfasst:.2f}".replace(".", ",") if erfasst else "-",
                        cls="wz-zahl",
                        title="Durchschnitt über die erfassten Monate",
                    ),
                    Span("", cls="wz-zahl"),
                    cls="wz-zeile wz-fuss",
                ),
                Div(
                    Span("Gespeichert.", cls="gruen meldung") if gespeichert else Span("", cls="gedaempft"),
                    Span(cls="fuellung"),
                    Button("Speichern", type="submit", cls="btn btn-primary"),
                    cls="dialog-fuss",
                ),
                cls="panel arbeitszeitpanel",
            ),
            hx_post=f"/arbeitszeit?jahr={monat.jahr}",
            hx_target="#arbeitszeit",
            hx_swap="outerHTML",
        ),
        id="arbeitszeit",
    )
