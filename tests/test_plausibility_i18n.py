"""Die Meldungen der Plausibilitätsprüfung gibt es auf Deutsch und Englisch.

Bis 16.09.2026 standen sie fest auf Deutsch im Code - bei englischer Oberfläche
war die Prüfung der einzige deutsche Rest.
"""

from __future__ import annotations

import json
import re
import string
from collections.abc import Iterator
from pathlib import Path

import pytest

from christo.i18n import load_locale
from christo.models.vehicle import Vehicle
from christo.services.database import Database
from christo.services.plausibility import run_all_checks
from tests.conftest import make_trip

_LOCALE = Path(__file__).resolve().parent.parent / "src" / "christo" / "locale"


def _pakete() -> tuple[dict[str, str], dict[str, str]]:
    de = json.loads((_LOCALE / "de.json").read_text(encoding="utf-8"))
    en = json.loads((_LOCALE / "en.json").read_text(encoding="utf-8"))
    return de, en


def _platzhalter(text: str) -> set[str]:
    return {name for _, name, _, _ in string.Formatter().parse(text) if name}


def test_plausi_schluessel_haben_in_beiden_sprachen_dieselben_platzhalter() -> None:
    de, en = _pakete()
    schluessel = [k for k in de if k.startswith("plausi.")]
    assert len(schluessel) >= 25
    abweichend = {
        k: (_platzhalter(de[k]), _platzhalter(en[k])) for k in schluessel if _platzhalter(de[k]) != _platzhalter(en[k])
    }
    assert not abweichend


@pytest.fixture
def english() -> Iterator[None]:
    load_locale("en")
    yield
    load_locale("de")


def test_pruefung_auf_englisch_liefert_keine_deutschen_reste(english: None, tmp_path: Path, vehicle: Vehicle) -> None:
    db = Database(tmp_path)
    db.open()
    try:
        db.save_vehicle(vehicle)
        # Samstag, Rueckwaertssprung und Endstand nicht erreicht - drei verschiedene Meldungen.
        db.add_trip(make_trip("2024-05-04", 50, purpose="Kunde"))
        db.add_trip(make_trip("2024-05-06", 30))
        report = run_all_checks(db)
    finally:
        db.close()

    meldungen = [issue.message for issue in report.issues]
    assert len(meldungen) >= 2
    deutsch = re.compile(r"[äöüß]|\b(Fahrt|Fahrten|bei|aber|erwartet|geschäftlich)\b")
    for meldung in meldungen:
        assert "plausi." not in meldung, meldung
        assert "{" not in meldung, meldung
        assert not deutsch.search(meldung), meldung
    assert any("Saturday" in m for m in meldungen)
