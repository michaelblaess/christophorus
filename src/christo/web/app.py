"""Die Web-Oberflaeche: Seitengeruest, Monatsliste, Bearbeiten-Dialog, Pruefung.

Alles laeuft gegen eine Arbeitskopie (siehe `workspace.py`). Fremde Dateien liegen unter
`static/vendor/`, es wird nichts aus dem Netz geladen.
"""

from __future__ import annotations

import json
import threading
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from fasthtml.common import (
    H1,
    A,
    Button,
    Details,
    Div,
    Form,
    Input,
    Label,
    Link,
    Mount,
    Nav,
    Option,
    RedirectResponse,
    Request,
    Response,
    Script,
    Select,
    Span,
    StaticFiles,
    Textarea,
    Title,
    fast_app,
)
from fasthtml.svg import Circle, Svg
from fasthtml.svg import Path as SvgPath

from christo.i18n import month_name
from christo.models.trip import Trip, set_business_categories, set_informational_categories
from christo.services.database import Database
from christo.services.formatting import format_km, iso_to_de
from christo.services.holiday_service import HolidayService
from christo.services.plausibility import (
    CAT_GHOST_BUSINESS_TRIP,
    SEVERITY_ERROR,
    SEVERITY_INFO,
    SEVERITY_WARNING,
    PlausibilityIssue,
    run_all_checks,
)
from christo.web.forms import FELDER, TripForm, form_from_trip, read_form, trip_from_form
from christo.web.workspace import Workspace

FT = Any
STATIC = Path(__file__).resolve().parent / "static"
STANDARD_THEME = "christophorus"

HEADERS = (
    Link(rel="icon", href="/static/christophorus.png"),
    Link(rel="stylesheet", href="/static/vendor/tabler/tabler.min.css"),
    Link(rel="stylesheet", href="/static/vendor/tabulator/tabulator_bootstrap5.min.css"),
    Link(rel="stylesheet", href="/static/vendor/web-themes/web-themes.css"),
    Link(rel="stylesheet", href="/static/vendor/web-themes/web-themes-tabulator.css"),
    Link(rel="stylesheet", href="/static/christo-web.css"),
    Script(src="/static/vendor/web-themes/web-themes.js"),
    Script(
        "(function(){var n='';try{n=localStorage.getItem('christo-theme')||''}catch(e){}"
        f"try{{WebThemes.apply(n||'{STANDARD_THEME}')}}catch(e){{WebThemes.apply('{STANDARD_THEME}')}}}})();"
    ),
    Script(src="/static/vendor/htmx/htmx.min.js"),
)

REITER = (
    ("Liste (Monat)", True),
    ("Liste (Jahr)", False),
    ("Kalender", False),
    ("Jahr", False),
    ("Blacklist", False),
    ("Belege", False),
    ("Arbeitszeit", False),
)


