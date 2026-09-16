"""Globale Konfiguration und Adress-Modell fuer das Fahrtenbuch."""

import contextlib
import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# Biegt das Konfigurationsverzeichnis um. Gedacht fuer Tests (auch in
# Unterprozessen), damit sie nie die echte ~/.christo/config.json lesen
# oder das zuletzt geoeffnete Fahrtenbuch oeffnen.
HOME_ENV_VAR = "CHRISTO_HOME"


def config_dir() -> Path:
    """Liefert das Konfigurationsverzeichnis.

    Wird bei jedem Aufruf neu gelesen und nicht beim Import eingefroren - sonst
    liesse sich die Umgebungsvariable im Test nicht mehr umhaengen.
    """
    override = os.environ.get(HOME_ENV_VAR, "").strip()
    return Path(override) if override else Path.home() / CONFIG_DIR_NAME


CONFIG_DIR_NAME = ".christo"

# Fruehere Namen des Settings-Ordners, juengster zuerst: "Death Proof" hiess
# davor "fahrtenbuch". Beim Laden wird der erste gefundene uebernommen.
LEGACY_CONFIG_DIRS: tuple[str, ...] = (".death-proof", ".fahrtenbuch")


def migrate_legacy_dir(home: Path) -> Path | None:
    """Benennt den ersten vorhandenen alten Settings-Ordner unter home um.

    Liefert den uebernommenen alten Pfad oder None. Existiert der neue Ordner
    schon, bleibt alles unangetastet - sonst koennte ein alter Stand neuere
    Einstellungen ueberschreiben.
    """
    new = home / CONFIG_DIR_NAME
    if new.exists():
        return None
    for name in LEGACY_CONFIG_DIRS:
        legacy = home / name
        if legacy.exists():
            with contextlib.suppress(Exception):
                legacy.rename(new)
                return legacy
            return None
    return None


# textual-themes 0.5 hat 25 Themes umbenannt (trademark-safety pass).
# Config-Files aelterer Versionen koennen alte Slugs gespeichert haben —
# die werden beim Laden transparent gemappt.
_LEGACY_THEME_MAP: dict[str, str] = {
    "c64": "brotkasten",
    "amiga": "boing",
    "atari-st": "gemstone",
    "ibm-terminal": "classic-terminal",
    "nextstep": "next",
    "beos": "bebox",
    "ubuntu": "bunty",
    "macos": "cupertino",
    "windows-xp": "luna",
    "msdos": "commandr",
    "solaris-cde": "motif",
    "os2-warp": "warp",
    "opensuse": "geeko",
    "linux-mint": "minty",
    "red-hat": "crimson",
    "raspberry-pi": "razzy",
    "freebsd": "beastie",
    "tudor": "fifty-eight",
    "goldfinger": "goldfinder",
    "hulk": "hulkula",
    "batman": "flughund",
    "gameboy": "brick",
    "pan-am": "clipper",
    "miami-vice": "miami",
    "martini-racing": "racing",
    "superman": "metropolis",
    "spiderman": "spiderized",
    "gulf-racing": "textual-dark",  # entferntes Theme -> Textual Default
}


@dataclass
class AddressEntry:
    """Adresse mit Name und Entfernung.

    Wird sowohl fuer die Darstellung im Speicher als auch
    fuer den Import/Export aus der SQLite-DB verwendet.
    """

    id: int = 0
    category: str = ""
    name: str = ""
    address: str = ""
    km: float = 0.0


