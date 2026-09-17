"""Tastenbelegung, Export-Dialog und Einstellungen an der echten App.

Die Einzelteile sind in test_keymap, test_export_formats und
test_export_save_screen geprueft. Hier geht es darum, ob sie in der laufenden
Anwendung ankommen - genau das faellt sonst erst beim Anwender auf.

Die Konfiguration liegt dank conftest in einem Wegwerf-Verzeichnis, das echte
Fahrtenbuch wird also nie geoeffnet.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from textual.widgets import Checkbox, Input, Select

from christo.app import FahrtenbuchApp
from christo.models.settings import GlobalConfig
from christo.models.vehicle import Vehicle
from christo.screens.export_save_screen import ExportSaveScreen
from christo.screens.keymap_screen import KeymapScreen
from christo.services.fahrtenbuch import Fahrtenbuch
from tests.conftest import make_trip


async def _settle(pilot: Any) -> None:
    """Laesst die App zur Ruhe kommen, bevor gemessen wird."""
    await pilot.pause()
    await pilot.pause()


def _stil_festlegen(stil: str) -> None:
    """Schreibt den Tastenstil VOR dem Bau der App in die isolierte Konfiguration.

    Ohne das haengt der Test an der Vorgabe der Plattform und prueft auf einem
    Mac etwas anderes als unter Windows.
    """
    config = GlobalConfig.load()
    config.keymap_style = stil
    config.save()


def _gebundene_tasten(app: FahrtenbuchApp) -> dict[str, str]:
    """Liest, welche Taste welche Aktion ausloest."""
    return {key: binding.action for key, bindings in app._bindings.key_to_bindings.items() for binding in bindings}


@pytest.fixture
def fahrtenbuch(tmp_path: Path, vehicle: Vehicle) -> Path:
    """Ein Fahrtenbuch mit zwei Fahrten im Mai 2024, als zuletzt geoeffnet eingetragen."""
    pfad = tmp_path / "fahrtenbuch"
    pfad.mkdir()
    fb = Fahrtenbuch.create(pfad, vehicle)
    fb.database.add_trip(make_trip("2024-05-02", 50, destination="Kunde Nord"))
    fb.database.add_trip(make_trip("2024-05-03", 20, business=False, destination="Markt"))
    fb.close()

    config = GlobalConfig.load()
    config.last_opened_path = str(pfad)
    config.save()
    return pfad


# --- Tasten ---------------------------------------------------------------------


def test_es_gibt_genau_eine_export_aktion() -> None:
    # Gegenprobe zur Umstellung: bliebe die alte Aktion stehen, gaebe es zwei
    # Wege mit unterschiedlichem Verhalten.
    assert hasattr(FahrtenbuchApp, "action_export")
    assert not hasattr(FahrtenbuchApp, "action_export_excel")


async def test_f_tasten_stil_bindet_f7_bis_f10() -> None:
    _stil_festlegen("function_keys")
    app = FahrtenbuchApp()
    async with app.run_test() as pilot:
        await _settle(pilot)
        gebunden = _gebundene_tasten(app)

    assert gebunden["f1"] == "show_about"
    assert gebunden["f2"] == "show_settings"
    assert gebunden["f4"] == "toggle_log"
    assert gebunden["f7"] == "new_trip"
    assert gebunden["f8"] == "check_plausibility"
    assert gebunden["f9"] == "toggle_blacklist"
    assert gebunden["f10"] == "export"
    assert gebunden["e"] == "export"
    # Das Log hat seinen Buchstaben abgegeben - l ist in der Vim-Ebene "rechts".
    assert "l" not in gebunden


async def test_im_bestandsstil_bleibt_alles_auf_buchstaben() -> None:
    _stil_festlegen("classic")
    app = FahrtenbuchApp()
    async with app.run_test() as pilot:
        await _settle(pilot)
        gebunden = _gebundene_tasten(app)

    assert gebunden["e"] == "export"
    assert gebunden["l"] == "toggle_log"
    # Beweist, dass der Stil wirklich angekommen ist - sonst prueft der Test
    # nur die Vorgabe der Plattform.
    assert "f10" not in gebunden


async def test_fragezeichen_oeffnet_die_uebersicht(fahrtenbuch: Path) -> None:
    app = FahrtenbuchApp()
    async with app.run_test(size=(160, 50)) as pilot:
        await _settle(pilot)
        assert app._fahrtenbuch is not None
        await pilot.press("question_mark")
        await _settle(pilot)
        assert isinstance(app.screen, KeymapScreen)


# --- Export ---------------------------------------------------------------------


async def test_export_schreibt_markdown_und_merkt_das_verzeichnis(fahrtenbuch: Path) -> None:
    app = FahrtenbuchApp()
    async with app.run_test(size=(160, 50)) as pilot:
        await _settle(pilot)
        assert app._fahrtenbuch is not None
        app._year, app._month = 2024, 5

        app.action_export()
        await _settle(pilot)
        assert isinstance(app.screen, ExportSaveScreen), type(app.screen).__name__

        feld = app.screen.query_one(Input)
        assert feld.value.startswith("Fahrtenbuch 2024-05 (Testwagen - B-TT 1) ")
        assert feld.value.endswith(".xlsx")

        feld.value = "Auswertung.md"
        feld.focus()
        await pilot.pause()
        await pilot.press("enter")
        await _settle(pilot)

    ziel = fahrtenbuch / "Auswertung.md"
    assert ziel.is_file()
    text = ziel.read_text(encoding="utf-8")
    assert "| 02.05.2024 |" in text
    assert "Kunde Nord" in text
    assert GlobalConfig.load().last_export_dir == str(fahrtenbuch)


async def test_export_ohne_fahrten_oeffnet_keinen_dialog(fahrtenbuch: Path) -> None:
    app = FahrtenbuchApp()
    async with app.run_test(size=(160, 50)) as pilot:
        await _settle(pilot)
        app._year, app._month = 2023, 1
        app.action_export()
        await _settle(pilot)
        assert not isinstance(app.screen, ExportSaveScreen)
        assert app._pending_export is None


async def test_dialog_geht_ohne_schreibtisch_auf(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Auf einem Rechner ohne Verzeichnis "Desktop" darf der Dialog nicht abstuerzen.

    In jira-timesheet ist genau das auf dem Linux-Runner der CI passiert.
    """
    heim = tmp_path / "heim-ohne-schreibtisch"
    heim.mkdir()
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: heim))

    app = FahrtenbuchApp()
    async with app.run_test() as pilot:
        await _settle(pilot)
        assert app._fahrtenbuch is None
        app._config.last_export_dir = str(heim / "gibt-es-nicht")
        assert app._save_dialog_location() == str(heim)


# --- Einstellungen --------------------------------------------------------------


async def test_einstellungen_speichern_die_tastenbelegung(fahrtenbuch: Path) -> None:
    _stil_festlegen("classic")
    app = FahrtenbuchApp()
    async with app.run_test(size=(160, 50)) as pilot:
        await _settle(pilot)
        app.action_show_settings()
        await _settle(pilot)

        dialog = app.screen
        dialog.query_one("#set-keymap-style", Select).value = "function_keys"
        dialog.query_one("#set-keymap-vim", Checkbox).value = True
        await pilot.press("ctrl+s")
        await _settle(pilot)
        assert app.screen is not dialog

    geladen = GlobalConfig.load()
    assert (geladen.keymap_style, geladen.keymap_vim) == ("function_keys", True)
