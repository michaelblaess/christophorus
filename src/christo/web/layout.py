"""Das Seitengeruest: Kopf, Fahrzeugpanel, Reiter, Werkzeugleiste.

Jeder Reiter ist eine eigene Adresse, damit ein Link teilbar bleibt und der Zurueck-Knopf
des Browsers funktioniert. Die Reiterzeile weiss, welche Werkzeuge zu welcher Ansicht
gehoeren - die Ansichten selbst kuemmern sich nur um ihren Inhalt.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from fasthtml.common import H1, A, Button, Div, Form, Input, Link, Nav, Option, Script, Select, Span, Title
from fasthtml.svg import Circle, Svg
from fasthtml.svg import Path as SvgPath

from christo.services.formatting import format_km, iso_to_de
from christo.web.context import Context, Monat

FT = Any
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


@dataclass(frozen=True)
class Ansicht:
    """Ein Reiter der Oberflaeche.

    Attributes:
        schluessel: Kurzname, steht als `data-ansicht` in der Seite und steuert das Skript.
        titel: Beschriftung im Reiter.
        basis: Adresse ohne Abfrageteil.
        zeitraum: "monat", "jahr" oder "" - bestimmt die Pfeilnavigation und die Adresse.
    """

    schluessel: str
    titel: str
    basis: str
    zeitraum: str

    def pfad(self, monat: Monat) -> str:
        if self.zeitraum == "monat":
            return f"{self.basis}?jahr={monat.jahr}&monat={monat.monat}"
        if self.zeitraum == "jahr":
            return f"{self.basis}?jahr={monat.jahr}"
        return self.basis


ANSICHTEN = (
    Ansicht("liste", "Liste (Monat)", "/fahrten", "monat"),
    Ansicht("jahresliste", "Liste (Jahr)", "/fahrten/jahr", "jahr"),
    Ansicht("kalender", "Kalender", "/kalender", "monat"),
    Ansicht("jahr", "Jahr", "/jahr", "jahr"),
    Ansicht("blacklist", "Blacklist", "/blacklist", ""),
    Ansicht("belege", "Belege", "/belege", ""),
    Ansicht("arbeitszeit", "Arbeitszeit", "/arbeitszeit", "jahr"),
)
ANSICHT_NACH_SCHLUESSEL = {a.schluessel: a for a in ANSICHTEN}


def pfad(schluessel: str, monat: Monat) -> str:
    """Die Adresse einer Ansicht fuer den gegebenen Zeitraum."""
    return ANSICHT_NACH_SCHLUESSEL[schluessel].pfad(monat)


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


def _zahnrad() -> FT:
    return Svg(
        Circle(cx="12", cy="12", r="3"),
        SvgPath(
            d="M12 2.5l1.6 2.6 3-.6.4 3 2.7 1.4-1.7 2.5 1.7 2.5-2.7 1.4-.4 3-3-.6L12 21.5"
            "l-1.6-2.6-3 .6-.4-3-2.7-1.4L6 12.5 4.3 10 7 8.6l.4-3 3 .6z"
        ),
        viewBox="0 0 24 24",
        fill="none",
        stroke_width="1.8",
        stroke_linecap="round",
        stroke_linejoin="round",
        aria_hidden="true",
    )


def kopf(ctx: Context) -> FT:
    """Logo, Name der Arbeitskopie, Theme-Auswahl und Einstellungen."""
    return Div(
        Div(
            Div(
                Div(
                    H1("Christophorus"),
                    Span(f"{ctx.workspace.source.name}, Kopie vom {ctx.workspace.copied_at:%d.%m.%Y %H:%M}"),
                    cls="titel",
                ),
                cls="marke",
            ),
            Div(
                Span("Theme", cls="gedaempft"),
                Select(id="theme", cls="form-select form-select-sm", aria_label="Theme wählen"),
                A(_zahnrad(), href="/einstellungen", cls="werkzeug", title="Einstellungen", aria_label="Einstellungen"),
                cls="themenwahl",
            ),
            cls="kopfzeile",
        ),
        cls="kopf",
    )


def fahrzeugpanel(ctx: Context, ansicht: Ansicht, monat: Monat) -> FT:
    """Die Fahrzeugdaten und die Navigation durch den Zeitraum."""
    vehicle = ctx.vehicle
    leasing = ""
    if vehicle.start_date and vehicle.end_date:
        leasing = f"{iso_to_de(vehicle.start_date)} - {iso_to_de(vehicle.end_date)}"
    felder = [
        ("Fahrzeug", f"{vehicle.name} ({vehicle.plate})" if vehicle.plate else vehicle.name),
        ("Vertrag", vehicle.contract_number),
        ("Leasing", leasing),
        ("km-Stand", f"{format_km(vehicle.start_km)} - {format_km(vehicle.end_km)} km"),
    ]
    inhalt = [
        Div(Span(f"{bezeichnung} ", cls="gedaempft"), wert or "-")
        for bezeichnung, wert in felder
        if wert or bezeichnung == "Fahrzeug"
    ]
    if ansicht.zeitraum:
        schritt = 1 if ansicht.zeitraum == "monat" else 12
        beschriftung = monat.titel if ansicht.zeitraum == "monat" else str(monat.jahr)
        inhalt.append(
            Div(
                A("‹", href=ansicht.pfad(monat.verschoben(-schritt)), aria_label="Zurück"),
                Span(beschriftung),
                A("›", href=ansicht.pfad(monat.verschoben(schritt)), aria_label="Weiter"),
                cls="zeitraum",
            )
        )
    return Div(Span("Fahrzeug", cls="legende"), Div(*inhalt, cls="fahrzeug"), cls="panel")


def _suchfeld(platzhalter: str) -> FT:
    return Div(
        _lupe(),
        Input(
            type="search",
            id="suche",
            placeholder=platzhalter,
            aria_label=platzhalter,
            autocomplete="off",
        ),
        cls="suche",
    )


def _exportknopf(ansicht: Ansicht, monat: Monat) -> FT:
    """Formularknopf statt Link: der Browser laedt die Datei herunter, die Seite bleibt."""
    ziel = f"/export?jahr={monat.jahr}" + ("" if ansicht.zeitraum == "jahr" else f"&monat={monat.monat}")
    return Form(
        Select(
            Option("Excel", value="xlsx"),
            Option("JSON", value="json"),
            Option("Markdown", value="md"),
            name="format",
            cls="form-select form-select-sm",
            aria_label="Exportformat",
        ),
        Button("Export", type="submit", cls="btn"),
        action=ziel,
        method="get",
        cls="exportgruppe",
    )


def werkzeuge(ansicht: Ansicht, monat: Monat) -> FT:
    """Die Werkzeuge rechts neben den Reitern, passend zur Ansicht."""
    inhalt: list[FT] = []
    if ansicht.schluessel in ("liste", "jahresliste"):
        inhalt.append(_suchfeld("Fahrten durchsuchen"))
        inhalt.append(
            Button(
                "Neue Fahrt",
                cls="btn",
                hx_get=f"/fahrten/neu?jahr={monat.jahr}&monat={monat.monat}",
                hx_target="#dialog",
                hx_swap="outerHTML",
            )
        )
        inhalt.append(_exportknopf(ansicht, monat))
        inhalt.append(
            Button(
                "Prüfen",
                cls="btn btn-primary",
                hx_get=f"/uebersicht?jahr={monat.jahr}&monat={monat.monat}"
                + ("&art=jahr" if ansicht.zeitraum == "jahr" else ""),
                hx_target="#uebersicht",
                hx_swap="outerHTML",
            )
        )
    elif ansicht.schluessel == "kalender":
        inhalt.append(
            Button(
                "Neue Fahrt",
                cls="btn btn-primary",
                hx_get=f"/fahrten/neu?jahr={monat.jahr}&monat={monat.monat}",
                hx_target="#dialog",
                hx_swap="outerHTML",
            )
        )
    elif ansicht.schluessel == "blacklist":
        inhalt.append(_suchfeld("Einträge durchsuchen"))
        inhalt.append(
            Button(
                "Neuer Eintrag",
                cls="btn btn-primary",
                hx_get=f"/blacklist/neu?jahr={monat.jahr}&monat={monat.monat}",
                hx_target="#dialog",
                hx_swap="outerHTML",
            )
        )
    elif ansicht.schluessel == "belege":
        inhalt.append(_suchfeld("Belege durchsuchen"))
    return Div(*inhalt, cls="aktionen")


def reiterzeile(ansicht: Ansicht, monat: Monat) -> FT:
    """Die Reiter und die Werkzeuge der aktiven Ansicht."""
    reiter = [
        A(
            a.titel,
            href=a.pfad(monat),
            cls="reiter aktiv" if a.schluessel == ansicht.schluessel else "reiter",
            aria_current="page" if a.schluessel == ansicht.schluessel else None,
        )
        for a in ANSICHTEN
    ]
    return Div(Nav(*reiter, cls="reiter-liste"), werkzeuge(ansicht, monat), cls="reiterzeile")


def seite(ctx: Context, schluessel: str, monat: Monat, *inhalt: FT) -> tuple[FT, ...]:
    """Baut die vollstaendige Seite einer Ansicht.

    Args:
        ctx: Der Kontext der Arbeitskopie.
        schluessel: Kurzname der Ansicht, siehe `ANSICHTEN`.
        monat: Der angezeigte Zeitraum.
        inhalt: Die Bausteine der Ansicht, zwischen Reiterzeile und Dialog.
    """
    ansicht = ANSICHT_NACH_SCHLUESSEL[schluessel]
    zeitraum = monat.titel if ansicht.zeitraum == "monat" else str(monat.jahr)
    name = f"{ansicht.titel} {zeitraum}" if ansicht.zeitraum else ansicht.titel
    return (
        Title(f"{name} - Christophorus"),
        Div(
            kopf(ctx),
            fahrzeugpanel(ctx, ansicht, monat),
            reiterzeile(ansicht, monat),
            *inhalt,
            Div(id="dialog"),
            cls="app",
            data_ansicht=ansicht.schluessel,
            data_jahr=str(monat.jahr),
            data_monat=str(monat.monat),
        ),
        Script(src="/static/vendor/tabulator/tabulator.min.js"),
        Script(src="/static/christo-web.js"),
    )
