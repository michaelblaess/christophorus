"""Tests der Exportformate: Formatmodell, Markdown, JSON und die Weiche."""

from __future__ import annotations

import json
from collections.abc import Iterator
from dataclasses import fields
from datetime import datetime
from pathlib import Path

import pytest
from openpyxl import load_workbook

from christo.models.export_format import (
    EXCEL,
    EXPORT_FORMATS,
    JSON,
    MARKDOWN,
    format_for_key,
    format_for_path,
    format_for_suffix,
    suggested_name,
    swap_suffix,
)
from christo.models.export_job import ExportJob
from christo.models.trip import (
    Trip,
    get_business_categories,
    get_informational_categories,
    set_business_categories,
    set_informational_categories,
)
from christo.services.exporters import write_export
from christo.services.json_export import SCHEMA, build_json
from christo.services.markdown_export import render_markdown


@pytest.fixture(autouse=True)
def _feste_kategorien() -> Iterator[None]:
    """Die Kategorien sind Modulzustand - fuer diese Tests fest und danach zurueck."""
    vorher_business = get_business_categories()
    vorher_info = get_informational_categories()
    set_business_categories({"business", "fuel", "service"})
    set_informational_categories({"delivery", "return"})
    yield
    set_business_categories(vorher_business)
    set_informational_categories(vorher_info)


def beispiel_monat() -> ExportJob:
    """Ein Monat mit geschaeftlicher Fahrt, Anlieferung und privatem Sammeleintrag."""
    return ExportJob(
        trips=[
            Trip(
                id=1,
                date="2024-05-02",
                time_from="08:00",
                time_to="09:00",
                destination="Kunde | Nord",
                purpose="Abstimmung Projekt",
                km_start=10000,
                km_end=10050,
                km_business=50,
                category="business",
            ),
            Trip(id=2, date="2024-05-03", category="delivery"),
            Trip(
                id=3,
                date="2024-05-04",
                purpose="Privatfahrten gesammelt",
                km_start=10050,
                km_end=11250,
                km_private=1200,
                category="private",
            ),
        ],
        title="Fahrtenbuch Testwagen (B-TT 1)",
        subtitle="Mai 2024 — 1.500 km / Monat Leasing",
        year=2024,
        month=5,
        category_labels={"delivery": "Anlieferung"},
        vehicle_name="Testwagen",
        vehicle_plate="B-TT 1",
    )


def beispiel_jahr() -> ExportJob:
    """Zwei Monate mit je einer Fahrt, gruppiert."""
    return ExportJob(
        trips=[
            Trip(date="2024-05-02", purpose="Mai", km_start=100, km_business=10, category="business"),
            Trip(date="2024-06-03", purpose="Juni", km_start=110, km_private=5, category="private", destination="X"),
        ],
        title="Fahrtenbuch",
        subtitle="2024",
        year=2024,
        group_by_month=True,
    )


# --- Formatmodell ---------------------------------------------------------------


def test_reihenfolge_im_dialog() -> None:
    assert EXPORT_FORMATS == (EXCEL, JSON, MARKDOWN)


@pytest.mark.parametrize(("eingabe", "erwartet"), [(".xlsx", EXCEL), ("XLSX", EXCEL), ("md", MARKDOWN), (".pdf", None)])
def test_format_zur_endung(eingabe: str, erwartet: object) -> None:
    assert format_for_suffix(eingabe) == erwartet


def test_format_zu_pfad_und_kennung() -> None:
    assert format_for_path(Path("a/b/Fahrtenbuch.JSON")) == JSON
    assert format_for_key(" Markdown ") == MARKDOWN
    assert format_for_key("pdf") is None


@pytest.mark.parametrize(
    ("name", "ziel", "erwartet"),
    [
        ("Fahrtenbuch 2024-05.xlsx", MARKDOWN, "Fahrtenbuch 2024-05.md"),
        ("Fahrtenbuch 2024-05.md", MARKDOWN, "Fahrtenbuch 2024-05.md"),
        ("Fahrtenbuch v1.2", JSON, "Fahrtenbuch v1.2.json"),
        ("", EXCEL, ""),
    ],
)
def test_endung_tauschen(name: str, ziel: object, erwartet: str) -> None:
    assert swap_suffix(name, ziel) == erwartet  # type: ignore[arg-type]


