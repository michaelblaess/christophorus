"""Die Einstellungen: Fahrzeug, Pruefung und Export, Kategorien.

Die TUI kann hier mehr - Adressbuecher, Tastaturbelegung, Journalmodus der Datenbank. Im
Web fehlen sie bewusst: Adressen gehoeren zum Erfassen in der TUI, die Tastaturbelegung hat
im Browser keine Entsprechung, und der Journalmodus einer Arbeitskopie ist bedeutungslos.
"""

from __future__ import annotations

from typing import Any

from fasthtml.common import A, Button, Div, Form, Input, Label, Option, Select, Span

from christo.services.formatting import format_km, iso_to_de
from christo.web.context import Context

FT = Any

BUNDESLAENDER = (
    ("BW", "Baden-Württemberg"),
    ("BY", "Bayern"),
    ("BE", "Berlin"),
    ("BB", "Brandenburg"),
    ("HB", "Bremen"),
    ("HH", "Hamburg"),
    ("HE", "Hessen"),
    ("MV", "Mecklenburg-Vorpommern"),
    ("NI", "Niedersachsen"),
    ("NW", "Nordrhein-Westfalen"),
    ("RP", "Rheinland-Pfalz"),
    ("SL", "Saarland"),
    ("SN", "Sachsen"),
    ("ST", "Sachsen-Anhalt"),
    ("SH", "Schleswig-Holstein"),
    ("TH", "Thüringen"),
)

# Name, Beschriftung, Erklaerung, Standard. Die Standardwerte muessen zu denen passen, mit
# denen die Pruefung selbst liest - sonst zeigt die Maske "aus", wo in Wahrheit "an" gilt.
SCHALTER = (
    ("check_ghost_trips", "Geisterfahrten prüfen", "Meldet Tage mit geschäftlichen Kilometern ohne Beleg.", "0"),
    (
        "fuel_winter_tolerance",
        "Winterverbrauch tolerieren",
        "Höherer Verbrauch zwischen November und März gilt als normal.",
        "1",
    ),
    (
        "export_include_prev_december",
        "Dezember des Vorjahrs mit exportieren",
        "Zeigt der Steuerberatung, woher der km-Stand am Jahresanfang kommt.",
        "0",
    ),
)


def _feld(name: str, beschriftung: str, wert: str, fehler: str = "", **kwargs: Any) -> FT:
    return Div(
        Label(beschriftung, fr=f"e-{name}", cls="form-label"),
        Input(
            id=f"e-{name}",
            name=name,
            value=wert,
            cls="form-control is-invalid" if fehler else "form-control",
            **kwargs,
        ),
        Div(fehler, cls="invalid-feedback") if fehler else None,
        cls="mb-2",
    )


def _schalter(name: str, beschriftung: str, erklaerung: str, an: bool) -> FT:
    return Div(
        Label(
            Input(type="checkbox", name=name, value="1", checked=an, cls="form-check-input"),
            Span(beschriftung, cls="form-check-label"),
            cls="form-check",
        ),
        Div(erklaerung, cls="gedaempft"),
        cls="mb-2",
    )


def fahrzeugformular(ctx: Context, fehler: dict[str, str] | None = None, gespeichert: bool = False) -> FT:
    """Die Stammdaten des Fahrzeugs."""
    fehler = fehler or {}
    v = ctx.vehicle
    return Form(
        Div(
            Span("Fahrzeug", cls="legende"),
            Div(
                _feld("name", "Bezeichnung", v.name, fehler.get("name", "")),
                _feld("plate", "Kennzeichen", v.plate),
                _feld("contract_number", "Vertragsnummer", v.contract_number),
                cls="raster-drei",
            ),
            Div(
                _feld(
                    "start_date",
                    "Vertrag von",
                    iso_to_de(v.start_date),
                    fehler.get("start_date", ""),
                    placeholder="01.01.2026",
                    inputmode="numeric",
                ),
                _feld(
                    "end_date",
                    "Vertrag bis",
                    iso_to_de(v.end_date),
                    fehler.get("end_date", ""),
                    placeholder="31.12.2028",
                    inputmode="numeric",
                ),
                _feld(
                    "lease_months",
                    "Laufzeit (Monate)",
                    str(v.lease_months),
                    fehler.get("lease_months", ""),
                    inputmode="numeric",
                ),
                cls="raster-drei",
            ),
            Div(
                _feld(
                    "lease_km_per_month",
                    "km je Monat",
                    format_km(v.lease_km_per_month),
                    fehler.get("lease_km_per_month", ""),
                    inputmode="numeric",
                ),
                _feld(
                    "start_km",
                    "km bei Übernahme",
                    format_km(v.start_km),
                    fehler.get("start_km", ""),
                    inputmode="numeric",
                ),
                _feld("end_km", "km aktuell", format_km(v.end_km), fehler.get("end_km", ""), inputmode="numeric"),
                cls="raster-drei",
            ),
            Div(
                _feld(
                    "tank_capacity_l",
                    "Tankinhalt (Liter)",
                    f"{v.tank_capacity_l:.1f}".replace(".", ",") if v.tank_capacity_l else "",
                    fehler.get("tank_capacity_l", ""),
                    inputmode="decimal",
                ),
                _feld(
                    "consumption_l_100km",
                    "Verbrauch (l/100 km)",
                    f"{v.consumption_l_100km:.1f}".replace(".", ",") if v.consumption_l_100km else "",
                    fehler.get("consumption_l_100km", ""),
                    inputmode="decimal",
                ),
                Div(),
                cls="raster-drei",
            ),
            Div(
                Span("Gespeichert.", cls="gruen meldung") if gespeichert else Span("", cls="gedaempft"),
                Span(cls="fuellung"),
                Button("Fahrzeug speichern", type="submit", cls="btn btn-primary"),
                cls="dialog-fuss",
            ),
            cls="panel",
        ),
        hx_post="/einstellungen/fahrzeug",
        hx_target="#fahrzeugformular",
        hx_swap="outerHTML",
        id="fahrzeugformular",
    )