@dataclass
class GlobalConfig:
    """Globale Konfiguration — wird als JSON in ~/.christo/config.json gespeichert.

    Enthaelt nur anwendungsweite Einstellungen, keine Fahrtenbuch-spezifischen Daten.
    """

    theme: str = "textual-dark"
    last_opened_path: str = ""
    recent_paths: list[str] = field(default_factory=list)
    log_visible: bool = True
    last_base_dir: str = ""
    language: str = "de"
    # Tastenbelegung: "" = nach Betriebssystem, "classic" oder "function_keys".
    keymap_style: str = ""
    keymap_vim: bool = False
    # Eigene Belegungen je Aktion, z.B. {"toggle_log": ["alt+l"]}. Geprueft
    # wird erst in textual_widgets.keymap.parse_overrides - Fehler landen im Log.
    keymap_custom: dict[str, Any] = field(default_factory=dict)
    # Zuletzt benutztes Exportverzeichnis, Startpunkt des Speichern-Dialogs.
    last_export_dir: str = ""

    # default_factory statt festem Wert: ein Default wird beim Import in das
    # erzeugte __init__ eingebacken und liesse sich danach nicht mehr umbiegen.
    CONFIG_DIR: Path = field(default_factory=config_dir)
    CONFIG_FILE: Path = field(default_factory=lambda: config_dir() / "config.json")

    MAX_RECENT: int = 10

    def add_recent(self, path: str) -> None:
        """Fuegt einen Pfad zur Liste der zuletzt geoeffneten Fahrtenbuecher hinzu."""
        if path in self.recent_paths:
            self.recent_paths.remove(path)
        self.recent_paths.insert(0, path)
        if len(self.recent_paths) > self.MAX_RECENT:
            self.recent_paths = self.recent_paths[: self.MAX_RECENT]

    def save(self) -> None:
        """Speichert die globale Konfiguration als JSON."""
        self.CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        data = {
            "theme": self.theme,
            "last_opened_path": self.last_opened_path,
            "recent_paths": self.recent_paths,
            "log_visible": self.log_visible,
            "last_base_dir": self.last_base_dir,
            "language": self.language,
            "keymap_style": self.keymap_style,
            "keymap_vim": self.keymap_vim,
            "keymap_custom": self.keymap_custom,
            "last_export_dir": self.last_export_dir,
        }
        with open(self.CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    @staticmethod
    def _migrate_legacy_dir() -> None:
        """Benennt einen alten Settings-Ordner einmalig auf ~/.christo um.

        Gesucht wird in LEGACY_CONFIG_DIRS, der juengste Name zuerst. Migriert
        nur, wenn der neue Ordner noch nicht existiert. Schlaegt die
        Umbenennung fehl (z.B. Rechte), wird der Fehler verschluckt — die App
        startet dann mit Default-Settings.

        Bei umgebogenem Verzeichnis (Tests) wird nichts migriert - sonst
        wuerde ein Testlauf den echten Heimatordner anfassen.
        """
        if os.environ.get(HOME_ENV_VAR, "").strip():
            return
        migrate_legacy_dir(Path.home())

    @staticmethod
    def load() -> "GlobalConfig":
        """Laedt die globale Konfiguration aus JSON oder erstellt Default.

        Migriert dabei den alten Settings-Ordner (~/.fahrtenbuch) sowie alte
        Theme-Slugs aus textual-themes < 0.5 auf ihre aktuellen Namen und
        persistiert die Migration.
        """
        GlobalConfig._migrate_legacy_dir()
        config = GlobalConfig()
        if not config.CONFIG_FILE.exists():
            return config
        try:
            with open(config.CONFIG_FILE, encoding="utf-8") as f:
                data = json.load(f)
            config.theme = data.get("theme", "textual-dark")
            config.last_opened_path = data.get("last_opened_path", "")
            config.recent_paths = data.get("recent_paths", [])
            config.log_visible = data.get("log_visible", True)
            config.last_base_dir = data.get("last_base_dir", "")
            config.language = data.get("language", "de")
            config.keymap_style = str(data.get("keymap_style", "") or "")
            config.keymap_vim = bool(data.get("keymap_vim", False))
            raw_custom = data.get("keymap_custom")
            config.keymap_custom = raw_custom if isinstance(raw_custom, dict) else {}
            config.last_export_dir = str(data.get("last_export_dir", "") or "")
        except (json.JSONDecodeError, KeyError):
            pass

        # Legacy-Theme-Slug migrieren
        if config.theme in _LEGACY_THEME_MAP:
            config.theme = _LEGACY_THEME_MAP[config.theme]
            with contextlib.suppress(Exception):
                config.save()

        return config
