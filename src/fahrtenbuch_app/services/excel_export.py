"""Excel-Export fuer Fahrtenbuch-Listen (Monat / Jahr)."""

from datetime import datetime
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.worksheet import Worksheet

from fahrtenbuch_app.models.trip import Trip


# Layout orientiert am Vorlage-Fahrtenbuch
_COLUMN_WIDTHS = {
    "A": 12,   # Datum
    "B": 14,   # Fahrzeit von-bis
    "C": 36,   # Route / Ziel
    "D": 32,   # Reisezweck
    "E": 12,   # km Anfang
    "F": 12,   # km Ende
    "G": 12,   # km geschaeftlich
    "H": 14,   # Wohnung/Arbeit (leer — historisch)
    "I": 12,   # km privat
}

_HEADER_FILL = PatternFill(start_color="FFCCCCCC", end_color="FFCCCCCC", fill_type="solid")
_TOTAL_FILL = PatternFill(start_color="FFEEEEEE", end_color="FFEEEEEE", fill_type="solid")
_THIN = Side(style="thin", color="FF999999")
_BORDER = Border(left=_THIN, right=_THIN, top=_THIN, bottom=_THIN)


def _iso_to_date(iso: str) -> datetime | None:
    """Konvertiert YYYY-MM-DD zu datetime.date, None bei Fehler."""
    try:
        return datetime.strptime(iso, "%Y-%m-%d")
    except (ValueError, TypeError):
        return None


def _format_time_range(time_from: str, time_to: str) -> str:
    """Formatiert Fahrzeit als 'HH:MM - HH:MM' oder einzeln."""
    if time_from and time_to:
        return f"{time_from} - {time_to}"
    if time_from:
        return time_from
    if time_to:
        return time_to
    return ""


def _write_header_block(ws: Worksheet, title_line1: str, subtitle: str) -> None:
    """Schreibt Titel und Spaltenkoepfe (2 Header-Zeilen)."""
    ws["A1"] = title_line1
    ws["A1"].font = Font(bold=True, size=14)
    ws.merge_cells("A1:D1")

    if subtitle:
        ws["E1"] = subtitle
        ws["E1"].font = Font(italic=True)
        ws.merge_cells("E1:I1")

    # Header-Zeile 1 (Gruppenkoepfe)
    ws["A4"] = "Datum"
    ws["B4"] = "Fahrzeit"
    ws["C4"] = "Route"
    ws["D4"] = "Reisezweck"
    ws["E4"] = "Kilometerstand"
    ws["G4"] = "Gefahrene Kilometer"
    ws.merge_cells("E4:F4")
    ws.merge_cells("G4:I4")

    # Header-Zeile 2 (Sub-Koepfe)
    ws["B5"] = "von - bis"
    ws["C5"] = "Ziel"
    ws["E5"] = "Anfang"
    ws["F5"] = "Ende"
    ws["G5"] = "gesch."
    ws["H5"] = "Wohng/Arbeit"
    ws["I5"] = "Privat"

    for row in (4, 5):
        for col in "ABCDEFGHI":
            cell = ws[f"{col}{row}"]
            cell.fill = _HEADER_FILL
            cell.border = _BORDER
            cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
            if row == 4:
                cell.font = Font(bold=True)

    ws.row_dimensions[4].height = 18
    ws.row_dimensions[5].height = 18


def _write_trip_row(ws: Worksheet, row: int, trip: Trip) -> None:
    """Schreibt eine einzelne Fahrt-Zeile."""
    date_obj = _iso_to_date(trip.date)
    if date_obj is not None:
        ws.cell(row=row, column=1, value=date_obj).number_format = "DD.MM.YYYY"
    else:
        ws.cell(row=row, column=1, value=trip.date)

    ws.cell(row=row, column=2, value=_format_time_range(trip.time_from, trip.time_to))
    ws.cell(row=row, column=3, value=trip.destination)
    ws.cell(row=row, column=4, value=trip.purpose)

    if trip.km_start:
        ws.cell(row=row, column=5, value=trip.km_start)
    if trip.km_end:
        ws.cell(row=row, column=6, value=trip.km_end)
    if trip.km_business:
        ws.cell(row=row, column=7, value=trip.km_business)
    # Spalte H (Wohng/Arbeit) bleibt leer — nicht im aktuellen Modell
    if trip.km_private:
        ws.cell(row=row, column=9, value=trip.km_private)

    # Zellen-Styling: Borders + Wrap fuer Ziel/Zweck
    for col in range(1, 10):
        cell = ws.cell(row=row, column=col)
        cell.border = _BORDER
        if col in (3, 4):
            cell.alignment = Alignment(wrap_text=True, vertical="top")
        else:
            cell.alignment = Alignment(vertical="top")