def pruefformular(ctx: Context, gespeichert: bool = False) -> FT:
    """Bundesland, Prüfoptionen, Heimatadresse."""
    db = ctx.db()
    land = db.get_setting("federal_state", "BB")
    return Form(
        Div(
            Span("Prüfung und Export", cls="legende"),
            Div(
                Label("Bundesland (Feiertage)", fr="e-federal_state", cls="form-label"),
                Select(
                    *[Option(name, value=code, selected=(code == land)) for code, name in BUNDESLAENDER],
                    id="e-federal_state",
                    name="federal_state",
                    cls="form-select",
                ),
                cls="mb-2",
            ),
            _feld("home_address", "Heimatadresse", db.get_setting("home_address", "")),
            *[
                _schalter(name, titel, text, db.get_setting(name, standard) == "1")
                for name, titel, text, standard in SCHALTER
            ],
            Div(
                Span("Gespeichert.", cls="gruen meldung") if gespeichert else Span("", cls="gedaempft"),
                Span(cls="fuellung"),
                Button("Prüfung speichern", type="submit", cls="btn btn-primary"),
                cls="dialog-fuss",
            ),
            cls="panel",
        ),
        hx_post="/einstellungen/pruefung",
        hx_target="#pruefformular",
        hx_swap="outerHTML",
        id="pruefformular",
    )


def kategorienformular(ctx: Context, meldung: str = "", fehler: str = "") -> FT:
    """Beschriftung, Farbe und Einstufung der Kategorien.

    Der interne Name bleibt stehen, er steckt in jeder gespeicherten Fahrt.
    """
    db = ctx.db()
    genutzt = {t.category for t in db.get_all_trips_ordered()}
    zeilen = []
    for kategorie in db.get_categories():
        kid = int(str(kategorie.get("id", 0)) or 0)
        name = str(kategorie.get("name", ""))
        in_gebrauch = name in genutzt
        zeilen.append(
            Div(
                Span(name, cls="kat-name gedaempft"),
                Input(
                    name=f"beschriftung_{kid}",
                    value=str(kategorie.get("display_name", "") or ""),
                    placeholder=name,
                    aria_label=f"Beschriftung für {name}",
                    cls="form-control form-control-sm",
                ),
                Input(
                    type="color",
                    name=f"farbe_{kid}",
                    value=str(kategorie.get("color", "") or "#888888"),
                    aria_label=f"Farbe für {name}",
                    cls="form-control form-control-color form-control-sm",
                ),
                Label(
                    Input(
                        type="checkbox",
                        name=f"geschaeftlich_{kid}",
                        value="1",
                        checked=bool(kategorie.get("counts_as_business")),
                        cls="form-check-input",
                    ),
                    Span("geschäftlich", cls="form-check-label"),
                    cls="form-check kat-schalter",
                ),
                Span(f"{sum(1 for t in db.get_all_trips_ordered() if t.category == name)} Fahrten", cls="gedaempft")
                if in_gebrauch
                else Button(
                    "Löschen",
                    type="submit",
                    name="loeschen",
                    value=str(kid),
                    cls="btn btn-sm btn-loeschen",
                ),
                cls="kat-zeile",
            )
        )
    return Form(
        Div(
            Span("Kategorien", cls="legende"),
            Div(
                "Der interne Name bleibt, wie er ist - er steht in jeder gespeicherten Fahrt. "
                "Löschen geht nur bei Kategorien, die keine Fahrt verwendet.",
                cls="gedaempft",
            ),
            *zeilen,
            Div(
                Span(meldung, cls="gruen meldung") if meldung else None,
                Span(fehler, cls="speicherfehler") if fehler else None,
                Span(cls="fuellung"),
                Button("Kategorien speichern", type="submit", cls="btn btn-primary"),
                cls="dialog-fuss",
            ),
            cls="panel",
        ),
        hx_post="/einstellungen/kategorien",
        hx_target="#kategorienformular",
        hx_swap="outerHTML",
        id="kategorienformular",
    )


def seite(ctx: Context) -> FT:
    """Alle drei Formulare untereinander."""
    return Div(
        Div(
            Span("Einstellungen", cls="legende"),
            Div(
                f"Arbeitskopie von {ctx.workspace.source}. ",
                "Änderungen wirken nur in der Kopie, das Original bleibt unberührt.",
                cls="gedaempft",
            ),
            Div(A("Zurück zur Liste", href="/", cls="btn"), cls="dialog-fuss"),
            cls="panel",
        ),
        fahrzeugformular(ctx),
        pruefformular(ctx),
        kategorienformular(ctx),
        cls="einstellungen",
    )