@dataclass
class Monat:
    """Der angezeigte Monat."""

    jahr: int
    monat: int

    @property
    def titel(self) -> str:
        return f"{month_name(self.monat)} {self.jahr}"

    def verschoben(self, schritte: int) -> Monat:
        gesamt = self.jahr * 12 + (self.monat - 1) + schritte
        return Monat(jahr=gesamt // 12, monat=gesamt % 12 + 1)


def _standardmonat(db: Database) -> Monat:
    """Zuletzt in der TUI angesehener Monat, sonst der erste mit Fahrten, sonst heute."""
    jahr = db.get_setting("last_viewed_year", "")
    monat = db.get_setting("last_viewed_month", "")
    if jahr.isdigit() and monat.isdigit():
        return Monat(jahr=int(jahr), monat=int(monat))
    erster = db.get_first_trip_date()
    if erster:
        return Monat(jahr=erster[0], monat=erster[1])
    heute = date.today()
    return Monat(jahr=heute.year, monat=heute.month)


def _issues(db: Database, jahr: int) -> list[PlausibilityIssue]:
    holidays_map = HolidayService(db.get_setting("federal_state", "BB")).get_holidays_in_year(jahr)
    skip: set[str] = set()
    if db.get_setting("check_ghost_trips", "0") != "1":
        skip.add(CAT_GHOST_BUSINESS_TRIP)
    return run_all_checks(db, holidays_by_date=holidays_map, skip_checks=skip).issues


def _lupe() -> FT:
    return Svg(
        Circle(cx="11", cy="11", r="7"),
        SvgPath(d="m20 20-3.5-3.5"),
        viewBox="0 0 24 24",
        fill="none",
        stroke_width="2.2",
        stroke_linecap="round",
        aria_hidden="true",
    )


def create_app(workspace: Workspace) -> Any:
    """Baut die Anwendung fuer eine Arbeitskopie.

    Die Datenbank bleibt waehrend der Laufzeit offen, die Kategorien werden wie in der TUI
    einmal aus der Datenbank in das Modell gesetzt.
    """
    # Starlette bedient synchrone Routen aus einem Threadpool, und eine SQLite-Verbindung
    # gehoert genau einem Thread. Deshalb eine Verbindung je Thread statt einer gemeinsamen.
    lokal = threading.local()

    def datenbank() -> Database:
        vorhanden: Database | None = getattr(lokal, "db", None)
        if vorhanden is None or not vorhanden.is_open:
            vorhanden = Database(workspace.path)
            vorhanden.open()
            lokal.db = vorhanden
        return vorhanden

    start_db = datenbank()
    set_business_categories(start_db.get_business_category_names())
    set_informational_categories(start_db.get_informational_category_names())
    vehicle = start_db.get_vehicle()

    app, rt = fast_app(default_hdrs=False, pico=False, hdrs=HEADERS, htmlkw={"lang": "de"})
    # Vor die Sammelroute von FastHTML, die sonst /static/... abfaengt
    app.router.routes.insert(0, Mount("/static", app=StaticFiles(directory=STATIC), name="static"))

    def kategorien() -> list[tuple[str, str]]:
        return datenbank().get_category_options()

    def kategoriename(code: str) -> str:
        return next((label for label, name in kategorien() if name == code), code)

    # --- Seitenteile ------------------------------------------------------------------

    def kopf() -> FT:
        return Div(
            Div(
                Div(
                    Div(
                        H1("Christophorus"),
                        Span(f"{workspace.source.name}, Kopie vom {workspace.copied_at:%d.%m.%Y %H:%M}"),
                        cls="titel",
                    ),
                    cls="marke",
                ),
                Div(
                    Span("Theme", cls="gedaempft"),
                    Select(id="theme", cls="form-select form-select-sm", aria_label="Theme wählen"),
                    cls="themenwahl",
                ),
                cls="kopfzeile",
            ),
            cls="kopf",
        )

    def fahrzeugpanel(monat: Monat) -> FT:
        leasing = ""
        if vehicle.start_date and vehicle.end_date:
            leasing = f"{iso_to_de(vehicle.start_date)} - {iso_to_de(vehicle.end_date)}"
        felder = [
            ("Fahrzeug", f"{vehicle.name} ({vehicle.plate})" if vehicle.plate else vehicle.name),
            ("Vertrag", vehicle.contract_number),
            ("Leasing", leasing),
            ("km-Stand", f"{format_km(vehicle.start_km)} - {format_km(vehicle.end_km)} km"),
        ]
        return Div(
            Span("Fahrzeug", cls="legende"),
            Div(
                *[
                    Div(Span(f"{bezeichnung} ", cls="gedaempft"), wert or "-")
                    for bezeichnung, wert in felder
                    if wert or bezeichnung == "Fahrzeug"
                ],
                Div(
                    A("‹", href=_pfad(monat.verschoben(-1)), aria_label="Voriger Monat"),
                    Span(monat.titel),
                    A("›", href=_pfad(monat.verschoben(1)), aria_label="Nächster Monat"),
                    cls="zeitraum",
                ),
                cls="fahrzeug",
            ),
            cls="panel",
        )

    def reiterzeile(monat: Monat) -> FT:
        reiter = [
            A(name, href="#", cls="reiter aktiv") if aktiv else Span(name, cls="reiter gesperrt", title="folgt später")
            for name, aktiv in REITER
        ]
        return Div(
            Nav(*reiter, cls="reiter-liste"),
            Div(
                Div(
                    _lupe(),
                    Input(
                        type="search",
                        id="suche",
                        placeholder="Fahrten durchsuchen",
                        aria_label="Fahrten durchsuchen",
                        autocomplete="off",
                    ),
                    cls="suche",
                ),
                Button(
                    "Prüfen",
                    cls="btn btn-primary",
                    hx_get=f"/uebersicht?jahr={monat.jahr}&monat={monat.monat}",
                    hx_target="#uebersicht",
                    hx_swap="outerHTML",
                ),
                cls="aktionen",
            ),
            cls="reiterzeile",
        )

    def uebersicht(monat: Monat) -> FT:
        daten = datenbank().get_month_data(monat.jahr, monat.monat)
        befunde = [i for i in _issues(datenbank(), monat.jahr) if i.month_key in (None, (monat.jahr, monat.monat))]
        zeilen = [
            Div(
                Span(_symbol(i.severity), cls=f"schwere-{i.severity}"),
                Span(iso_to_de(i.trip_date) if i.trip_date else "", cls="zeit"),
                Span(i.message),
            )
            for i in befunde[:12]
        ]
        if not zeilen:
            zeilen = [Div("Keine Auffälligkeiten in diesem Monat.", cls="gedaempft")]
        zaehler = {
            s: sum(1 for i in befunde if i.severity == s) for s in (SEVERITY_ERROR, SEVERITY_WARNING, SEVERITY_INFO)
        }
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
                    f"{zaehler[SEVERITY_INFO]} Hinweise in diesem Monat",
                    cls="gedaempft",
                ),
                *zeilen,
                cls="panel protokoll",
            ),
            id="uebersicht",
        )

    def dialog(trip: Trip, form: TripForm) -> FT:
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
                        # Immer das gespeicherte Datum, nicht die (womoeglich falsche) Eingabe
                        Span(f"Fahrt vom {iso_to_de(trip.date)}", cls="legende"),
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
                                    for label, name in kategorien()
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
                            Span("Tanken und Hin- und Rückfahrt", cls="zusatz-titel"),
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
                            Button("Speichern", type="submit", cls="btn btn-primary"),
                            Button("Abbrechen", type="button", cls="btn", onclick="schliesseDialog()"),
                            cls="dialog-fuss",
                        ),
                        cls="panel dialog-inhalt",
                    ),
                    hx_post=f"/fahrten/{trip.id}",
                    hx_target="#dialog",
                    hx_swap="outerHTML",
                ),
                cls="dialog-rahmen",
            ),
            id="dialog",
            cls="dialog-hintergrund",
        )

    def _pfad(monat: Monat) -> str:
        return f"/fahrten?jahr={monat.jahr}&monat={monat.monat}"

    def seite(monat: Monat) -> tuple[FT, ...]:
        return (
            Title(f"{monat.titel} - Christophorus"),
            Div(
                kopf(),
                fahrzeugpanel(monat),
                reiterzeile(monat),
                Div(Div(id="tabelle"), cls="panel tabellenpanel"),
                uebersicht(monat),
                Div(id="dialog"),
                cls="app",
                data_jahr=str(monat.jahr),
                data_monat=str(monat.monat),
            ),
            Script(src="/static/vendor/tabulator/tabulator.min.js"),
            Script(src="/static/christo-web.js"),
        )

    # --- Routen -----------------------------------------------------------------------

    @rt("/")
    def index() -> RedirectResponse:
        return RedirectResponse(_pfad(_standardmonat(datenbank())), status_code=303)

    @rt("/fahrten")
    def fahrten(jahr: int = 0, monat: int = 0) -> tuple[FT, ...]:
        gewaehlt = Monat(jahr=jahr, monat=monat) if 1 <= monat <= 12 and jahr > 0 else _standardmonat(datenbank())
        return seite(gewaehlt)

    @rt("/api/fahrten")
    def api_fahrten(jahr: int, monat: int) -> Response:
        warnungen: dict[int, str] = {}
        for issue in _issues(datenbank(), jahr):
            if issue.trip_id:
                warnungen.setdefault(issue.trip_id, f"{_symbol(issue.severity)} {issue.message}")
        zeilen = [
            {
                "id": t.id,
                "datum": iso_to_de(t.date),
                "tag": _wochentag(t.date),
                "zeit": f"{t.time_from} - {t.time_to}".strip(" -"),
                "ziel": t.destination,
                "zweck": t.purpose or kategoriename(t.category),
                "kmAnfang": format_km(t.km_start) if not t.is_informational else "",
                "kmEnde": format_km(t.km_end) if not t.is_informational else "",
                "geschaeftlich": format_km(t.km_business) if t.km_business else "",
                "privat": format_km(t.km_private) if t.km_private else "",
                "warnung": warnungen.get(t.id, ""),
                "privatfahrt": not t.is_business_km,
            }
            for t in datenbank().get_trips_for_month(jahr, monat)
        ]
        return Response(json.dumps(zeilen, ensure_ascii=False), media_type="application/json; charset=utf-8")

    @rt("/uebersicht")
    def uebersicht_route(jahr: int, monat: int) -> FT:
        return uebersicht(Monat(jahr=jahr, monat=monat))

    @rt("/fahrten/{trip_id}/bearbeiten")
    def bearbeiten(trip_id: int) -> FT:
        trip = datenbank().get_trip_by_id(trip_id)
        if trip is None:
            return Div(id="dialog")
        return dialog(trip, form_from_trip(trip))

    @rt("/fahrten/{trip_id}", methods=["POST"])
    async def speichern(trip_id: int, request: Request) -> FT | Response:
        trip = datenbank().get_trip_by_id(trip_id)
        if trip is None:
            return Div(id="dialog")
        rohdaten = await request.form()
        daten = {name: str(rohdaten.get(name, "")) for name in FELDER}
        form = read_form(daten, {name for _, name in kategorien()})
        if form.valid:
            try:
                datenbank().update_trip(trip_id, trip_from_form(form, trip_id))
            except (ValueError, RuntimeError) as fehler:
                form.errors["speichern"] = str(fehler)
            else:
                # Leerer Dialog zurueck, die Seite laedt Tabelle und Uebersicht neu
                return Response(
                    '<div id="dialog"></div>',
                    media_type="text/html; charset=utf-8",
                    headers={"HX-Trigger": "fahrtGespeichert"},
                )
        return dialog(trip, form)

    return app


def _symbol(severity: str) -> str:
    return {SEVERITY_ERROR: "▲", SEVERITY_WARNING: "▲", SEVERITY_INFO: "●"}.get(severity, "")


def _wochentag(iso: str) -> str:
    try:
        return ("Mo", "Di", "Mi", "Do", "Fr", "Sa", "So")[date.fromisoformat(iso).weekday()]
    except ValueError:
        return ""
