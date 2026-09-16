"""Anzeigenamen der Standardkategorien folgen der Sprache.

Bis 16.09.2026 standen sie deutsch mit Ersatzschreibung in der Datenbank, im
englischen Dialog "Neue Fahrt" hieß die Kategorie deshalb "Geschaeftlich".
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from christo.i18n import load_locale
from christo.services.database import Database, category_label, display_name_to_store


@pytest.fixture
def english() -> Iterator[None]:
    load_locale("en")
    yield
    load_locale("de")


def _optionen(pfad: Path) -> dict[str, str]:
    db = Database(pfad)
    db.open()
    try:
        return {name: label for label, name in db.get_category_options()}
    finally:
        db.close()


def test_neue_datenbank_zeigt_englische_namen(english: None, tmp_path: Path) -> None:
    optionen = _optionen(tmp_path)
    assert optionen["business"] == "Business"
    assert optionen["fuel_private"] == "Refuelling after private trip"
    assert optionen["delivery"] == "Delivery"


def test_neue_datenbank_zeigt_deutsche_namen_mit_umlauten(tmp_path: Path) -> None:
    optionen = _optionen(tmp_path)
    assert optionen["business"] == "Geschäftlich"
    assert optionen["return"] == "Rückgabe / Abholung"


def test_alte_ersatzschreibung_wird_uebersetzt(english: None, tmp_path: Path) -> None:
    # So sieht eine Datenbank aus, die vor der Umstellung angelegt wurde.
    db = Database(tmp_path)
    db.open()
    conn = db._get_conn()
    conn.execute("UPDATE categories SET display_name = 'Geschaeftlich' WHERE name = 'business'")
    conn.commit()
    db.close()

    assert _optionen(tmp_path)["business"] == "Business"


def test_selbst_umbenannte_kategorie_bleibt(english: None, tmp_path: Path) -> None:
    db = Database(tmp_path)
    db.open()
    conn = db._get_conn()
    conn.execute("UPDATE categories SET display_name = 'Firmenfahrt' WHERE name = 'business'")
    conn.commit()
    db.close()

    assert _optionen(tmp_path)["business"] == "Firmenfahrt"


def test_eigene_kategorie_bleibt_unberuehrt() -> None:
    assert category_label("pferdehof", "Pferdehof") == "Pferdehof"


def test_speichern_ohne_aenderung_behaelt_den_gespeicherten_wert(english: None) -> None:
    # Das Feld zeigte "Business" - unverändert gespeichert bleibt der alte Wert
    # stehen, sonst wäre die Kategorie ab dann fest englisch.
    assert display_name_to_store("business", "Geschäftlich", "Business") == "Geschäftlich"


def test_speichern_mit_aenderung_uebernimmt_die_eingabe(english: None) -> None:
    assert display_name_to_store("business", "Geschäftlich", "Company trip") == "Company trip"
