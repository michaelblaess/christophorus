"""Markdown-Export fuer Fahrtenbuch-Listen (Monat / Jahr).

Folgt dem Excel-Export Zeile fuer Zeile: dieselben Spalten, dieselbe
km-Kette, dieselben Zwischensummen. Wo Excel eine Formel schreibt, steht hier
der Wert, den die Formel ergeben wuerde - die Kette beginnt beim km-Stand der
ersten realen Fahrt und laeuft ueber geschaeftliche plus private km weiter.
"""

from pathlib import Path

from death_proof.models.export_job import ExportJob
from death_proof.models.trip import get_informational_categories
from death_proof.services.export_rows import format_time_range, is_untimed_private, iso_to_date, month_label
from death_proof.services.formatting import format_km

_HEADER = "| Datum | Fahrzeit | Ziel | Reisezweck | km Anfang | km Ende | km gesch. | km privat |"
_SEPARATOR = "| --- | --- | --- | --- | ---: | ---: | ---: | ---: |"


def export_markdown(job: ExportJob, out_path: Path) -> None:
    """Schreibt den Auftrag als Markdown-Datei (UTF-8, LF).

    Args:
        job: Was exportiert werden soll.
        out_path: Zielpfad der .md-Datei.
    """
    out_path.write_text(render_markdown(job), encoding="utf-8", newline="\n")


def render_markdown(job: ExportJob) -> str:
    """Baut den Markdown-Text.

    Args:
        job: Was exportiert werden soll.

    Returns:
        Der vollstaendige Text mit abschliessendem Zeilenumbruch.
    """
    lines = [f"# {_cell(job.title)}", ""]
    if job.subtitle:
        lines += [_cell(job.subtitle), ""]
    lines += [_HEADER, _SEPARATOR]

    informational = get_informational_categories()
    km_end: int | None = None
    total_business = total_private = 0
    month_business = month_private = 0
    current_month: tuple[int, int] | None = None
    month_has_trips = False

    for trip in job.trips:
        date_obj = iso_to_date(trip.date)
        trip_month = (date_obj.year, date_obj.month) if date_obj else (0, 0)

        if job.group_by_month and current_month is not None and trip_month != current_month:
            if month_has_trips:
                lines.append(_sum_row(f"Summe {month_label(*current_month)}", km_end, month_business, month_private))
            month_business = month_private = 0
            month_has_trips = False
        current_month = trip_month

        date_text = f"{date_obj:%d.%m.%Y}" if date_obj else _cell(trip.date)

        if trip.category in informational:
            label = job.category_labels.get(trip.category, trip.category)
            lines.append(f"| {date_text} |  | *{_cell(label)}* |  |  |  |  |  |")
            continue

        # Wie im Excel: erste reale Zeile nimmt ihren km-Stand, jede weitere
        # startet am Ende der vorherigen.
        km_start = trip.km_start if km_end is None else km_end
        km_end = km_start + trip.km_business + trip.km_private
        month_business += trip.km_business
        month_private += trip.km_private
        total_business += trip.km_business
        total_private += trip.km_private
        month_has_trips = True

        cells = [
            "" if is_untimed_private(trip) else date_text,
            _cell(format_time_range(trip.time_from, trip.time_to)),
            _cell(trip.destination),
            _cell(trip.purpose),
            format_km(km_start) if km_start else "",
            format_km(km_end),
            format_km(trip.km_business) if trip.km_business else "",
            format_km(trip.km_private) if trip.km_private else "",
        ]
        lines.append(f"| {' | '.join(cells)} |")

    if job.group_by_month and current_month is not None and month_has_trips:
        lines.append(_sum_row(f"Summe {month_label(*current_month)}", km_end, month_business, month_private))

    lines.append(_sum_row("Gesamt", km_end, total_business, total_private))
    return "\n".join(lines) + "\n"


def _sum_row(label: str, km_end: int | None, business: int, private: int) -> str:
    """Baut eine fett gesetzte Summenzeile.

    Args:
        label: Beschriftung in der Spalte Reisezweck.
        km_end: km-Stand am Ende des Abschnitts, None wenn es keine reale Fahrt gab.
        business: Summe der geschaeftlichen km.
        private: Summe der privaten km.

    Returns:
        Die Tabellenzeile.
    """
    end_text = f"**{format_km(km_end)}**" if km_end is not None else ""
    return f"|  |  |  | **{label}** |  | {end_text} | **{format_km(business)}** | **{format_km(private)}** |"


def _cell(text: str) -> str:
    """Macht einen Text tabellentauglich.

    Ein senkrechter Strich wuerde die Zelle beenden, ein Zeilenumbruch die
    Tabelle.

    Args:
        text: Der Rohtext.

    Returns:
        Der maskierte, einzeilige Text.
    """
    return " ".join(text.split()).replace("|", "\\|")
