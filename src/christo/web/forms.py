"""Die Formulare der Weboberflaeche: Eingaben lesen, pruefen, in Fachobjekte uebersetzen.

Fahrt, Sperrtag, Fahrzeug und Arbeitszeit. Alles ohne FastHTML, damit es sich ohne Server
testen laesst. Die Speicherregeln selbst kommen aus dem Kern (`services/trip_rules.py`),
hier wird nur die Eingabe geprueft.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date

from christo.models.trip import Trip, get_informational_categories
from christo.models.vehicle import Vehicle
from christo.services.formatting import (
    de_to_iso,
    format_km,
    format_liters,
    iso_to_de,
    parse_km,
    parse_liters,
)
from christo.services.trip_rules import FUEL_CATEGORIES, km_end_from_columns, normalize_trip

_DATUM = re.compile(r"^\d{2}\.\d{2}\.\d{4}$")
_UHRZEIT = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")
_ZAHL = re.compile(r"^[\d.,\s]*$")

# Feldnamen im Formular. Bewusst deutsch wie die TUI-Oberflaeche, stabil fuer Tests.
FELDER = (
    "datum",
    "abfahrt",
    "ankunft",
    "ziel",
    "zweck",
    "kategorie",
    "km_anfang",
    "km_geschaeftlich",
    "km_privat",
    "hin_und_zurueck",
    "tankliter",
    "volltank",
)


@dataclass
class TripForm:
    """Formularzustand: die eingegebenen Texte und die Fehler je Feld."""

    values: dict[str, str]
    errors: dict[str, str] = field(default_factory=dict)

    @property
    def valid(self) -> bool:
        return not self.errors


def pruefe_datum(text: str, pflicht: bool = True) -> str:
    """Prueft ein deutsches Datum und gibt den Fehlertext zurueck, oder leer wenn es passt."""
    text = text.strip()
    if not text:
        return "Bitte ein Datum eintragen." if pflicht else ""
    if not _DATUM.match(text):
        return "Datum bitte als TT.MM.JJJJ eintragen, zum Beispiel 16.05.2026."
    try:
        date.fromisoformat(de_to_iso(text))
    except ValueError:
        return "Dieses Datum gibt es nicht."
    return ""


def form_from_trip(trip: Trip) -> TripForm:
    """Vorbelegung des Formulars aus einer gespeicherten Fahrt."""
    return TripForm(
        values={
            "datum": iso_to_de(trip.date),
            "abfahrt": trip.time_from,
            "ankunft": trip.time_to,
            "ziel": trip.destination,
            "zweck": trip.purpose,
            "kategorie": trip.category,
            "km_anfang": format_km(trip.km_start),
            "km_geschaeftlich": format_km(trip.km_business),
            "km_privat": format_km(trip.km_private),
            "hin_und_zurueck": "1" if trip.round_trip else "",
            "tankliter": format_liters(trip.fuel_liters),
            "volltank": "1" if trip.fuel_full_tank else "",
        }
    )


def read_form(data: Mapping[str, str], categories: set[str]) -> TripForm:
    """Liest und prueft die Eingaben.

    Args:
        data: Die Formularfelder als Text. Fehlende Felder gelten als leer, nicht angehakte
            Kontrollkaestchen fehlen im Formular ganz.
        categories: Die erlaubten Kategorienamen aus der Datenbank.

    Returns:
        Den Formularzustand mit Fehlern je Feld. Fehlertexte sagen, was zu tun ist.
    """
    werte = {name: str(data.get(name, "")).strip() for name in FELDER}
    fehler: dict[str, str] = {}

    datumsfehler = pruefe_datum(werte["datum"])
    if datumsfehler:
        fehler["datum"] = datumsfehler

    for feld, name in (("abfahrt", "Abfahrt"), ("ankunft", "Ankunft")):
        if werte[feld] and not _UHRZEIT.match(werte[feld]):
            fehler[feld] = f"{name} bitte als HH:MM eintragen, zum Beispiel 07:15."
    if (
        werte["abfahrt"]
        and werte["ankunft"]
        and "abfahrt" not in fehler
        and "ankunft" not in fehler
        and werte["ankunft"] < werte["abfahrt"]
    ):
        fehler["ankunft"] = "Die Ankunft liegt vor der Abfahrt."

    if werte["kategorie"] not in categories:
        fehler["kategorie"] = "Bitte eine Kategorie aus der Liste wählen."

    for feld in ("km_anfang", "km_geschaeftlich", "km_privat"):
        if not _ZAHL.match(werte[feld]):
            fehler[feld] = "Bitte nur Ziffern eintragen."
    if werte["tankliter"] and parse_liters(werte["tankliter"]) <= 0:
        fehler["tankliter"] = "Liter bitte als Zahl eintragen, zum Beispiel 42,5."

    informationell = werte["kategorie"] in get_informational_categories()
    if not informationell and "kategorie" not in fehler:
        strecke = parse_km(werte["km_geschaeftlich"]) + parse_km(werte["km_privat"])
        if not fehler.get("km_geschaeftlich") and not fehler.get("km_privat") and strecke <= 0:
            fehler["km_geschaeftlich"] = "Bitte die gefahrenen Kilometer eintragen."

    return TripForm(values=werte, errors=fehler)


def trip_from_form(form: TripForm, trip_id: int) -> Trip:
    """Uebersetzt ein gueltiges Formular in die zu speichernde Fahrt.

    Der Endstand ergibt sich wie in der TUI aus Anfang plus beiden km-Spalten. Danach gelten
    die gemeinsamen Speicherregeln.

    Raises:
        ValueError: Wenn das Formular Fehler hat.
    """
    if not form.valid:
        raise ValueError("Formular mit Fehlern laesst sich nicht speichern")
    w = form.values
    km_anfang = parse_km(w["km_anfang"])
    km_geschaeftlich = parse_km(w["km_geschaeftlich"])
    km_privat = parse_km(w["km_privat"])
    tanken = w["kategorie"] in FUEL_CATEGORIES
    return normalize_trip(
        Trip(
            id=trip_id,
            date=de_to_iso(w["datum"]),
            time_from=w["abfahrt"],
            time_to=w["ankunft"],
            destination=w["ziel"],
            purpose=w["zweck"],
            km_start=km_anfang,
            km_end=km_end_from_columns(km_anfang, km_geschaeftlich, km_privat),
            km_business=km_geschaeftlich,
            km_private=km_privat,
            category=w["kategorie"],
            round_trip=bool(w["hin_und_zurueck"]),
            fuel_liters=parse_liters(w["tankliter"]) if tanken else 0.0,
            fuel_full_tank=bool(w["volltank"]) and tanken,
        )
    )


# --- Sperrtag (Blacklist) ----------------------------------------------------------------


@dataclass
class BlacklistForm:
    """Ein Sperrtag im Formular."""

    datum: str
    grund: str
    errors: dict[str, str] = field(default_factory=dict)

    @property
    def valid(self) -> bool:
        return not self.errors

    @property
    def datum_iso(self) -> str:
        return de_to_iso(self.datum)


def read_blacklist_form(data: Mapping[str, str]) -> BlacklistForm:
    """Liest und prueft einen Sperrtag."""
    datum = str(data.get("datum", "")).strip()
    grund = str(data.get("grund", "")).strip()
    fehler: dict[str, str] = {}
    datumsfehler = pruefe_datum(datum)
    if datumsfehler:
        fehler["datum"] = datumsfehler
    if not grund:
        fehler["grund"] = "Bitte einen Grund eintragen, zum Beispiel Urlaub."
    return BlacklistForm(datum=datum, grund=grund, errors=fehler)


# --- Fahrzeug ----------------------------------------------------------------------------


@dataclass
class VehicleForm:
    """Die Fahrzeugstammdaten im Formular."""

    vehicle: Vehicle
    errors: dict[str, str] = field(default_factory=dict)

    @property
    def valid(self) -> bool:
        return not self.errors


def _ganzzahl(roh: str, feld: str, fehler: dict[str, str], standard: int = 0) -> int:
    roh = roh.strip()
    if not roh:
        return standard
    if not _ZAHL.match(roh):
        fehler[feld] = "Bitte nur Ziffern eintragen."
        return standard
    return parse_km(roh, standard)


def _kommazahl(roh: str, feld: str, fehler: dict[str, str]) -> float:
    roh = roh.strip()
    if not roh:
        return 0.0
    wert = parse_liters(roh)
    if wert <= 0:
        fehler[feld] = "Bitte eine Zahl eintragen, zum Beispiel 42,5."
    return wert


def read_vehicle_form(data: Mapping[str, str]) -> VehicleForm:
    """Liest und prueft die Fahrzeugstammdaten."""
    fehler: dict[str, str] = {}
    werte = {name: str(wert).strip() for name, wert in data.items()}

    name = werte.get("name", "")
    if not name:
        fehler["name"] = "Bitte eine Bezeichnung eintragen."

    daten_iso: dict[str, str] = {}
    for feld in ("start_date", "end_date"):
        roh = werte.get(feld, "")
        datumsfehler = pruefe_datum(roh, pflicht=False)
        if datumsfehler:
            fehler[feld] = datumsfehler
        daten_iso[feld] = de_to_iso(roh) if roh and not datumsfehler else ""

    if not fehler.get("start_date") and not fehler.get("end_date"):
        von, bis = daten_iso["start_date"], daten_iso["end_date"]
        if von and bis and bis < von:
            fehler["end_date"] = "Das Vertragsende liegt vor dem Beginn."

    start_km = _ganzzahl(werte.get("start_km", ""), "start_km", fehler)
    end_km = _ganzzahl(werte.get("end_km", ""), "end_km", fehler)
    if not fehler.get("start_km") and not fehler.get("end_km") and end_km and end_km < start_km:
        fehler["end_km"] = "Der aktuelle Stand liegt unter dem bei der Übernahme."

    fahrzeug = Vehicle(
        name=name,
        plate=werte.get("plate", ""),
        contract_number=werte.get("contract_number", ""),
        lease_km_per_month=_ganzzahl(werte.get("lease_km_per_month", ""), "lease_km_per_month", fehler, 1500),
        start_km=start_km,
        end_km=end_km,
        start_date=daten_iso["start_date"],
        end_date=daten_iso["end_date"],
        lease_months=_ganzzahl(werte.get("lease_months", ""), "lease_months", fehler, 12),
        tank_capacity_l=_kommazahl(werte.get("tank_capacity_l", ""), "tank_capacity_l", fehler),
        consumption_l_100km=_kommazahl(werte.get("consumption_l_100km", ""), "consumption_l_100km", fehler),
    )
    return VehicleForm(vehicle=fahrzeug, errors=fehler)


# --- Arbeitszeit -------------------------------------------------------------------------


def read_worktimes(data: Mapping[str, str]) -> dict[int, float]:
    """Liest die zwoelf Stundenfelder.

    Returns:
        Monat auf Stunden. Ein leeres oder unlesbares Feld ergibt 0.0 und loescht den Monat.
    """
    stunden: dict[int, float] = {}
    for monat in range(1, 13):
        roh = str(data.get(f"monat_{monat}", "")).strip()
        stunden[monat] = parse_liters(roh) if roh else 0.0
    return stunden
