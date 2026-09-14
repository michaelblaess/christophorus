"""JSON-Export fuer Fahrtenbuch-Listen (Monat / Jahr).

Bewusst verlustfrei: jede Fahrt mit allen Feldern des Modells, unabhaengig
davon, was Excel oder Markdown zeigen. Wer JSON waehlt, will weiterverarbeiten.

Die Zusammenfassung rechnet wie die Statusleiste der Anwendung (MonthData):
km einer nicht-geschaeftlichen Kategorie zaehlen dort als privat, auch wenn
sie im Feld km_business stehen. Die Rohwerte stehen unveraendert in `trips`.
"""

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from death_proof.models.export_job import ExportJob
from death_proof.models.trip import MonthData

SCHEMA = "death-proof/fahrtenbuch-export"
VERSION = 1


def build_json(job: ExportJob) -> dict[str, Any]:
    """Baut die JSON-Struktur.

    Args:
        job: Was exportiert werden soll.

    Returns:
        Ein serialisierbares Dict.
    """
    summary = MonthData(year=job.year, month=job.month or 0, trips=job.trips)
    return {
        "schema": SCHEMA,
        "version": VERSION,
        "title": job.title,
        "subtitle": job.subtitle,
        "vehicle": {"name": job.vehicle_name, "plate": job.vehicle_plate},
        "period": {"year": job.year, "month": job.month},
        "summary": {
            "trips": len(job.trips),
            "km_business": summary.km_business,
            "km_private": summary.km_private,
            "km_total": summary.km_total,
        },
        "trips": [
            {
                **asdict(trip),
                "km_total": trip.km_total,
                "counts_as_business": trip.is_business_km,
                "informational": trip.is_informational,
                "category_label": job.category_labels.get(trip.category, trip.category),
            }
            for trip in job.trips
        ],
    }


def export_json(job: ExportJob, out_path: Path) -> None:
    """Schreibt den Auftrag als JSON-Datei (UTF-8, LF).

    Args:
        job: Was exportiert werden soll.
        out_path: Zielpfad der .json-Datei.
    """
    text = json.dumps(build_json(job), indent=2, ensure_ascii=False)
    out_path.write_text(f"{text}\n", encoding="utf-8", newline="\n")
