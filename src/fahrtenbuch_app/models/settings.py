"""Globale Konfiguration und Adress-Modell fuer das Fahrtenbuch."""

import json
from dataclasses import dataclass, field
from pathlib import Path


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
    """Globale Konfiguration — wird als JSON in ~/.fahrtenbuch/config.json gespeichert.

    Enthaelt nur anwendungsweite Einstellungen, keine Fahrtenbuch-spezifischen Daten.
    """

    theme: str = "textual-dark"
    last_opened_path: str = ""
    recent_paths: list[str] = field(default_factory=list)
    log_visible: bool = True

    CONFIG_DIR: Path = Path.home() / ".fahrtenbuch"
    CONFIG_FILE: Path = CONFIG_DIR / "config.json"

    MAX_RECENT: int = 10

    def add_recent(self, path: str) -> None:
        """Fuegt einen Pfad zur Liste der zuletzt geoeffneten Fahrtenbuecher hinzu."""
        if path in self.recent_paths:
            self.recent_paths.remove(path)
        self.recent_paths.insert(0, path)
        if len(self.recent_paths) > self.MAX_RECENT:
            self.recent_paths = self.recent_paths[:self.MAX_RECENT]

    def save(self) -> None:
        """Speichert die globale Konfiguration als JSON."""
        self.CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        data = {
            "theme": self.theme,
            "last_opened_path": self.last_opened_path,
            "recent_paths": self.recent_paths,
            "log_visible": self.log_visible,
        }
        with open(self.CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    @staticmethod
    def load() -> "GlobalConfig":
        """Laedt die globale Konfiguration aus JSON oder erstellt Default."""
        config = GlobalConfig()
        if not config.CONFIG_FILE.exists():
            return config
        try:
            with open(config.CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            config.theme = data.get("theme", "textual-dark")
            config.last_opened_path = data.get("last_opened_path", "")
            config.recent_paths = data.get("recent_paths", [])
            config.log_visible = data.get("log_visible", True)
        except (json.JSONDecodeError, KeyError):
            pass
        return config
