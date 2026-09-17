"""Arbeitskopie eines Fahrtenbuchs fuer die Web-Oberflaeche.

Die Web-Version bekommt eine eigene Kopie der `christo.db` unter
`<config_dir>/web/<name>/`. Die TUI und ihre Datei bleiben unberuehrt, gleichzeitiger Zugriff
ist damit ausgeschlossen (Entscheidung vom 17.09.2026, kein WAL-Umbau).

Belege werden nicht mitkopiert, die erste Web-Version zeigt sie nicht an.
"""

from __future__ import annotations

import contextlib
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from christo.models.settings import config_dir
from christo.services.database import Database

WEB_DIR_NAME = "web"
MARKER_FILE = "kopie-von.txt"


@dataclass(frozen=True)
class Workspace:
    """Eine Arbeitskopie.

    Attributes:
        path: Verzeichnis der Kopie (wird wie ein Fahrtenbuch geoeffnet).
        source: Das Original-Fahrtenbuch.
        copied_at: Zeitpunkt der Kopie.
    """

    path: Path
    source: Path
    copied_at: datetime


def workspace_root() -> Path:
    """Wurzel aller Arbeitskopien."""
    return config_dir() / WEB_DIR_NAME


def _vorhandene_db(source: Path) -> Path:
    """Die tatsaechlich vorhandene Datenbankdatei, auch unter einem alten Namen."""
    for name in (Database.DB_FILENAME, *Database.LEGACY_DB_FILENAMES):
        if (source / name).exists():
            return source / name
    raise FileNotFoundError(f"Keine Datenbank unter {source}")


def _backup_copy(source_db: Path, target_db: Path) -> None:
    # SQLite-Backup statt Dateikopie: liefert einen konsistenten Stand, auch wenn die TUI
    # gerade schreibt oder ein Journal offen ist
    target_db.parent.mkdir(parents=True, exist_ok=True)
    tmp = target_db.with_suffix(".db.tmp")
    tmp.unlink(missing_ok=True)
    # as_uri() maskiert Leerzeichen und Laufwerksbuchstaben korrekt
    quelle = sqlite3.connect(f"{source_db.resolve().as_uri()}?mode=ro", uri=True)
    try:
        ziel = sqlite3.connect(tmp)
        try:
            quelle.backup(ziel)
        finally:
            ziel.close()
    finally:
        quelle.close()
    tmp.replace(target_db)


def prepare(source: Path, refresh: bool = False) -> Workspace:
    """Legt die Arbeitskopie an oder nimmt die vorhandene.

    Args:
        source: Verzeichnis des Original-Fahrtenbuchs (mit christo.db).
        refresh: Vorhandene Kopie verwerfen und neu kopieren. Aenderungen in der Web-Version
            gehen dabei verloren.

    Returns:
        Die Arbeitskopie.

    Raises:
        FileNotFoundError: Wenn am Pfad kein Fahrtenbuch liegt.
    """
    source = source.resolve()
    if not Database.has_logbook(source):
        raise FileNotFoundError(f"Kein Fahrtenbuch unter {source}")
    source_db = _vorhandene_db(source)

    ziel = workspace_root() / source.name
    ziel_db = ziel / Database.DB_FILENAME
    marker = ziel / MARKER_FILE

    if refresh or not ziel_db.exists():
        _backup_copy(source_db, ziel_db)
        jetzt = datetime.now().replace(microsecond=0)
        marker.write_text(f"{source}\n{jetzt.isoformat()}\n", encoding="utf-8", newline="\n")
        return Workspace(path=ziel, source=source, copied_at=jetzt)

    zeitpunkt = datetime.fromtimestamp(ziel_db.stat().st_mtime).replace(microsecond=0)
    if marker.exists():
        zeilen = marker.read_text(encoding="utf-8").splitlines()
        if len(zeilen) >= 2:
            with contextlib.suppress(ValueError):
                zeitpunkt = datetime.fromisoformat(zeilen[1])
    return Workspace(path=ziel, source=source, copied_at=zeitpunkt)
