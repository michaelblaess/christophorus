"""Tests fuer den bestaetigungspflichtigen Haftungshinweis beim Programmstart.

Der Hinweis ist nicht optional - ohne Zustimmung beendet sich das Programm.
Diese Tests halten fest, dass er erscheint, dass Ablehnung wirklich beendet und
dass eine einmal erteilte Zustimmung beim naechsten Start nicht erneut
abgefragt wird.

Die conftest erteilt die Zustimmung fuer alle anderen Tests. Hier wird sie
gezielt entfernt.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from textual.widgets import Button, Checkbox
from textual_widgets import DISCLAIMER_VERSION, DisclaimerScreen

from christo.app import FahrtenbuchApp


@pytest.fixture
def ohne_zustimmung(_isolated_config: Path) -> Path:
    """Entfernt die von der conftest erteilte Zustimmung."""
    datei = _isolated_config / "disclaimer.json"
    datei.unlink()
    return datei


def test_conftest_erteilt_die_zustimmung(_isolated_config: Path) -> None:
    # Positivkontrolle: ohne die Datei wuerden die uebrigen App-Tests hinter
    # dem Dialog haengen.
    assert DISCLAIMER_VERSION in (_isolated_config / "disclaimer.json").read_text(encoding="utf-8")


async def test_hinweis_erscheint_beim_ersten_start(ohne_zustimmung: Path) -> None:
    app = FahrtenbuchApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        assert isinstance(app.screen, DisclaimerScreen)


async def test_ablehnen_beendet_ohne_zustimmung(ohne_zustimmung: Path) -> None:
    app = FahrtenbuchApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        assert isinstance(app.screen, DisclaimerScreen)
        await pilot.press("escape")
        await pilot.pause()

    assert not ohne_zustimmung.is_file()


async def test_zustimmung_wird_gemerkt_und_nicht_erneut_abgefragt(ohne_zustimmung: Path) -> None:
    app = FahrtenbuchApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        dialog = app.screen
        assert isinstance(dialog, DisclaimerScreen)
        # Zustimmung wie durch den Anwender: Haken setzen, dann bestaetigen.
        dialog.query_one("#disclaimer-agree", Checkbox).value = True
        await pilot.pause()
        dialog.query_one("#disclaimer-accept", Button).press()
        await pilot.pause()
        assert not isinstance(app.screen, DisclaimerScreen)

    assert DISCLAIMER_VERSION in ohne_zustimmung.read_text(encoding="utf-8")

    wieder = FahrtenbuchApp()
    async with wieder.run_test() as pilot:
        await pilot.pause()
        assert not isinstance(wieder.screen, DisclaimerScreen)
