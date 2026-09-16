"""Tests für die Übernahme alter Namen (fahrtenbuch -> death-proof -> christo).

Wer das Programm nach der Umbenennung startet, darf weder seine Einstellungen
noch sein Fahrtenbuch verlieren.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from christo.models.settings import CONFIG_DIR_NAME, migrate_legacy_dir
from christo.services.database import Database


class TestConfigDirMigration:
    @pytest.mark.parametrize("old_name", [".death-proof", ".fahrtenbuch"])
    def test_old_dir_is_renamed(self, tmp_path: Path, old_name: str) -> None:
        old = tmp_path / old_name
        old.mkdir()
        (old / "config.json").write_text('{"language": "en"}', encoding="utf-8", newline="\n")

        assert migrate_legacy_dir(tmp_path) == old

        new = tmp_path / CONFIG_DIR_NAME
        assert not old.exists()
        assert (new / "config.json").read_text(encoding="utf-8") == '{"language": "en"}'

    def test_youngest_old_dir_wins(self, tmp_path: Path) -> None:
        (tmp_path / ".death-proof").mkdir()
        (tmp_path / ".fahrtenbuch").mkdir()

        assert migrate_legacy_dir(tmp_path) == tmp_path / ".death-proof"
        assert (tmp_path / ".fahrtenbuch").exists()

    def test_existing_new_dir_is_never_overwritten(self, tmp_path: Path) -> None:
        (tmp_path / CONFIG_DIR_NAME).mkdir()
        (tmp_path / ".death-proof").mkdir()

        assert migrate_legacy_dir(tmp_path) is None
        assert (tmp_path / ".death-proof").exists()

    def test_nothing_to_migrate(self, tmp_path: Path) -> None:
        assert migrate_legacy_dir(tmp_path) is None
        assert not (tmp_path / CONFIG_DIR_NAME).exists()


def _write_marker_db(path: Path, marker: str) -> None:
    connection = sqlite3.connect(str(path))
    try:
        connection.execute("CREATE TABLE marker (value TEXT)")
        connection.execute("INSERT INTO marker VALUES (?)", (marker,))
        connection.commit()
    finally:
        connection.close()


def _read_marker(path: Path) -> str:
    connection = sqlite3.connect(str(path))
    try:
        return str(connection.execute("SELECT value FROM marker").fetchone()[0])
    finally:
        connection.close()


class TestDatabaseMigration:
    @pytest.mark.parametrize("old_name", ["death-proof.db", "fahrtenbuch.db"])
    def test_old_db_is_recognised_and_renamed(self, tmp_path: Path, old_name: str) -> None:
        _write_marker_db(tmp_path / old_name, old_name)
        assert Database.has_logbook(tmp_path)

        database = Database(tmp_path)
        database.open()
        database.close()

        assert not (tmp_path / old_name).exists()
        assert _read_marker(tmp_path / Database.DB_FILENAME) == old_name

    def test_youngest_old_db_wins(self, tmp_path: Path) -> None:
        _write_marker_db(tmp_path / "death-proof.db", "death-proof")
        _write_marker_db(tmp_path / "fahrtenbuch.db", "fahrtenbuch")

        database = Database(tmp_path)
        database.open()
        database.close()

        assert _read_marker(tmp_path / Database.DB_FILENAME) == "death-proof"
        assert (tmp_path / "fahrtenbuch.db").exists()

    def test_existing_new_db_is_never_replaced(self, tmp_path: Path) -> None:
        _write_marker_db(tmp_path / Database.DB_FILENAME, "neu")
        _write_marker_db(tmp_path / "death-proof.db", "alt")

        database = Database(tmp_path)
        database.open()
        database.close()

        assert _read_marker(tmp_path / Database.DB_FILENAME) == "neu"
        assert (tmp_path / "death-proof.db").exists()

    def test_locked_old_db_is_opened_under_old_name(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        # Nachgestellt: eine noch laufende alte Instanz haelt death-proof.db offen,
        # Windows meldet beim Umbenennen WinError 32.
        _write_marker_db(tmp_path / "death-proof.db", "alt")

        def locked(self: Path, target: Path) -> Path:
            raise PermissionError(32, "Datei wird von einem anderen Prozess verwendet")

        monkeypatch.setattr(Path, "rename", locked)

        database = Database(tmp_path)
        database.open()
        database.close()

        assert database.db_file == tmp_path / "death-proof.db"
        assert not (tmp_path / Database.DB_FILENAME).exists()
        assert _read_marker(tmp_path / "death-proof.db") == "alt"

    def test_empty_dir_is_no_logbook(self, tmp_path: Path) -> None:
        assert not Database.has_logbook(tmp_path)
