"""Tastenbelegung von Death Proof.

Die Mechanik (Stile, Vim-Ebene, eigene Belegungen, Pruefer) liegt in
`textual_widgets.keymap`. Hier steht nur, was diese Anwendung ausmacht: ihre
Aktionen im Bestandsstil, ihre F-Tasten, die Zuordnung zu den Beschriftungen
aus dem Sprachpaket und die Bruecke zur Konfiguration.

Aufbau uebernommen aus jira-timesheet (keymap.py, Stand v1.22.1).

Public API:
    - `CLASSIC` - die Belegung im Bestandsstil, so wie sie bis v1.2.1 galt.
    - `LABEL_KEYS` / `TOOLTIP_KEYS` - Aktion auf i18n-Schluessel.
    - `APP_FUNCTION_KEYS` / `FUNCTION_KEYS` - die F-Tasten dieser Anwendung.
    - `resolve(config)` - die fertige Belegung aus der Konfiguration.
    - `style_from_settings(config)` - der gewaehlte oder vorgeschlagene Stil.
"""

from __future__ import annotations

from typing import Any

from textual_widgets.keymap import (
    COMMON_FUNCTION_KEYS,
    KeyBinding,
    KeymapStyle,
    ResolvedKeymap,
    default_style_for_platform,
    parse_overrides,
    resolve_keymap,
    sort_for_footer,
)

CLASSIC: dict[str, KeyBinding] = {
    "quit": KeyBinding(("q", "Q")),
    "new_trip": KeyBinding(("n", "N")),
    # Loeschen bewusst auf DEL statt auf einen Buchstaben - destruktiv.
    "delete_trip": KeyBinding(("delete",)),
    "export": KeyBinding(("e", "E")),
    "show_settings": KeyBinding(("s", "S")),
    "open_fahrtenbuch": KeyBinding(("v", "V")),
    "toggle_blacklist": KeyBinding(("b", "B")),
    # Monatsnavigation: die Pfeile im InfoHeader zeigen die Funktion schon,
    # im Footer waere sie doppelt.
    "prev_month": KeyBinding(("comma",), show=False),
    "next_month": KeyBinding(("full_stop",), show=False),
    "refresh": KeyBinding(("f5",)),
    "check_plausibility": KeyBinding(("p", "P")),
    "rebuild_km": KeyBinding(("r", "R")),
    "toggle_log": KeyBinding(("l", "L")),
    "log_bigger": KeyBinding(("plus",), show=False),
    "log_smaller": KeyBinding(("minus",), show=False),
    "copy_log": KeyBinding(("c", "C"), show=False),
    "clear_log": KeyBinding(("ctrl+l",), show=False),
    "cycle_theme": KeyBinding(("t", "T")),
    "show_about": KeyBinding(("i", "I")),
    # Uebersicht der Belegung. "?" ist frei und in Terminals die gelaeufige
    # Taste dafuer - im Footer waere sie nur Ballast.
    "keymap_overview": KeyBinding(("question_mark",), show=False),
}
"""Der Bestandsstil - Stand v1.2.1, woertlich aus dem frueheren app.py."""

LABEL_KEYS: dict[str, str] = {
    "quit": "binding.quit",
    "new_trip": "binding.new_trip",
    "delete_trip": "binding.delete",
    "export": "binding.export",
    "show_settings": "binding.settings",
    "open_fahrtenbuch": "binding.manage",
    "toggle_blacklist": "binding.blacklist",
    "prev_month": "binding.month_prev",
    "next_month": "binding.month_next",
    "refresh": "binding.refresh",
    "check_plausibility": "binding.plausibility",
    "rebuild_km": "binding.rebuild_km",
    "toggle_log": "binding.log_toggle",
    "log_bigger": "binding.log_bigger",
    "log_smaller": "binding.log_smaller",
    "copy_log": "binding.log_copy",
    "clear_log": "binding.log_clear",
    "cycle_theme": "binding.theme",
    "show_about": "binding.info",
    "keymap_overview": "binding.keymap_overview",
}
"""Aktion auf den i18n-Schluessel ihrer Footer-Beschriftung."""

TOOLTIP_KEYS: dict[str, str] = {
    "quit": "tooltip.quit",
    "new_trip": "tooltip.new_trip",
    "delete_trip": "tooltip.delete",
    "export": "tooltip.export",
    "show_settings": "tooltip.settings",
    "open_fahrtenbuch": "tooltip.manage",
    "toggle_blacklist": "tooltip.blacklist",
    "prev_month": "tooltip.month_prev",
    "next_month": "tooltip.month_next",
    "refresh": "tooltip.refresh",
    "check_plausibility": "tooltip.plausibility",
    "rebuild_km": "tooltip.rebuild_km",
    "toggle_log": "tooltip.log_toggle",
    "log_bigger": "tooltip.log_bigger",
    "log_smaller": "tooltip.log_smaller",
    "copy_log": "tooltip.log_copy",
    "clear_log": "tooltip.log_clear",
    "cycle_theme": "tooltip.theme",
    "show_about": "tooltip.info",
    "keymap_overview": "tooltip.keymap_overview",
}
"""Aktion auf den i18n-Schluessel ihres Footer-Tooltips."""

