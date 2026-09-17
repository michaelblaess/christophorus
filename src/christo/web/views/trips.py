"""Die Fahrtenliste: Tabellendaten, Summe, Pruefprotokoll, Dialoge zum Bearbeiten.

Die Liste selbst baut Tabulator im Browser aus `/api/fahrten`. Hier entstehen die Zeilen
und alles, was serverseitig gerendert wird.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from fasthtml.common import Button, Details, Div, Form, Input, Label, Option, Select, Span, Summary, Textarea

from christo.models.trip import Trip
from christo.services.formatting import format_km, iso_to_de
from christo.services.plausibility import SEVERITY_ERROR, SEVERITY_INFO, SEVERITY_WARNING
from christo.web.context import Context, Monat
from christo.web.forms import TripForm

FT = Any
WOCHENTAGE = ("Mo", "Di", "Mi", "Do", "Fr", "Sa", "So")


def symbol(severity: str) -> str:
    """Das Zeichen vor einem Befund. Warnungen tragen ein Dreieck, nicht nur Farbe."""
    return {SEVERITY_ERROR: "▲", SEVERITY_WARNING: "▲", SEVERITY_INFO: "●"}.get(severity, "")


def wochentag(iso: str) -> str:
    try:
        return WOCHENTAGE[date.fromisoformat(iso).weekday()]
    except ValueError:
        return ""


def tabellenpanel() -> FT:
    """Der Platz, in den Tabulator die Liste zeichnet."""
    return Div(Div(id="tabelle"), cls="panel tabellenpanel")


def zeilen(ctx: Context, jahr: int, monat: int | None) -> list[dict[str, object]]:
    """Die Fahrten als Tabellenzeilen. `monat=None` liefert das ganze Jahr."""
    warnungen: dict[int, str] = {}
    for issue in ctx.issues(jahr):
        if issue.trip_id:
            warnungen.setdefault(issue.trip_id, f"{symbol(issue.severity)} {issue.message}")
    db = ctx.db()
    fahrten = db.get_trips_for_year(jahr) if monat is None else db.get_trips_for_month(jahr, monat)
    from christo.i18n import month_name

    return [
        {
            "id": t.id,
            "datum": iso_to_de(t.date),
            "monat": f"{month_name(int(t.date[5:7]))} {t.date[:4]}" if len(t.date) >= 7 else "",
            "tag": wochentag(t.date),
            "zeit": f"{t.time_from} - {t.time_to}".strip(" -"),
            "ziel": t.destination,
            "zweck": t.purpose or ctx.kategoriename(t.category),
            "kmAnfang": format_km(t.km_start) if not t.is_informational else "",
            "kmEnde": format_km(t.km_end) if not t.is_informational else "",
            "geschaeftlich": format_km(t.km_business) if t.km_business else "",
            "privat": format_km(t.km_private) if t.km_private else "",
            "warnung": warnungen.get(t.id, ""),
            "privatfahrt": not t.is_business_km,
        }
        for t in fahrten
    ]


def uebersicht(ctx: Context, monat: Monat, jahresmodus: bool = False) -> FT:
    """Summenzeile und Pruefprotokoll fuer Monat oder Jahr."""
    db = ctx.db()
    daten = db.get_year_data(monat.jahr) if jahresmodus else db.get_month_data(monat.jahr, monat.monat)
    alle = ctx.issues(monat.jahr)
    befunde = alle if jahresmodus else [i for i in alle if i.month_key in (None, (monat.jahr, monat.monat))]
    protokoll = [
        Div(
            Span(symbol(i.severity), cls=f"schwere-{i.severity}"),
            Span(iso_to_de(i.trip_date) if i.trip_date else "", cls="zeit"),
            Span(i.message),
        )
        for i in befunde[:12]
    ]
    if not protokoll:
        protokoll = [Div("Keine Auffälligkeiten in diesem Zeitraum.", cls="gedaempft")]
    zaehler = {s: sum(1 for i in befunde if i.severity == s) for s in (SEVERITY_ERROR, SEVERITY_WARNING, SEVERITY_INFO)}
    bezeichnung = str(monat.jahr) if jahresmodus else "diesem Monat"
    return Div(
        Div(
            Span(f"km gesamt: {format_km(daten.km_total)}"),
            Span("|", cls="trenner"),
            Span(f"geschäftlich: {format_km(daten.km_business)} ({daten.business_percentage:.0f} %)", cls="gruen"),
            Span("|", cls="trenner"),
            Span(f"privat: {format_km(daten.km_private)}"),
            Span("|", cls="trenner"),
            Span(f"{len(daten.trips)} Fahrten"),
            cls="panel summe",
        ),
        Div(
            Span("Plausibilitätsprüfung", cls="legende"),
            Div(
                f"{zaehler[SEVERITY_ERROR]} Fehler, {zaehler[SEVERITY_WARNING]} Warnungen, "
                f"{zaehler[SEVERITY_INFO]} Hinweise in {bezeichnung}"
                + (f" (die ersten {len(protokoll)} von {len(befunde)})" if len(befunde) > 12 else ""),
                cls="gedaempft",
            ),
            *protokoll,
            cls="panel protokoll",
        ),
        id="uebersicht",
    )


def dialog(ctx: Context, form: TripForm, trip: Trip | None, monat: Monat) -> FT:
    """Der Dialog zum Anlegen oder Bearbeiten einer Fahrt.

    Args:
        ctx: Der Kontext.
        form: Der Formularzustand, samt Fehlern.
        trip: Die gespeicherte Fahrt, oder None fuer eine neue.
        monat: Der Zeitraum der Seite, fuer die Adresse beim Anlegen.
    """
    ziel = f"/fahrten/neu?jahr={monat.jahr}&monat={monat.monat}" if trip is None else f"/fahrten/{trip.id}"
    # Immer das gespeicherte Datum, nicht die (womoeglich falsche) Eingabe
    titel = "Neue Fahrt" if trip is None else f"Fahrt vom {iso_to_de(trip.date)}"

    def feld(name: str, beschriftung: str, **kwargs: Any) -> FT:
        fehler = form.errors.get(name, "")
        return Div(
            Label(beschriftung, fr=f"f-{name}", cls="form-label"),
            Input(
                id=f"f-{name}",
                name=name,
                value=form.values[name],
                cls="form-control is-invalid" if fehler else "form-control",
                **kwargs,
            ),
            Div(fehler, cls="invalid-feedback") if fehler else None,
            cls="mb-2",
        )

    kategorie_fehler = form.errors.get("kategorie", "")
    return Div(
        Div(
            Form(
                Div(
                    Span(titel, cls="legende"),
                    Div(
                        feld("datum", "Datum", inputmode="numeric"),
                        feld("abfahrt", "Abfahrt", placeholder="07:15"),
                        feld("ankunft", "Ankunft", placeholder="10:40"),
                        cls="raster-drei",
                    ),
                    Div(
                        Label("Ziel", fr="f-ziel", cls="form-label"),
                        Textarea(form.values["ziel"], id="f-ziel", name="ziel", rows="2", cls="form-control"),
                        cls="mb-2",
                    ),
                    feld("zweck", "Reisezweck"),
                    Div(
                        Label("Kategorie", fr="f-kategorie", cls="form-label"),
                        Select(
                            *[
                                Option(label, value=name, selected=(name == form.values["kategorie"]))
                                for label, name in ctx.kategorien()
                            ],
                            id="f-kategorie",
                            name="kategorie",
                            cls="form-select is-invalid" if kategorie_fehler else "form-select",
                        ),
                        Div(kategorie_fehler, cls="invalid-feedback") if kategorie_fehler else None,
                        cls="mb-2",
                    ),
                    Div(
                        feld("km_anfang", "km Anfang", inputmode="numeric"),
                        feld("km_geschaeftlich", "km geschäftlich", inputmode="numeric"),
                        feld("km_privat", "km privat", inputmode="numeric"),
                        cls="raster-drei",
                    ),
                    Details(
                        # Ohne <summary> zeigt der Browser sein eigenes Wort "Details"
                        Summary("Tanken und Hin- und Rückfahrt", cls="zusatz-titel"),
                        Div(
                            feld("tankliter", "Liter", inputmode="decimal"),
                            Label(
                                Input(
                                    type="checkbox",
                                    name="volltank",
                                    value="1",
                                    checked=bool(form.values["volltank"]),
                                    cls="form-check-input",
                                ),
                                Span("Vollgetankt", cls="form-check-label"),
                                cls="form-check",
                            ),
                            Label(
                                Input(
                                    type="checkbox",
                                    name="hin_und_zurueck",
                                    value="1",
                                    checked=bool(form.values["hin_und_zurueck"]),
                                    cls="form-check-input",
                                ),
                                Span("Hin- und Rückfahrt", cls="form-check-label"),
                                cls="form-check",
                            ),
                            cls="raster-drei",
                        ),
                        cls="zusatz",
                    ),
                    Div(form.errors.get("speichern", ""), cls="speicherfehler")
                    if form.errors.get("speichern")
                    else None,
                    Div(
                        Button(
                            "Löschen",
                            type="button",
                            cls="btn btn-loeschen",
                            hx_get=f"/fahrten/{trip.id}/loeschen",
                            hx_target="#dialog",
                            hx_swap="outerHTML",
                        )
                        if trip is not None
                        else None,
                        Span(cls="fuellung"),
                        Button("Speichern", type="submit", cls="btn btn-primary"),
                        Button("Abbrechen", type="button", cls="btn", onclick="schliesseDialog()"),
                        cls="dialog-fuss",
                    ),
                    cls="panel dialog-inhalt",
                ),
                hx_post=ziel,
                hx_target="#dialog",
                hx_swap="outerHTML",
            ),
            cls="dialog-rahmen",
        ),
        id="dialog",
        cls="dialog-hintergrund",
    )


def loeschdialog(ctx: Context, trip: Trip) -> FT:
    """Rueckfrage vor dem Loeschen, mit Hinweis auf verknuepfte Belege."""
    belege = ctx.db().get_documents(trip_id=trip.id)
    zweck = trip.purpose.strip() or ctx.kategoriename(trip.category)
    ziel = trip.destination.split("\n")[0].strip()
    hinweis = ""
    if belege:
        hinweis = (
            f"Dazu {'gehört ein Beleg' if len(belege) == 1 else f'gehören {len(belege)} Belege'}. "
            "Die Verknüpfung wird mit gelöscht, die Datei selbst bleibt liegen."
        )
    return Div(
        Div(
            Div(
                Span("Fahrt löschen", cls="legende"),
                Div(f"{iso_to_de(trip.date)} - {zweck}"),
                Div(ziel, cls="gedaempft") if ziel else None,
                Div(hinweis, cls="schwere-warning") if hinweis else None,
                Div("Das lässt sich nicht rückgängig machen.", cls="gedaempft"),
                Div(
                    Button(
                        "Endgültig löschen",
                        cls="btn btn-loeschen",
                        hx_post=f"/fahrten/{trip.id}/loeschen",
                        hx_target="#dialog",
                        hx_swap="outerHTML",
                    ),
                    Button("Abbrechen", type="button", cls="btn", onclick="schliesseDialog()"),
                    cls="dialog-fuss",
                ),
                cls="panel dialog-inhalt",
            ),
            cls="dialog-rahmen dialog-schmal",
        ),
        id="dialog",
        cls="dialog-hintergrund",
    )
