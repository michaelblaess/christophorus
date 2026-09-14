"""Tests fuer den Speichern-Dialog des Exports.

Der Dialog ist die einzige Stelle, an der das Format gewaehlt wird, und er
gibt nur einen Pfad zurueck. Zwei Dinge muessen deshalb am laufenden Dialog
geprueft werden, nicht am Quelltext:

1. Der Filterwechsel zieht die Endung im Namensfeld nach.
2. Der zurueckgegebene Pfad traegt eine Endung, aus der sich das Format lesen
   laesst.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from textual.app import App, ComposeResult
from textual.pilot import Pilot
from textual.widgets import Input, Select

from death_proof.models.export_format import DEFAULT_FORMAT, format_for_key, format_for_path
from death_proof.screens.export_save_screen import ExportSaveScreen

_START_NAME = "Fahrtenbuch 2024-05 (Testwagen - B-TT 1) 20260914-101530.xlsx"


class _Host(App[None]):
    """Traegeranwendung, die nur den Dialog aufmacht."""

    def __init__(self, location: Path) -> None:
        super().__init__()
        self._location = location
        self.ergebnis: Path | None = None
        self.geschlossen = False

    def compose(self) -> ComposeResult:
        return iter(())

    def on_mount(self) -> None:
        self.push_screen(
            ExportSaveScreen(location=str(self._location), default_file=_START_NAME, start_format=DEFAULT_FORMAT),
            callback=self._merken,
        )

    def _merken(self, pfad: Path | None) -> None:
        self.ergebnis = pfad
        self.geschlossen = True


async def _filter_umschalten(pilot: Pilot[None], index: int) -> str:
    """Stellt das Auswahlfeld um und liefert den Namen, der danach dasteht."""
    dialog = pilot.app.screen
    auswahl: Select[Any] = dialog.query_one(Select)
    auswahl.value = index
    await pilot.pause()
    return str(dialog.query_one(Input).value)


async def _namen_setzen_und_speichern(pilot: Pilot[None], name: str) -> None:
    """Tippt einen Namen ins Namensfeld und bestaetigt mit Enter.

    Der Fokus muss vorher wirklich im Feld liegen - sonst laeuft das Enter in
    die Dateiliste und der Dialog bleibt offen.
    """
    feld = pilot.app.screen.query_one(Input)
    feld.value = name
    feld.focus()
    await pilot.pause()
    await pilot.press("enter")
    await pilot.pause()


async def test_filterwechsel_zieht_die_endung_nach(tmp_path: Path) -> None:
    app = _Host(tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        assert app.screen.query_one(Input).value == _START_NAME
        # Reihenfolge wie in EXPORT_FORMATS: 0 Excel, 1 JSON, 2 Markdown.
        assert await _filter_umschalten(pilot, 2) == _START_NAME.replace(".xlsx", ".md")
        assert await _filter_umschalten(pilot, 1) == _START_NAME.replace(".xlsx", ".json")
        assert await _filter_umschalten(pilot, 0) == _START_NAME


async def test_alle_dateien_laesst_den_namen_in_ruhe(tmp_path: Path) -> None:
    app = _Host(tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        await _filter_umschalten(pilot, 2)
        # Index 3 ist "Alle Dateien" - er sagt etwas ueber die Liste aus, nicht
        # darueber, was geschrieben werden soll.
        assert await _filter_umschalten(pilot, 3) == _START_NAME.replace(".xlsx", ".md")
        screen = app.screen
        assert isinstance(screen, ExportSaveScreen)
        assert screen.selected_format.key == "markdown"


async def test_getippter_name_ohne_endung_bekommt_die_des_formats(tmp_path: Path) -> None:
    app = _Host(tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        await _filter_umschalten(pilot, 1)
        await _namen_setzen_und_speichern(pilot, "Auswertung")

    assert app.ergebnis is not None
    assert app.ergebnis.name == "Auswertung.json"
    assert format_for_path(app.ergebnis) == format_for_key("json")


async def test_getippte_endung_schlaegt_das_auswahlfeld(tmp_path: Path) -> None:
    # Wer ".md" tippt, obwohl im Auswahlfeld Excel steht, bekommt Markdown.
    app = _Host(tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        await _namen_setzen_und_speichern(pilot, "Auswertung.md")

    assert app.ergebnis is not None
    assert app.ergebnis.name == "Auswertung.md"


async def test_abbrechen_liefert_keinen_pfad(tmp_path: Path) -> None:
    app = _Host(tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("escape")
        await pilot.pause()

    assert app.geschlossen
    assert app.ergebnis is None
