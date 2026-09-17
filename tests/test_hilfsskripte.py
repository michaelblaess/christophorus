"""Die Skripte neben dem Paket: zeigen ihre Importe noch auf vorhandene Module?

`assets/make_screenshots.py` und `tools/sync_web_assets.py` liegen ausserhalb von `src/` und
werden von keinem anderen Gate ausgefuehrt. Beim Verschieben von `Fahrtenbuch` nach
`services/` blieb der Import im Screenshot-Skript deshalb stehen, ohne dass etwas rot wurde -
gemeldet hat es am Ende die CI, und auch nur als Sortierfehler von ruff.

Der Test importiert die Skripte nicht (sie starten eine Oberflaeche), sondern liest ihre
Importe aus dem Syntaxbaum und laesst sie von importlib aufloesen.
"""

from __future__ import annotations

import ast
import importlib.util
from pathlib import Path

import pytest

WURZEL = Path(__file__).resolve().parent.parent
SKRIPTE = sorted((WURZEL / "assets").glob("*.py")) + sorted((WURZEL / "tools").glob("*.py"))


def _christo_module(pfad: Path) -> list[str]:
    """Alle importierten `christo.*`-Module eines Skripts, aus dem Syntaxbaum gelesen."""
    baum = ast.parse(pfad.read_text(encoding="utf-8"))
    gefunden: list[str] = []
    for knoten in ast.walk(baum):
        if isinstance(knoten, ast.ImportFrom) and knoten.module and knoten.module.startswith("christo"):
            gefunden.append(knoten.module)
        elif isinstance(knoten, ast.Import):
            gefunden.extend(name.name for name in knoten.names if name.name.startswith("christo"))
    return gefunden


def test_some_script_actually_imports_the_core() -> None:
    """Sonst liefe die Pruefung unten leer, ohne dass es auffiele.

    Nicht jedes Skript muss den Kern verwenden - `sync_web_assets.py` kopiert nur Dateien.
    Mindestens eines muss es aber, sonst prueft der Test darunter nichts mehr.
    """
    assert SKRIPTE, "keine Skripte unter assets/ oder tools/ gefunden"
    assert any(_christo_module(s) for s in SKRIPTE), "kein Skript importiert aus christo"


@pytest.mark.parametrize("skript", SKRIPTE, ids=lambda p: str(p.relative_to(WURZEL)).replace("\\", "/"))
def test_script_imports_still_resolve(skript: Path) -> None:
    fehlend = [name for name in _christo_module(skript) if importlib.util.find_spec(name) is None]
    assert not fehlend, f"{skript.name} importiert nicht vorhandene Module: {', '.join(fehlend)}"
