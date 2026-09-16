"""Verfremdet Fahrtenbuch-Daten fuer Screenshots und Vorfuehrungen.

Nur fuer die Anzeige: Die Datenbank und die Exporte bleiben unberuehrt. Jeder
echte Wert bekommt einen stabilen Ersatz - derselbe Kunde heisst in jeder
Ansicht und nach jedem Neuladen gleich, damit ein Screenshot in sich stimmig ist.

Zusaetzlich merkt sich der Anonymizer jedes ersetzte Paar. `censor()` ersetzt
damit freie Texte wie Log-Zeilen oder Pruefmeldungen, in denen die echten Werte
eingebettet vorkommen.
"""

from __future__ import annotations

import zlib
from dataclasses import replace
from pathlib import PurePath
from typing import Any

from christo.models.trip import MonthData, Trip
from christo.models.vehicle import Vehicle

FAKE_PATH = "~/Fahrtenbuch"
FAKE_VEHICLE = "Kompaktwagen"
FAKE_PLATE = "B-XX 1"
FAKE_CONTRACT = "V-0000"

# Die Hervorhebung von Geschaeftsessen haengt am Wort im Reisezweck (trip_table,
# calendar_view, plausibility). Es muss den Ersatz ueberleben.
_KEEP_KEYWORDS = ("geschaeftsessen", "geschäftsessen")

_DESTINATIONS = (
    "Kunde Nord",
    "Kunde Süd",
    "Kunde West",
    "Kunde Ost",
    "Musterfirma GmbH, Musterstadt",
    "Beispiel AG, Beispielstadt",
    "Tankstelle Hauptstraße",
    "Baumarkt Am Ring",
    "Steuerbüro Musterweg",
    "Werkstatt Industriestraße",
    "Büro Zentrum",
    "Lager Gewerbegebiet",
)

_PURPOSES = (
    "Kundentermin",
    "Projektbesprechung",
    "Abstimmung vor Ort",
    "Wartung",
    "Tanken",
    "Einkauf Material",
    "Besprechung Steuerbüro",
    "Schulung",
    "Abholung Unterlagen",
    "Präsentation",
)

_REASONS = ("Urlaub", "Krank", "Brückentag", "Fortbildung", "Überstundenausgleich")

_DOCUMENT_DESCRIPTIONS = ("Tankbeleg", "Rechnung", "Quittung", "Werkstattrechnung")

# Kuerzere Werte nicht fuer censor() registrieren - "Tanken" oder "Test" koennten
# sonst in Woertern mitten im Log ersetzt werden.
_MIN_CENSOR_LENGTH = 4


def _pick(pool: tuple[str, ...], original: str) -> str:
    """Waehlt stabil einen Ersatz: gleicher Text, gleiche Auswahl, ueber Laeufe hinweg."""
    return pool[zlib.crc32(original.encode("utf-8")) % len(pool)]


class Anonymizer:
    """Liefert verfremdete Kopien und merkt sich die Paare fuer censor()."""

    def __init__(self) -> None:
        self._pairs: dict[str, str] = {}

    def _remember(self, original: str, fake: str) -> str:
        original = original.strip()
        if len(original) >= _MIN_CENSOR_LENGTH and original != fake:
            self._pairs[original] = fake
        return fake

    # --- Einzelwerte ------------------------------------------------------------

    def destination(self, value: str) -> str:
        """Ersatz fuer ein Ziel. Leer bleibt leer, mehrzeilige Adressen zaehlen als Ganzes."""
        if not value.strip():
            return value
        fake = _pick(_DESTINATIONS, value)
        for line in value.split("\n"):
            self._remember(line, fake)
        return self._remember(value, fake)

    def purpose(self, value: str) -> str:
        """Ersatz fuer einen Reisezweck. Das Wort Geschaeftsessen bleibt erhalten."""
        if not value.strip():
            return value
        lower = value.lower()
        keyword = next((k for k in _KEEP_KEYWORDS if k in lower), None)
        fake = _pick(_PURPOSES, value)
        if keyword is not None:
            fake = f"Geschaeftsessen {fake}"
        return self._remember(value, fake)

    def reason(self, value: str) -> str:
        """Ersatz fuer den Grund eines gesperrten Tages."""
        if not value.strip():
            return value
        return self._remember(value, _pick(_REASONS, value))

    def document_path(self, value: str) -> str:
        """Ersatz fuer einen Belegpfad: fester Name, die Dateiendung bleibt."""
        if not value.strip():
            return value
        original = PurePath(value)
        number = zlib.crc32(value.encode("utf-8")) % 1000
        fake = f"belege/Beleg-{number:03d}{original.suffix}"
        self._remember(original.name, PurePath(fake).name)
        return self._remember(value, fake)

    def path(self, value: str) -> str:
        """Ersatz fuer den Ordner des Fahrtenbuchs."""
        if not value.strip():
            return value
        self._remember(PurePath(value).name, PurePath(FAKE_PATH).name)
        return self._remember(value, FAKE_PATH)

    # --- Zusammengesetzte Daten -------------------------------------------------

    def trip(self, trip: Trip) -> Trip:
        """Kopie einer Fahrt mit verfremdetem Ziel und Zweck. km, Datum und Zeiten bleiben."""
        return replace(trip, destination=self.destination(trip.destination), purpose=self.purpose(trip.purpose))

    def month_data(self, data: MonthData) -> MonthData:
        """Kopie eines Monats (oder Jahres) mit verfremdeten Fahrten."""
        return replace(data, trips=[self.trip(trip) for trip in data.trips])

    def vehicle(self, vehicle: Vehicle | None) -> Vehicle | None:
        """Kopie des Fahrzeugs ohne Name, Kennzeichen und Vertragsnummer. Leasingzahlen bleiben."""
        if vehicle is None:
            return None
        self._remember(vehicle.name, FAKE_VEHICLE)
        self._remember(vehicle.plate, FAKE_PLATE)
        self._remember(vehicle.contract_number, FAKE_CONTRACT)
        return replace(vehicle, name=FAKE_VEHICLE, plate=FAKE_PLATE, contract_number=FAKE_CONTRACT)

    def blacklist_entries(self, entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Kopien der gesperrten Tage mit verfremdetem Grund."""
        return [{**entry, "reason": self.reason(str(entry.get("reason") or ""))} for entry in entries]

    def documents(self, documents: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Kopien der Belege mit verfremdetem Pfad, Beschreibung, Zweck und Grund."""
        result: list[dict[str, Any]] = []
        for doc in documents:
            description = str(doc.get("description") or "")
            fake_description = (
                self._remember(description, _pick(_DOCUMENT_DESCRIPTIONS, description)) if description.strip() else ""
            )
            result.append(
                {
                    **doc,
                    "path": self.document_path(str(doc.get("path") or "")),
                    "description": fake_description,
                    "trip_purpose": self.purpose(str(doc.get("trip_purpose") or "")),
                    "bl_reason": self.reason(str(doc.get("bl_reason") or "")),
                }
            )
        return result

    # --- Freie Texte ------------------------------------------------------------

    def censor(self, text: str) -> str:
        """Ersetzt alle bisher gesehenen echten Werte in einem freien Text.

        Laengere Werte zuerst - sonst frisst der Ort "Musterstadt" die Adresse
        "Musterfirma, Musterstadt", bevor sie als Ganzes ersetzt werden kann.
        """
        for original in sorted(self._pairs, key=len, reverse=True):
            if original in text:
                text = text.replace(original, self._pairs[original])
        return text
