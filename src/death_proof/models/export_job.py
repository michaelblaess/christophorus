"""Was ein Export schreiben soll - unabhaengig vom Format."""

from __future__ import annotations

from dataclasses import dataclass, field

from death_proof.models.trip import Trip


@dataclass(frozen=True)
class ExportJob:
    """Alle Angaben, die jeder Exporter braucht.

    Die Oberflaeche stellt den Auftrag einmal zusammen, jedes Format liest
    daraus. So entsteht der Titel nicht in jedem Exporter ein zweites Mal.

    Attributes:
        trips: Die Fahrten, nach Datum sortiert.
        title: Haupttitel, z.B. "Fahrtenbuch Audi A5 (B-XX 1)".
        subtitle: Untertitel mit Zeitraum und Leasing-Angabe.
        year: Das exportierte Jahr.
        month: Der exportierte Monat, oder None beim Jahresexport.
        group_by_month: Monats-Zwischensummen einfuegen (Jahresexport).
        category_labels: Kategorie-Code auf Anzeigename.
        vehicle_name: Fahrzeugbezeichnung, leer wenn unbekannt.
        vehicle_plate: Kennzeichen, leer wenn unbekannt.
    """

    trips: list[Trip]
    title: str
    subtitle: str
    year: int
    month: int | None = None
    group_by_month: bool = False
    category_labels: dict[str, str] = field(default_factory=dict)
    vehicle_name: str = ""
    vehicle_plate: str = ""
