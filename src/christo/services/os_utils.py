"""Hilfsfunktionen fuer Betriebssystem-Interaktion."""

import os
import platform
import subprocess
from pathlib import Path


def open_file_in_system(path: Path) -> None:
    """Oeffnet eine Datei im Standard-Programm des Betriebssystems."""
    if not path.exists():
        raise FileNotFoundError(str(path))
    system = platform.system()
    if system == "Windows":
        # startfile gibt es nur unter Windows - auf Linux/macOS braucht mypy das Ignore
        os.startfile(str(path))  # type: ignore[attr-defined, unused-ignore]
    elif system == "Darwin":
        subprocess.Popen(["open", str(path)])
    else:
        subprocess.Popen(["xdg-open", str(path)])
