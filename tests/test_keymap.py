"""Tests der umschaltbaren Tastenbelegung.

Die Mechanik selbst ist in `textual-widgets` geprueft. Hier steht, was diese
Anwendung ausmacht: dass die Bestandstabelle zur Anwendung passt, dass beide
Stile das Erwartete binden, dass jede Beschriftung in beiden Sprachen existiert
und dass die Vim-Ebene an den Tabellen wirklich ankommt.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from textual.app import App, ComposeResult
from textual_widgets.keymap import KeymapStyle, find_collisions, function_key_number

from christo import keymap
from christo.models.settings import HOME_ENV_VAR, GlobalConfig
from christo.screens.keymap_screen import ist_grossschreibung
from christo.widgets.navigable_data_table import NavigableDataTable

_LOCALE = Path(__file__).resolve().parent.parent / "src" / "christo" / "locale"


def _config(**werte: Any) -> GlobalConfig:
    """Baut eine Konfiguration mit den genannten Werten."""
    return GlobalConfig(**werte)


# --- Die Tabelle der Anwendung --------------------------------------------------


def test_bestandstabelle_ist_kollisionsfrei() -> None:
    assert find_collisions(keymap.CLASSIC) == ()


def test_jede_aktion_hat_beschriftung_und_tooltip() -> None:
    assert [a for a in keymap.CLASSIC if a not in keymap.LABEL_KEYS] == []
    assert [a for a in keymap.CLASSIC if a not in keymap.TOOLTIP_KEYS] == []


def test_keine_verwaiste_beschriftung() -> None:
    # Gegenrichtung: eine verwaiste Beschriftung heisst, dass eine Aktion
    # entfernt wurde und der Schluessel liegen blieb.
    assert [a for a in keymap.LABEL_KEYS if a not in keymap.CLASSIC] == []
    assert [a for a in keymap.TOOLTIP_KEYS if a not in keymap.CLASSIC] == []


@pytest.mark.parametrize("sprache", ["de", "en"])
def test_jeder_schluessel_steht_im_sprachpaket(sprache: str) -> None:
    texte = json.loads((_LOCALE / f"{sprache}.json").read_text(encoding="utf-8"))
    fehlend = [k for k in (*keymap.LABEL_KEYS.values(), *keymap.TOOLTIP_KEYS.values()) if k not in texte]
    assert fehlend == []


def test_jede_aktion_gibt_es_in_der_app() -> None:
    from christo.app import FahrtenbuchApp

    fehlend = [a for a in keymap.CLASSIC if not hasattr(FahrtenbuchApp, f"action_{a}")]
    assert fehlend == []


def test_beide_stile_sind_kollisionsfrei() -> None:
    for stil in KeymapStyle:
        ergebnis = keymap.resolve(_config(keymap_style=stil.value))
        assert ergebnis.problems == (), f"{stil.value}: {[p.message for p in ergebnis.problems]}"


# --- Die Stile ------------------------------------------------------------------


def test_klassisch_laesst_alles_wie_bisher() -> None:
    bindings = keymap.resolve(_config(keymap_style="classic")).bindings
    assert bindings["show_settings"].keys == ("s", "S")
    assert bindings["show_about"].keys == ("i", "I")
    assert bindings["toggle_log"].keys == ("l", "L")
    assert bindings["new_trip"].keys == ("n", "N")
    assert bindings["export"].keys == ("e", "E")


def test_f_tasten_treten_neben_die_buchstaben() -> None:
    bindings = keymap.resolve(_config(keymap_style="function_keys")).bindings
    assert bindings["show_about"].keys == ("f1", "i", "I")
    assert bindings["show_settings"].keys == ("f2", "s", "S")
    assert bindings["toggle_log"].keys == ("f4", "alt+l")
    assert bindings["refresh"].keys == ("f5",)
    assert bindings["new_trip"].keys == ("f7", "n", "N")
    assert bindings["check_plausibility"].keys == ("f8", "p", "P")
    assert bindings["toggle_blacklist"].keys == ("f9", "b", "B")
    assert bindings["export"].keys == ("f10", "e", "E")


def test_nur_das_log_verliert_seinen_buchstaben() -> None:
    # Der Anspruch der Umstellung: sie nimmt genau eine Taste weg.
    klassisch = keymap.resolve(_config(keymap_style="classic")).bindings
    f_tasten = keymap.resolve(_config(keymap_style="function_keys")).bindings
    verloren = {a: sorted(set(klassisch[a].keys) - set(f_tasten[a].keys)) for a in klassisch}
    assert {a: k for a, k in verloren.items() if k} == {"toggle_log": ["L", "l"]}


# --- F-Tasten und Footer-Reihenfolge --------------------------------------------


def test_f_reihe_hat_genau_die_geplanten_tasten() -> None:
    # F3 (Filter) und F6 (Details) gibt es in Christophorus nicht.
    bindings = keymap.resolve(_config(keymap_style="function_keys")).bindings
    nummern = sorted(n for b in bindings.values() if (n := function_key_number(b)) is not None)
    assert nummern == [1, 2, 4, 5, 7, 8, 9, 10]


def test_f11_und_f12_bleiben_frei() -> None:
    bindings = keymap.resolve(_config(keymap_style="function_keys")).bindings
    belegt = {key for b in bindings.values() for key in b.keys}
    assert not belegt & {"f11", "f12"}


def test_footer_beginnt_mit_den_f_tasten_in_der_richtigen_reihenfolge() -> None:
    bindings = keymap.resolve(_config(keymap_style="function_keys")).bindings
    sichtbar = [keymap.key_display(b.keys[0]) for b in bindings.values() if b.show]
    assert sichtbar[:8] == ["F1", "F2", "F4", "F5", "F7", "F8", "F9", "F10"]
    assert all(not e.startswith("F") for e in sichtbar[8:])


def test_klassischer_stil_behaelt_seine_reihenfolge() -> None:
    reihenfolge = list(keymap.resolve(_config(keymap_style="classic")).bindings)
    assert reihenfolge == list(keymap.CLASSIC)


def test_jede_f_taste_hat_eine_anzeige() -> None:
    bindings = keymap.resolve(_config(keymap_style="function_keys")).bindings
    for action, binding in bindings.items():
        erste = binding.keys[0]
        if function_key_number(binding) is not None and erste.startswith("f"):
            assert keymap.key_display(erste) == erste.upper(), f"{action}: {erste}"


@pytest.mark.parametrize(
    ("plattform", "erwartet"),
    [("darwin", KeymapStyle.CLASSIC), ("win32", KeymapStyle.FUNCTION_KEYS)],
)
def test_leerer_stil_folgt_der_plattform(
    plattform: str, erwartet: KeymapStyle, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("textual_widgets.keymap.sys.platform", plattform)
    assert keymap.style_from_settings(_config(keymap_style="")) is erwartet


def test_unbekannter_stil_faellt_nicht_um() -> None:
    # Eine von Hand verbogene Konfigurationsdatei darf den Start nicht verhindern.
    assert keymap.style_from_settings(_config(keymap_style="quatsch")) in tuple(KeymapStyle)


# --- Eigene Belegungen ----------------------------------------------------------


def test_eigene_belegung_gewinnt() -> None:
    ergebnis = keymap.resolve(_config(keymap_style="function_keys", keymap_custom={"toggle_log": ["alt+l"]}))
    assert ergebnis.bindings["toggle_log"].keys == ("alt+l",)
    assert ergebnis.problems == ()


def test_eigene_belegung_auf_unbekannte_aktion_wird_gemeldet() -> None:
    ergebnis = keymap.resolve(_config(keymap_custom={"gibtsnicht": ["z"]}))
    assert len(ergebnis.problems) == 1
    assert "gibtsnicht" in ergebnis.problems[0].message


def test_eigene_belegung_darf_quit_nicht_ausknipsen() -> None:
    ergebnis = keymap.resolve(_config(keymap_style="classic", keymap_custom={"show_about": ["q", "Q"]}))
    assert ergebnis.bindings["quit"].keys == ("q", "Q")
    assert len(ergebnis.problems) == 1


def test_vim_im_bestandsstil_meldet_das_verdeckte_log() -> None:
    # Im Bestandsstil liegt das Log auf l - mit Vim-Ebene waere es in Tabellen
    # stumm. Das muss im Log stehen, nicht still passieren.
    ergebnis = keymap.resolve(_config(keymap_style="classic", keymap_vim=True))
    assert {p.action for p in ergebnis.problems} == {"toggle_log"}


# --- Konfiguration --------------------------------------------------------------


def test_konfiguration_liegt_im_umgebogenen_verzeichnis(_isolated_config: Path) -> None:
    # Positivkontrolle der Test-Isolation: ohne sie laege die Datei im echten
    # Heimatverzeichnis.
    erwartet = _isolated_config / "config.json"
    assert erwartet == GlobalConfig().CONFIG_FILE


def test_tastenbelegung_ueberlebt_speichern_und_laden(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    ziel = tmp_path / "eigene-home"
    monkeypatch.setenv(HOME_ENV_VAR, str(ziel))
    config = GlobalConfig.load()
    config.keymap_style = "function_keys"
    config.keymap_vim = True
    config.keymap_custom = {"toggle_log": ["alt+l"]}
    config.last_export_dir = str(tmp_path)
    config.save()

    geladen = GlobalConfig.load()
    assert (ziel / "config.json").is_file()
    assert geladen.keymap_style == "function_keys"
    assert geladen.keymap_vim is True
    assert geladen.keymap_custom == {"toggle_log": ["alt+l"]}
    assert geladen.last_export_dir == str(tmp_path)


# --- Die Vim-Ebene am Widget ----------------------------------------------------


class _TabellenApp(App[None]):
    """Kleinste App mit einer Tabelle, um die Vim-Bindung zu pruefen."""

    def __init__(self, vim: bool) -> None:
        super().__init__()
        self._vim = vim

    @property
    def vim_navigation(self) -> bool:
        return self._vim

    def compose(self) -> ComposeResult:
        yield NavigableDataTable(id="probe")

    def on_mount(self) -> None:
        tabelle = self.query_one("#probe", NavigableDataTable)
        tabelle.add_column("a")
        for zeile in ("eins", "zwei", "drei"):
            tabelle.add_row(zeile)
        tabelle.focus()


async def test_j_bewegt_den_zeiger_wenn_vim_an_ist() -> None:
    app = _TabellenApp(vim=True)
    async with app.run_test() as pilot:
        tabelle = app.query_one("#probe", NavigableDataTable)
        assert tabelle.cursor_row == 0
        await pilot.press("j")
        await pilot.pause()
        assert tabelle.cursor_row == 1
        await pilot.press("k")
        await pilot.pause()
        assert tabelle.cursor_row == 0


async def test_j_tut_nichts_wenn_vim_aus_ist() -> None:
    # Gegenprobe: ohne den Schalter darf die Taste den Zeiger nicht bewegen.
    app = _TabellenApp(vim=False)
    async with app.run_test() as pilot:
        tabelle = app.query_one("#probe", NavigableDataTable)
        await pilot.press("j")
        await pilot.pause()
        assert tabelle.cursor_row == 0


# --- Uebersichtsseite und Tastenhinweise ----------------------------------------


def test_uebersicht_zeigt_jede_aktion_mit_taste() -> None:
    ergebnis = keymap.resolve(_config(keymap_style="function_keys"))
    for action, binding in ergebnis.bindings.items():
        sichtbar = [key for key in binding.keys if not ist_grossschreibung(key)]
        assert sichtbar, f"{action} haette in der Uebersicht keine Taste"


def test_grossschreibung_wird_als_dublette_erkannt() -> None:
    assert ist_grossschreibung("Q")
    assert not ist_grossschreibung("q")
    assert not ist_grossschreibung("f5")
    assert not ist_grossschreibung("alt+l")


@pytest.mark.parametrize("sprache", ["de", "en"])
def test_keine_meldung_nennt_eine_taste_woertlich(sprache: str) -> None:
    """Die Texte hatten [V], [S] und [N] fest eingebaut - im F-Tasten-Stil falsch."""
    texte = json.loads((_LOCALE / f"{sprache}.json").read_text(encoding="utf-8"))
    for schluessel in ("log.fahrtenbuch_closed_hint", "log.configure_vehicle_hint", "summary.empty_hint"):
        assert "{shortcut}" in texte[schluessel], f"{sprache}/{schluessel} hat keinen Platzhalter"


async def test_tastenhinweis_folgt_dem_stil() -> None:
    from christo.app import FahrtenbuchApp

    for stil, erwartet in (("classic", ("S", "N")), ("function_keys", ("F2", "F7"))):
        config = GlobalConfig.load()
        config.keymap_style = stil
        config.save()
        app = FahrtenbuchApp()
        assert (app._key_hint("show_settings"), app._key_hint("new_trip")) == erwartet, stil
