# Death Proof

<p align="center">
  <img src="docs/flags/gb.svg" height="13" alt=""> <a href="README.md">English</a> ·
  <img src="docs/flags/de.svg" height="13" alt=""> <b>Deutsch</b>
</p>

---

Eine Terminal-Anwendung für das Fahrtenbuch, gebaut für Leasing-Dienstwagen.
Death Proof erfasst jede Fahrt, hält die Kilometerkette stimmig, prüft die
Einträge auf Plausibilität und exportiert das Fahrtenbuch als Excel, JSON oder
Markdown.

Die Oberfläche gibt es auf Deutsch und Englisch.

> **Hinweis:** Ob ein Fahrtenbuch steuerlich anerkannt wird, entscheidet allein
> das Finanzamt. Death Proof sichert diese Anerkennung nicht zu und ersetzt keine
> steuerliche Beratung. Beim ersten Start musst du diesen Hinweis bestätigen.

## Funktionen

- **Fahrten:** Datum, Fahrzeit, Ziel, Reisezweck, Kilometerstand am Anfang und
  am Ende, geschäftliche und private Kilometer, Kategorie, Hin- und Rückfahrt,
  getankte Liter.
- **Ansichten:** Liste je Monat und je Jahr, Kalender, Jahresübersicht,
  gesperrte Tage (Blacklist), Belege und Arbeitszeit.
- **Plausibilitätsprüfung:** Kilometerkette, Verbrauch gegen die Fahrzeugdaten,
  Geschäftsfahrten am Wochenende und an Feiertagen, verdächtige Doppeleinträge,
  Anteil der Geschäftskilometer im Jahr.
- **Kilometerkette reparieren:** setzt Anfangs- und Endstände chronologisch neu,
  ohne die Strecke einer einzelnen Fahrt zu verändern.
- **Export** über einen Speichern-Dialog: Excel mit Live-Formeln, JSON mit allen
  Feldern, Markdown-Tabelle. Das Format folgt der Dateiendung.
- **Mehrere Fahrtenbücher:** Jedes Fahrtenbuch ist ein Ordner mit eigener
  SQLite-Datenbank. Öffnen, neu anlegen, sichern oder die Einstellungen eines
  bestehenden Fahrtenbuchs übernehmen.
- **Einstellungen:** Fahrzeug- und Leasingdaten, Wohnadresse, Kunden,
  Tankstellen, Einkaufen, Steuerberatung, Restaurants, Kategorien, Bundesland
  für die Feiertage, SQLite-Journal-Modus (sicher für Dropbox und OneDrive).
- **Tastatur:** klassisch mit Buchstaben oder mit den F-Tasten F1 bis F10,
  wahlweise Vim-Navigation in Tabellen, Übersicht auf `?`.
- **Themes** aus [textual-themes](https://github.com/michaelblaess/textual-themes).

## Installation

### Fertige Programmpakete

Jedes Release auf der [Releases-Seite](https://github.com/michaelblaess/death-proof/releases)
enthält eigenständige Builds für Windows (x64), Linux (x86_64) und macOS (Apple Silicon).
Archiv entpacken und `death-proof` starten.

### Aus dem Quellcode

Du brauchst Python 3.12 oder neuer und [uv](https://docs.astral.sh/uv/).

```powershell
# Windows
.\bootstrap.ps1
.\run.ps1
```

```bash
# Linux / macOS
./bootstrap.sh
./run.sh
```

## Benutzung

```bash
death-proof                 # öffnet das zuletzt benutzte Fahrtenbuch, sonst den Startbildschirm
death-proof --year 2024     # in einem bestimmten Jahr starten
death-proof --lang en       # Sprache wechseln (wird für den nächsten Start gemerkt)
death-proof --version
```

## Tastenbelegung

Den Stil wählst du unter Einstellungen -> Tastatur. Mit F-Tasten bleiben die
Buchstaben erhalten, nur das Log zieht von `L` auf `F4`.

| Aktion | Klassisch | Mit F-Tasten |
|---|---|---|
| Info | `I` | `F1` |
| Einstellungen | `S` | `F2` |
| Log ein/aus | `L` | `F4` / `Alt+L` |
| Aktualisieren | `F5` | `F5` |
| Neue Fahrt | `N` | `F7` |
| Plausibilitätsprüfung | `P` | `F8` |
| Blacklist ein/aus | `B` | `F9` |
| Export | `E` | `F10` |
| Fahrt löschen | `DEL` | `DEL` |
| Fahrtenbücher verwalten | `V` | `V` |
| Kilometerkette reparieren | `R` | `R` |
| Nächstes Theme | `T` | `T` |
| Vorheriger / nächster Monat | `<` / `>` | `<` / `>` |
| Tastenübersicht | `?` | `?` |
| Beenden | `Q` | `Q` |

Eigene Belegungen trägst du in der `config.json` unter `keymap_custom` ein, zum
Beispiel `{"toggle_log": ["alt+l"]}`.

## Wo die Daten liegen

| Was | Wo |
|---|---|
| Programmeinstellungen | `~/.death-proof/config.json` |
| Zustimmung zum Hinweis | `~/.death-proof/disclaimer.json` |
| Fahrtenbuch | ein Ordner deiner Wahl mit `death-proof.db` und einem Ordner `belege/` für Belege |

## Entwicklung

```bash
uv run poe lint        # ruff
uv run poe typecheck   # mypy strict
uv run poe layers      # import-linter: Schichtgrenzen
uv run poe test        # pytest
```

Der Kern (`services`, `models`) importiert weder die Oberfläche noch Textual.
Das prüft import-linter in der CI und im pre-commit-Hook.

## Tech-Stack

[Textual](https://textual.textualize.io/), SQLite, [openpyxl](https://openpyxl.readthedocs.io/),
[holidays](https://github.com/vacanza/holidays),
[textual-fspicker](https://github.com/davep/textual-fspicker),
[textual-widgets](https://github.com/michaelblaess/textual-widgets) und
[textual-themes](https://github.com/michaelblaess/textual-themes).

## Lizenz

[Apache License 2.0](./LICENSE)

## Autor

Michael Blaess