def test_vorgeschlagener_name_traegt_zeitstempel_und_endung() -> None:
    fest = datetime(2026, 9, 14, 10, 15, 30)
    assert suggested_name(JSON, "Fahrtenbuch 2024-05", now=fest) == "Fahrtenbuch 2024-05 20260914-101530.json"


# --- Markdown -------------------------------------------------------------------


def test_markdown_monat_zeilen_wie_im_excel() -> None:
    zeilen = render_markdown(beispiel_monat()).splitlines()
    assert zeilen[0] == "# Fahrtenbuch Testwagen (B-TT 1)"
    assert "| 02.05.2024 | 08:00 - 09:00 | Kunde \\| Nord | Abstimmung Projekt | 10.000 | 10.050 | 50 |  |" in zeilen
    assert "| 03.05.2024 |  | *Anlieferung* |  |  |  |  |  |" in zeilen
    # Privater Sammeleintrag ohne Zeit und Ziel: ohne Datum, Kette laeuft weiter.
    assert "|  |  |  | Privatfahrten gesammelt | 10.050 | 11.250 |  | 1.200 |" in zeilen
    assert zeilen[-1] == "|  |  |  | **Gesamt** |  | **11.250** | **50** | **1.200** |"


def test_markdown_jahr_mit_monatssummen() -> None:
    zeilen = render_markdown(beispiel_jahr()).splitlines()
    assert "|  |  |  | **Summe Mai 2024** |  | **110** | **10** | **0** |" in zeilen
    assert "|  |  |  | **Summe Juni 2024** |  | **115** | **0** | **5** |" in zeilen
    assert zeilen.index("|  |  |  | **Summe Mai 2024** |  | **110** | **10** | **0** |") < zeilen.index(
        "|  |  |  | **Summe Juni 2024** |  | **115** | **0** | **5** |"
    )
    assert zeilen[-1] == "|  |  |  | **Gesamt** |  | **115** | **10** | **5** |"


def test_markdown_datei_hat_lf_und_endet_mit_umbruch(tmp_path: Path) -> None:
    ziel = tmp_path / "f.md"
    write_export(MARKDOWN, beispiel_monat(), ziel)
    rohdaten = ziel.read_bytes()
    assert b"\r" not in rohdaten
    assert rohdaten.endswith(b"|\n")


# --- JSON -----------------------------------------------------------------------


def test_json_ist_verlustfrei() -> None:
    daten = build_json(beispiel_monat())
    assert daten["schema"] == SCHEMA
    feldnamen = {f.name for f in fields(Trip)}
    for eintrag in daten["trips"]:
        assert feldnamen <= set(eintrag), feldnamen - set(eintrag)
    assert daten["trips"][0]["destination"] == "Kunde | Nord"
    assert daten["trips"][1]["category_label"] == "Anlieferung"
    assert daten["vehicle"] == {"name": "Testwagen", "plate": "B-TT 1"}
    assert daten["period"] == {"year": 2024, "month": 5}


def test_json_zusammenfassung() -> None:
    assert build_json(beispiel_monat())["summary"] == {
        "trips": 3,
        "km_business": 50,
        "km_private": 1200,
        "km_total": 1250,
    }


def test_json_datei_behaelt_umlaute_und_hat_lf(tmp_path: Path) -> None:
    job = beispiel_monat()
    ziel = tmp_path / "f.json"
    write_export(JSON, job, ziel)
    rohdaten = ziel.read_bytes()
    assert b"\r" not in rohdaten
    assert "Mai 2024 — 1.500".encode() in rohdaten
    assert json.loads(rohdaten.decode("utf-8"))["title"] == job.title


# --- Die Weiche -----------------------------------------------------------------


def test_excel_ueber_die_weiche(tmp_path: Path) -> None:
    ziel = tmp_path / "f.xlsx"
    write_export(EXCEL, beispiel_monat(), ziel)
    blatt = load_workbook(ziel)["Fahrtenbuch"]
    assert blatt["A1"].value == "Fahrtenbuch Testwagen (B-TT 1)"


def test_unbekanntes_format_wird_abgelehnt(tmp_path: Path) -> None:
    from christo.models.export_format import ExportFormat

    with pytest.raises(ValueError, match="pdf"):
        write_export(ExportFormat("pdf", ".pdf", "x", "y"), beispiel_monat(), tmp_path / "f.pdf")
