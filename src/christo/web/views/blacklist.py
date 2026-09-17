"""Die Blacklist: Tage, an denen keine geschaeftliche Fahrt stattgefunden haben kann.

Urlaub, Krankheit, Feiertage mit Nachweis. Die Plausibilitaetspruefung schlaegt an, wenn an
so einem Tag trotzdem geschaeftliche Kilometer stehen.
"""

from __future__ import annotations

from typing import Any

from fasthtml.common import Button, Div, Form, Input, Label, Span, Textarea

from christo.services.formatting import iso_to_de
from christo.web.context import Context

FT = Any


def tabellenpanel() -> FT:
    """Der Platz fuer die Tabelle der Sperrtage."""
    return Div(Div(id="tabelle"), cls="panel tabellenpanel")


def zeilen(ctx: Context) -> list[dict[str, object]]:
    """Die Sperrtage als Tabellenzeilen, mit der Zahl der Belege."""
    db = ctx.db()
    ergebnis: list[dict[str, object]] = []
    for eintrag in db.get_blacklist():
        eintrag_id = int(str(eintrag.get("id", 0)) or 0)
        belege = db.get_documents(blacklist_id=eintrag_id)
        ergebnis.append(
            {
                "id": eintrag_id,
                "datum": iso_to_de(str(eintrag.get("date", ""))),
                "grund": str(eintrag.get("reason", "")),
                "belege": len(belege) or "",
            }
        )
    return ergebnis


def uebersicht(ctx: Context) -> FT:
    """Die Zusammenfassung unter der Tabelle."""
    eintraege = ctx.db().get_blacklist()
    jahre = sorted({str(e.get("date", ""))[:4] for e in eintraege if str(e.get("date", ""))})
    return Div(
        Div(
            Span(f"{len(eintraege)} gesperrte Tage"),
            Span("|", cls="trenner"),
            Span(f"Jahre: {', '.join(jahre)}" if jahre else "keine Einträge", cls="gedaempft"),
            cls="panel summe",
        ),
        id="uebersicht",
    )


def dialog(eintrag_id: int, datum: str, grund: str, fehler: dict[str, str] | None = None) -> FT:
    """Der Dialog zum Anlegen oder Bearbeiten eines Sperrtags."""
    fehler = fehler or {}
    neu = eintrag_id <= 0
    ziel = "/blacklist/neu" if neu else f"/blacklist/{eintrag_id}"
    return Div(
        Div(
            Form(
                Div(
                    Span("Neuer Sperrtag" if neu else "Sperrtag bearbeiten", cls="legende"),
                    Div(
                        Label("Datum", fr="f-datum", cls="form-label"),
                        Input(
                            id="f-datum",
                            name="datum",
                            value=datum,
                            inputmode="numeric",
                            placeholder="16.05.2026",
                            cls="form-control is-invalid" if fehler.get("datum") else "form-control",
                        ),
                        Div(fehler["datum"], cls="invalid-feedback") if fehler.get("datum") else None,
                        cls="mb-2",
                    ),
                    Div(
                        Label("Grund", fr="f-grund", cls="form-label"),
                        Textarea(
                            grund,
                            id="f-grund",
                            name="grund",
                            rows="2",
                            cls="form-control is-invalid" if fehler.get("grund") else "form-control",
                            placeholder="Urlaub, Krankheit, Feiertag",
                        ),
                        Div(fehler["grund"], cls="invalid-feedback") if fehler.get("grund") else None,
                        cls="mb-2",
                    ),
                    Div(fehler["speichern"], cls="speicherfehler") if fehler.get("speichern") else None,
                    Div(
                        None
                        if neu
                        else Button(
                            "Löschen",
                            type="button",
                            cls="btn btn-loeschen",
                            hx_post=f"/blacklist/{eintrag_id}/loeschen",
                            hx_target="#dialog",
                            hx_swap="outerHTML",
                        ),
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
            cls="dialog-rahmen dialog-schmal",
        ),
        id="dialog",
        cls="dialog-hintergrund",
    )
