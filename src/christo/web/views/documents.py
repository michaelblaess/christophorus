"""Die Belege: Tankquittungen, Werkstattrechnungen, Nachweise zu Sperrtagen.

Die Dateien selbst liegen beim Original-Fahrtenbuch, nicht in der Arbeitskopie - die Kopie
enthaelt nur die Datenbank. Der Browser bekommt sie ueber `/belege/<id>/datei`, und nur die
Pfade, die in der Datenbank stehen.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fasthtml.common import Div, Span

from christo.services.formatting import iso_to_de
from christo.web.context import Context

FT = Any


def tabellenpanel() -> FT:
    """Der Platz fuer die Belegtabelle."""
    return Div(Div(id="tabelle"), cls="panel tabellenpanel")


def datei_pfad(ctx: Context, doc_id: int) -> Path | None:
    """Die Datei zu einem Beleg, oder None wenn es sie nicht (mehr) gibt.

    Relative Pfade zaehlen ab dem Original-Fahrtenbuch.
    """
    beleg = next((d for d in ctx.db().get_all_documents() if int(str(d.get("id", 0)) or 0) == doc_id), None)
    if beleg is None:
        return None
    roh = str(beleg.get("path", ""))
    if not roh:
        return None
    pfad = Path(roh)
    if not pfad.is_absolute():
        pfad = ctx.workspace.source / pfad
    return pfad if pfad.is_file() else None


def zeilen(ctx: Context) -> list[dict[str, object]]:
    """Die Belege als Tabellenzeilen, aeltester zuerst."""
    ergebnis: list[dict[str, object]] = []
    for beleg in ctx.db().get_all_documents():
        fahrt_datum = str(beleg.get("trip_date") or "")
        sperr_datum = str(beleg.get("bl_date") or "")
        if beleg.get("trip_id"):
            art, bezug = "Fahrt", str(beleg.get("trip_purpose") or "")
            bemerkung = ""
            liter = beleg.get("trip_fuel_liters")
            if str(beleg.get("trip_category") or "") in ("fuel", "fuel_private") and liter:
                bemerkung = f"{float(str(liter)):.2f} L".replace(".", ",")
        elif beleg.get("blacklist_id"):
            art, bezug, bemerkung = "Sperrtag", str(beleg.get("bl_reason") or ""), ""
        else:
            art, bezug, bemerkung = "-", "", ""
        roh = str(beleg.get("path", ""))
        doc_id = int(str(beleg.get("id", 0)) or 0)
        ergebnis.append(
            {
                "id": doc_id,
                "sortierung": fahrt_datum or sperr_datum,
                "art": art,
                "datum": iso_to_de(fahrt_datum or sperr_datum),
                "zeit": str(beleg.get("trip_time_from") or "")[:5],
                "bezug": bezug,
                "bemerkung": bemerkung,
                "datei": Path(roh).name or roh,
                "vorhanden": datei_pfad(ctx, doc_id) is not None,
            }
        )
    return sorted(ergebnis, key=lambda z: str(z["sortierung"]))


def _fehlmeldung(anzahl: int) -> str:
    if not anzahl:
        return "alle Dateien vorhanden"
    return "1 Datei fehlt" if anzahl == 1 else f"{anzahl} Dateien fehlen"


def uebersicht(ctx: Context) -> FT:
    """Zusammenfassung: wie viele Belege, wie viele Dateien fehlen."""
    alle = zeilen(ctx)
    fehlend = [z for z in alle if not z["vorhanden"]]
    return Div(
        Div(
            Span(f"{len(alle)} Belege"),
            Span("|", cls="trenner"),
            Span(f"zu Fahrten: {sum(1 for z in alle if z['art'] == 'Fahrt')}"),
            Span("|", cls="trenner"),
            Span(f"zu Sperrtagen: {sum(1 for z in alle if z['art'] == 'Sperrtag')}"),
            Span("|", cls="trenner"),
            Span(
                _fehlmeldung(len(fehlend)),
                cls="schwere-warning" if fehlend else "gruen",
            ),
            cls="panel summe",
        ),
        Div(
            Span("Hinweis", cls="legende"),
            Div(
                f"Die Dateien liegen beim Original unter {ctx.workspace.source}. "
                "Die Arbeitskopie enthält nur die Datenbank, ein Klick lädt die Datei von dort.",
                cls="gedaempft",
            ),
            cls="panel protokoll",
        ),
        id="uebersicht",
    )