# Die Anzeige der Taste im Footer. Ohne das steht dort "full_stop" statt ">".
KEY_DISPLAY: dict[str, str] = {
    "comma": "<",
    "full_stop": ">",
    "plus": "+",
    "minus": "-",
    "delete": "DEL",
    "question_mark": "?",
    "f1": "F1",
    "f2": "F2",
    "f3": "F3",
    "f4": "F4",
    "f5": "F5",
    "f6": "F6",
    "f7": "F7",
    "f8": "F8",
    "f9": "F9",
    "f10": "F10",
}


def key_display(key: str) -> str:
    """Uebersetzt einen Tastennamen in seine Anzeige im Footer.

    Args:
        key: Der Tastenname, so wie Textual ihn kennt.

    Returns:
        Der Text fuer den Footer.
    """
    return KEY_DISPLAY.get(key, key)


def style_from_settings(config: Any) -> KeymapStyle:
    """Ermittelt den Stil aus der Konfiguration.

    Ein leerer Wert heisst "noch nicht entschieden" - dann entscheidet die
    Plattform, damit eine frische Installation auf dem Mac nicht mit F-Tasten
    startet, die das Betriebssystem abfaengt.

    Args:
        config: Die geladene Konfiguration (GlobalConfig).

    Returns:
        Der anzuwendende Stil.
    """
    gewaehlt = str(getattr(config, "keymap_style", "") or "").strip().lower()
    for stil in KeymapStyle:
        if gewaehlt == stil.value:
            return stil
    return default_style_for_platform()


APP_FUNCTION_KEYS: dict[str, KeyBinding] = {
    "new_trip": KeyBinding(("f7", "n", "N")),
    "check_plausibility": KeyBinding(("f8", "p", "P")),
    "toggle_blacklist": KeyBinding(("f9", "b", "B")),
    "export": KeyBinding(("f10", "e", "E")),
}
"""Die F-Tasten, die diese Anwendung selbst vergibt.

`f1` bis `f6` kommen aus der gemeinsamen Konvention. Davon nutzt Death Proof
F1 (Info), F2 (Einstellungen), F4 (Log) und F5 (Aktualisieren) - einen Filter
(F3) und eine Detailansicht (F6) gibt es hier nicht, die Plaetze bleiben leer.

Ab `f7` in der Reihenfolge der Arbeit: erfassen, pruefen, Sperrtage
markieren, ausgeben.

Ohne F-Taste bleiben bewusst:

- `q` Beenden und `DEL` Loeschen - eindeutig, Loeschen soll nicht auf einer
  Taste liegen, die man im Vorbeigehen trifft.
- `v` Verwalten, `r` km-Kette reparieren und `t` Theme - selten gebraucht.
- `f11` und `f12`: viele Terminals belegen sie selbst mit Vollbild.
"""

FUNCTION_KEYS: dict[str, KeyBinding] = {**COMMON_FUNCTION_KEYS, **APP_FUNCTION_KEYS}
"""Die gemeinsame Konvention plus die Ergaenzungen dieser Anwendung."""


def resolve(config: Any) -> ResolvedKeymap:
    """Baut die fertige Belegung aus der Konfiguration.

    Im F-Tasten-Stil steht das Ergebnis in der Reihenfolge fuer den Footer:
    erst alles mit F-Taste, aufsteigend nach Nummer, danach der Rest. Im
    Bestandsstil wird NICHT sortiert - dort haette nur `refresh` eine F-Taste,
    und die allein nach vorn zu ziehen wuerde die gewohnte Reihenfolge aendern.

    Args:
        config: Die geladene Konfiguration (GlobalConfig).

    Returns:
        Die Belegung samt Beanstandungen. Die Beanstandungen gehoeren ins Log,
        nicht in einen Dialog - sie betreffen die Konfigurationsdatei, nicht
        den laufenden Vorgang.
    """
    stil = style_from_settings(config)
    overrides, probleme = parse_overrides(getattr(config, "keymap_custom", None))
    ergebnis = resolve_keymap(
        stil,
        CLASSIC,
        function_keys=FUNCTION_KEYS,
        overrides=overrides,
        vim_navigation=bool(getattr(config, "keymap_vim", False)),
    )
    if stil is not KeymapStyle.FUNCTION_KEYS:
        return ResolvedKeymap(bindings=ergebnis.bindings, problems=probleme + ergebnis.problems)
    return ResolvedKeymap(
        bindings=sort_for_footer(ergebnis.bindings),
        problems=probleme + ergebnis.problems,
    )
