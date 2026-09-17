"""Die Web-Oberflaeche arbeitet auf einer Kopie, nie auf der Datei der TUI."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from christo.models.vehicle import Vehicle
from christo.services.database import Database
from christo.services.fahrtenbuch import Fahrtenbuch
from christo.web.workspace import prepare, workspace_root
from tests.conftest import make_trip


def _pruefsumme(datei: Path) -> str:
    return hashlib.sha256(datei.read_bytes()).hexdigest()


@pytest.fixture
def quelle(tmp_path: Path, vehicle: Vehicle) -> Path:
    pfad = tmp_path / "Kompaktkombi"
    pfad.mkdir()
    fb = Fahrtenbuch.create(pfad, vehicle)
    fb.database.add_trip(make_trip("2024-05-02", 50, destination="Kunde Nord"))
    fb.close()
    return pfad


def test_copy_lands_in_the_config_dir(quelle: Path) -> None:
    kopie = prepare(quelle)
    assert kopie.path == workspace_root() / quelle.name
    assert (kopie.path / Database.DB_FILENAME).exists()
    assert kopie.source == quelle.resolve()


def test_source_is_not_touched_by_web_changes(quelle: Path) -> None:
    quelle_db = quelle / Database.DB_FILENAME
    vorher = _pruefsumme(quelle_db)
    kopie = prepare(quelle)

    db = Database(kopie.path)
    db.open()
    db.add_trip(make_trip("2024-05-09", 20, destination="Nur im Web"))
    db.close()

    assert _pruefsumme(quelle_db) == vorher
    original = Database(quelle)
    original.open()
    ziele = [t.destination for t in original.get_trips_for_month(2024, 5)]
    original.close()
    assert ziele == ["Kunde Nord"]


def test_second_start_keeps_the_existing_copy(quelle: Path) -> None:
    erste = prepare(quelle)
    db = Database(erste.path)
    db.open()
    db.add_trip(make_trip("2024-05-09", 20, destination="Nur im Web"))
    db.close()

    zweite = prepare(quelle)
    db = Database(zweite.path)
    db.open()
    ziele = [t.destination for t in db.get_trips_for_month(2024, 5)]
    db.close()
    assert "Nur im Web" in ziele
    assert zweite.copied_at == erste.copied_at


def test_refresh_replaces_the_copy(quelle: Path) -> None:
    prepare(quelle)
    db = Database(prepare(quelle).path)
    db.open()
    db.add_trip(make_trip("2024-05-09", 20, destination="Nur im Web"))
    db.close()

    neu = prepare(quelle, refresh=True)
    db = Database(neu.path)
    db.open()
    ziele = [t.destination for t in db.get_trips_for_month(2024, 5)]
    db.close()
    assert "Nur im Web" not in ziele


def test_missing_logbook_is_an_error(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        prepare(tmp_path / "gibt-es-nicht")
