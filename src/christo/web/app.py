"""Die Routen der Weboberflaeche.

Jeder Reiter ist eine eigene Adresse, die Dialoge kommen als HTMX-Fragmente zurueck. Die
Inhalte selbst stehen in `views/`, das Geruest in `layout.py`, der Zustand in `context.py`.
Alles laeuft gegen eine Arbeitskopie (siehe `workspace.py`), es wird nichts aus dem Netz
geladen.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

from fasthtml.common import (
    Div,
    FileResponse,
    Mount,
    RedirectResponse,
    Request,
    Response,
    Script,
    StaticFiles,
    Title,
    fast_app,
)

from christo.services.formatting import format_km, iso_to_de
from christo.web import export as export_dienst
from christo.web.context import Context, Monat
from christo.web.forms import (
    FELDER,
    TripForm,
    form_from_trip,
    read_blacklist_form,
    read_form,
    read_vehicle_form,
    read_worktimes,
    trip_from_form,
)
from christo.web.layout import HEADERS, kopf, pfad, seite
from christo.web.views import blacklist as blacklist_view
from christo.web.views import calendar_view, documents, settings, worktimes
from christo.web.views import trips as trips_view
from christo.web.views import year as year_view
from christo.web.workspace import Workspace

FT = Any
STATIC = Path(__file__).resolve().parent / "static"
# Der Browser laedt nach jeder Aenderung Tabelle und Uebersicht neu
GEAENDERT = {"HX-Trigger": "datenGeaendert"}
LEERER_DIALOG = '<div id="dialog"></div>'


def _antwort(html: str, headers: dict[str, str] | None = None) -> Response:
    return Response(html, media_type="text/html; charset=utf-8", headers=headers)


def _json(daten: list[dict[str, object]]) -> Response:
    return Response(json.dumps(daten, ensure_ascii=False), media_type="application/json; charset=utf-8")


def create_app(workspace: Workspace) -> Any:
    """Baut die Anwendung fuer eine Arbeitskopie."""
    ctx = Context(workspace)

    app, rt = fast_app(default_hdrs=False, pico=False, hdrs=HEADERS, htmlkw={"lang": "de"})
    # Vor die Sammelroute von FastHTML, die sonst /static/... abfaengt
    app.router.routes.insert(0, Mount("/static", app=StaticFiles(directory=STATIC), name="static"))

    def zeitraum(jahr: int, monat: int) -> Monat:
        """Der angefragte Zeitraum, mit dem Standardmonat als Rueckfall."""
        if jahr > 0 and 1 <= monat <= 12:
            return Monat(jahr=jahr, monat=monat)
        standard = ctx.standardmonat()
        return Monat(jahr=jahr, monat=standard.monat) if jahr > 0 else standard

    def kategorienamen() -> set[str]:
        return {name for _, name in ctx.kategorien()}

    # --- Seiten -----------------------------------------------------------------------

    @rt("/")
    def index() -> RedirectResponse:
        return RedirectResponse(pfad("liste", ctx.standardmonat()), status_code=303)

    @rt("/fahrten")
    def fahrten(jahr: int = 0, monat: int = 0) -> tuple[FT, ...]:
        gewaehlt = zeitraum(jahr, monat)
        return seite(ctx, "liste", gewaehlt, trips_view.tabellenpanel(), trips_view.uebersicht(ctx, gewaehlt))

    @rt("/fahrten/jahr")
    def fahrten_jahr(jahr: int = 0) -> tuple[FT, ...]:
        gewaehlt = zeitraum(jahr, 0)
        return seite(
            ctx,
            "jahresliste",
            gewaehlt,
            trips_view.tabellenpanel(),
            trips_view.uebersicht(ctx, gewaehlt, jahresmodus=True),
        )

    @rt("/kalender")
    def kalender(jahr: int = 0, monat: int = 0) -> tuple[FT, ...]:
        gewaehlt = zeitraum(jahr, monat)
        return seite(
            ctx,
            "kalender",
            gewaehlt,
            calendar_view.ansicht(ctx, gewaehlt),
            trips_view.uebersicht(ctx, gewaehlt),
        )

    @rt("/jahr")
    def jahr_seite(jahr: int = 0) -> tuple[FT, ...]:
        gewaehlt = zeitraum(jahr, 0)
        return seite(ctx, "jahr", gewaehlt, year_view.ansicht(ctx, gewaehlt))

    @rt("/blacklist")
    def blacklist_seite(jahr: int = 0, monat: int = 0) -> tuple[FT, ...]:
        gewaehlt = zeitraum(jahr, monat)
        return seite(ctx, "blacklist", gewaehlt, blacklist_view.tabellenpanel(), blacklist_view.uebersicht(ctx))

    @rt("/belege")
    def belege_seite(jahr: int = 0, monat: int = 0) -> tuple[FT, ...]:
        gewaehlt = zeitraum(jahr, monat)
        return seite(ctx, "belege", gewaehlt, documents.tabellenpanel(), documents.uebersicht(ctx))

    @rt("/arbeitszeit", methods=["GET"])
    def arbeitszeit_seite(jahr: int = 0) -> tuple[FT, ...]:
        gewaehlt = zeitraum(jahr, 0)
        return seite(ctx, "arbeitszeit", gewaehlt, worktimes.ansicht(ctx, gewaehlt))

    @rt("/arbeitszeit", methods=["POST"])
    async def arbeitszeit_speichern(request: Request, jahr: int = 0) -> FT:
        gewaehlt = zeitraum(jahr, 0)
        rohdaten = await request.form()
        db = ctx.db()
        for monat, stunden in read_worktimes({k: str(v) for k, v in rohdaten.items()}).items():
            if stunden > 0:
                db.save_worktime(gewaehlt.jahr, monat, stunden)
            else:
                db.delete_worktime(gewaehlt.jahr, monat)
        return worktimes.ansicht(ctx, gewaehlt, gespeichert=True)

    # --- Tabellendaten ----------------------------------------------------------------

    @rt("/api/fahrten")
    def api_fahrten(jahr: int, monat: int = 0) -> Response:
        return _json(trips_view.zeilen(ctx, jahr, monat if 1 <= monat <= 12 else None))

    @rt("/api/blacklist")
    def api_blacklist() -> Response:
        return _json(blacklist_view.zeilen(ctx))

    @rt("/api/belege")
    def api_belege() -> Response:
        return _json(documents.zeilen(ctx))

    @rt("/uebersicht")
    def uebersicht_route(jahr: int, monat: int = 0, art: str = "") -> FT:
        jahresmodus = art == "jahr" or not 1 <= monat <= 12
        return trips_view.uebersicht(ctx, Monat(jahr=jahr, monat=monat or 1), jahresmodus=jahresmodus)

    # --- Fahrt anlegen, bearbeiten, loeschen ------------------------------------------

    @rt("/fahrten/neu", methods=["GET"])
    def neue_fahrt(jahr: int = 0, monat: int = 0, datum: str = "") -> FT:
        gewaehlt = zeitraum(jahr, monat)
        if datum:
            try:
                tag = date.fromisoformat(datum)
                gewaehlt = Monat(jahr=tag.year, monat=tag.month)
            except ValueError:
                datum = ""
        return trips_view.dialog(ctx, _leeres_formular(gewaehlt, datum), None, gewaehlt)

    @rt("/fahrten/neu", methods=["POST"])
    async def fahrt_anlegen(request: Request, jahr: int = 0, monat: int = 0) -> FT | Response:
        gewaehlt = zeitraum(jahr, monat)
        rohdaten = await request.form()
        form = read_form({name: str(rohdaten.get(name, "")) for name in FELDER}, kategorienamen())
        if form.valid:
            try:
                ctx.db().add_trip(trip_from_form(form, trip_id=0))
            except (ValueError, RuntimeError) as fehler:
                form.errors["speichern"] = str(fehler)
            else:
                return _antwort(LEERER_DIALOG, GEAENDERT)
        return trips_view.dialog(ctx, form, None, gewaehlt)

    @rt("/fahrten/{trip_id:int}/bearbeiten")
    def bearbeiten(trip_id: int) -> FT:
        trip = ctx.db().get_trip_by_id(trip_id)
        if trip is None:
            return Div(id="dialog")
        return trips_view.dialog(ctx, form_from_trip(trip), trip, _monat_der_fahrt(trip.date))

    @rt("/fahrten/{trip_id:int}", methods=["POST"])
    async def speichern(trip_id: int, request: Request) -> FT | Response:
        trip = ctx.db().get_trip_by_id(trip_id)
        if trip is None:
            return Div(id="dialog")
        rohdaten = await request.form()
        form = read_form({name: str(rohdaten.get(name, "")) for name in FELDER}, kategorienamen())
        if form.valid:
            try:
                ctx.db().update_trip(trip_id, trip_from_form(form, trip_id))
            except (ValueError, RuntimeError) as fehler:
                form.errors["speichern"] = str(fehler)
            else:
                return _antwort(LEERER_DIALOG, GEAENDERT)
        return trips_view.dialog(ctx, form, trip, _monat_der_fahrt(trip.date))

    @rt("/fahrten/{trip_id:int}/loeschen", methods=["GET"])
    def loeschen_fragen(trip_id: int) -> FT:
        trip = ctx.db().get_trip_by_id(trip_id)
        if trip is None:
            return Div(id="dialog")
        return trips_view.loeschdialog(ctx, trip)

    @rt("/fahrten/{trip_id:int}/loeschen", methods=["POST"])
    def loeschen(trip_id: int) -> Response:
        if ctx.db().get_trip_by_id(trip_id) is not None:
            ctx.db().delete_trip(trip_id)
        return _antwort(LEERER_DIALOG, GEAENDERT)

    # --- Sperrtage --------------------------------------------------------------------

    @rt("/blacklist/neu", methods=["GET"])
    def neuer_sperrtag(jahr: int = 0, monat: int = 0) -> FT:
        gewaehlt = zeitraum(jahr, monat)
        return blacklist_view.dialog(0, f"01.{gewaehlt.monat:02d}.{gewaehlt.jahr}", "")

    @rt("/blacklist/neu", methods=["POST"])
    async def sperrtag_anlegen(request: Request) -> FT | Response:
        rohdaten = await request.form()
        form = read_blacklist_form({k: str(v) for k, v in rohdaten.items()})
        if form.valid:
            ctx.db().add_blacklist_entry(form.datum_iso, form.grund)
            return _antwort(LEERER_DIALOG, GEAENDERT)
        return blacklist_view.dialog(0, form.datum, form.grund, form.errors)

    @rt("/blacklist/{entry_id:int}/bearbeiten")
    def sperrtag_bearbeiten(entry_id: int) -> FT:
        eintrag = _sperrtag(entry_id)
        if eintrag is None:
            return Div(id="dialog")
        return blacklist_view.dialog(entry_id, iso_to_de(str(eintrag.get("date", ""))), str(eintrag.get("reason", "")))

    @rt("/blacklist/{entry_id:int}", methods=["POST"])
    async def sperrtag_speichern(entry_id: int, request: Request) -> FT | Response:
        if _sperrtag(entry_id) is None:
            return Div(id="dialog")
        rohdaten = await request.form()
        form = read_blacklist_form({k: str(v) for k, v in rohdaten.items()})
        if form.valid:
            ctx.db().update_blacklist_entry(entry_id, form.datum_iso, form.grund)
            return _antwort(LEERER_DIALOG, GEAENDERT)
        return blacklist_view.dialog(entry_id, form.datum, form.grund, form.errors)

    @rt("/blacklist/{entry_id:int}/loeschen", methods=["POST"])
    def sperrtag_loeschen(entry_id: int) -> Response:
        if _sperrtag(entry_id) is not None:
            ctx.db().delete_blacklist_entry(entry_id)
        return _antwort(LEERER_DIALOG, GEAENDERT)

    # --- Belege -----------------------------------------------------------------------

    @rt("/belege/{doc_id:int}/datei")
    def beleg_datei(doc_id: int) -> Response:
        datei = documents.datei_pfad(ctx, doc_id)
        if datei is None:
            return Response("Diesen Beleg gibt es nicht mehr.", status_code=404, media_type="text/plain")
        return FileResponse(datei, filename=datei.name)

    # --- Export -----------------------------------------------------------------------

    @rt("/export")
    def export_route(jahr: int = 0, monat: int = 0, format: str = "xlsx") -> Response:
        gewaehlt = zeitraum(jahr, monat)
        auftrag = export_dienst.baue(ctx, gewaehlt, jahresexport=not 1 <= monat <= 12)
        if auftrag is None:
            return Response(
                "In diesem Zeitraum gibt es keine Fahrten zum Exportieren.",
                status_code=404,
                media_type="text/plain; charset=utf-8",
            )
        ausgabe = export_dienst.schreibe(*auftrag, export_dienst.format_aus_wahl(format))
        return Response(ausgabe.inhalt, media_type=ausgabe.medientyp, headers=ausgabe.headers)

    # --- Einstellungen ----------------------------------------------------------------

    @rt("/einstellungen")
    def einstellungen() -> tuple[FT, ...]:
        return (
            Title("Einstellungen - Christophorus"),
            Div(kopf(ctx), settings.seite(ctx), cls="app", data_ansicht="einstellungen"),
            Script(src="/static/vendor/tabulator/tabulator.min.js"),
            Script(src="/static/christo-web.js"),
        )

    @rt("/einstellungen/fahrzeug", methods=["POST"])
    async def fahrzeug_speichern(request: Request) -> FT:
        rohdaten = await request.form()
        form = read_vehicle_form({k: str(v) for k, v in rohdaten.items()})
        if not form.valid:
            return settings.fahrzeugformular(ctx, form.errors)
        ctx.db().save_vehicle(form.vehicle)
        return settings.fahrzeugformular(ctx, gespeichert=True)

    @rt("/einstellungen/pruefung", methods=["POST"])
    async def pruefung_speichern(request: Request) -> FT:
        rohdaten = await request.form()
        db = ctx.db()
        land = str(rohdaten.get("federal_state", "BB"))
        if land in {code for code, _ in settings.BUNDESLAENDER}:
            db.set_setting("federal_state", land)
        db.set_setting("home_address", str(rohdaten.get("home_address", "")).strip())
        for name, _, _, _ in settings.SCHALTER:
            db.set_setting(name, "1" if rohdaten.get(name) else "0")
        return settings.pruefformular(ctx, gespeichert=True)

    @rt("/einstellungen/kategorien", methods=["POST"])
    async def kategorien_speichern(request: Request) -> FT:
        rohdaten = await request.form()
        db = ctx.db()
        zu_loeschen = str(rohdaten.get("loeschen", "")).strip()
        if zu_loeschen.isdigit():
            db.delete_category(int(zu_loeschen))
            ctx.uebernehme_kategorien()
            return settings.kategorienformular(ctx, meldung="Kategorie gelöscht.")
        for kategorie in db.get_categories():
            kid = int(str(kategorie.get("id", 0)) or 0)
            name = str(kategorie.get("name", ""))
            beschriftung = str(rohdaten.get(f"beschriftung_{kid}", "")).strip()
            db.update_category(
                kid,
                name,
                beschriftung or name,
                bool(rohdaten.get(f"geschaeftlich_{kid}")),
                str(rohdaten.get(f"farbe_{kid}", "")).strip() or str(kategorie.get("color", "") or ""),
            )
        ctx.uebernehme_kategorien()
        return settings.kategorienformular(ctx, meldung="Kategorien gespeichert.")

    # --- Helfer -----------------------------------------------------------------------

    def _sperrtag(entry_id: int) -> dict[str, Any] | None:
        return next((e for e in ctx.db().get_blacklist() if int(str(e.get("id", 0)) or 0) == entry_id), None)

    def _monat_der_fahrt(iso: str) -> Monat:
        try:
            tag = date.fromisoformat(iso)
        except ValueError:
            return ctx.standardmonat()
        return Monat(jahr=tag.year, monat=tag.month)

    def _leeres_formular(monat: Monat, datum_iso: str) -> TripForm:
        """Vorbelegung einer neuen Fahrt: Datum aus dem Zeitraum, km-Stand vom Vorgaenger.

        `get_last_km_end` sieht nur in den Monat selbst, in einem leeren Monat also ins
        Leere. Dann zaehlt der Stand vor dem ersten Tag des Zeitraums.
        """
        heute = date.today()
        if datum_iso:
            vorgabe = iso_to_de(datum_iso)
        elif (heute.year, heute.month) == (monat.jahr, monat.monat):
            vorgabe = f"{heute:%d.%m.%Y}"
        else:
            vorgabe = f"01.{monat.monat:02d}.{monat.jahr}"
        db = ctx.db()
        letzter_stand = db.get_last_km_end(monat.jahr, monat.monat)
        if not letzter_stand:
            letzter_stand = db.get_km_end_before(f"{monat.jahr}-{monat.monat:02d}-01")
        werte = dict.fromkeys(FELDER, "")
        werte.update(
            {
                "datum": vorgabe,
                "kategorie": "business",
                "km_anfang": format_km(letzter_stand) if letzter_stand else "",
            }
        )
        return TripForm(values=werte)

    return app