def _write_total_row(
    ws: Worksheet,
    row: int,
    label: str,
    km_business: int,
    km_private: int,
) -> None:
    """Schreibt eine Summenzeile."""
    cell_label = ws.cell(row=row, column=4, value=label)
    cell_label.font = Font(bold=True)
    cell_label.alignment = Alignment(horizontal="right")

    ws.cell(row=row, column=7, value=km_business).font = Font(bold=True)
    ws.cell(row=row, column=9, value=km_private).font = Font(bold=True)

    for col in range(1, 10):
        cell = ws.cell(row=row, column=col)
        cell.fill = _TOTAL_FILL
        cell.border = _BORDER


def _apply_column_widths(ws: Worksheet) -> None:
    """Setzt Spaltenbreiten gemaess Vorlage."""
    for col_letter, width in _COLUMN_WIDTHS.items():
        ws.column_dimensions[col_letter].width = width


def export_trips(
    trips: list[Trip],
    out_path: Path,
    title_line1: str,
    subtitle: str,
    group_by_month: bool = False,
) -> None:
    """Schreibt eine Trip-Liste als Excel-Datei.

    trips: Liste der zu exportierenden Fahrten (sortiert nach Datum)
    out_path: Zielpfad der .xlsx-Datei
    title_line1: Haupttitel (z.B. 'Fahrtenbuch Audi A5 Cabrio (B-TT 1)')
    subtitle: Untertitel (z.B. 'Mai 2024' oder '2024 — 1.500 km/Monat Leasing')
    group_by_month: bei True werden Monats-Zwischensummen eingefuegt (Jahresexport)
    """
    wb = Workbook()
    ws = wb.active
    if ws is None:
        ws = wb.create_sheet("Fahrtenbuch")
    else:
        ws.title = "Fahrtenbuch"

    _apply_column_widths(ws)
    _write_header_block(ws, title_line1, subtitle)
    ws.freeze_panes = "A6"

    current_row = 6
    total_business = 0
    total_private = 0

    if group_by_month and trips:
        # Nach Monat gruppieren und Zwischensummen einfuegen
        current_month: tuple[int, int] | None = None
        month_business = 0
        month_private = 0

        for trip in trips:
            date_obj = _iso_to_date(trip.date)
            trip_month = (date_obj.year, date_obj.month) if date_obj else (0, 0)

            if current_month is not None and trip_month != current_month:
                # Vorherigen Monat abschliessen
                _write_total_row(
                    ws,
                    current_row,
                    f"Summe {_month_label(current_month)}:",
                    month_business,
                    month_private,
                )
                current_row += 1
                month_business = 0
                month_private = 0

            current_month = trip_month
            _write_trip_row(ws, current_row, trip)
            month_business += trip.km_business
            month_private += trip.km_private
            total_business += trip.km_business
            total_private += trip.km_private
            current_row += 1

        # Letzter Monat
        if current_month is not None:
            _write_total_row(
                ws,
                current_row,
                f"Summe {_month_label(current_month)}:",
                month_business,
                month_private,
            )
            current_row += 1
    else:
        for trip in trips:
            _write_trip_row(ws, current_row, trip)
            total_business += trip.km_business
            total_private += trip.km_private
            current_row += 1

    # Gesamtsumme
    current_row += 1
    _write_total_row(ws, current_row, "Gesamt:", total_business, total_private)

    wb.save(out_path)


_MONTH_NAMES_DE = [
    "", "Januar", "Februar", "Maerz", "April", "Mai", "Juni",
    "Juli", "August", "September", "Oktober", "November", "Dezember",
]


def _month_label(year_month: tuple[int, int]) -> str:
    """Gibt 'Mai 2024' fuer (2024, 5) zurueck."""
    year, month = year_month
    if 1 <= month <= 12:
        return f"{_MONTH_NAMES_DE[month]} {year}"
    return f"{year}-{month:02d}"


def month_name_de(month: int) -> str:
    """Gibt den deutschen Monatsnamen zurueck."""
    if 1 <= month <= 12:
        return _MONTH_NAMES_DE[month]
    return f"{month:02d}"
