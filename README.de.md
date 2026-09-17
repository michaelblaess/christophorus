# Christophorus

<p align="center">
  <img src="docs/flags/gb.svg" height="13" alt=""> <a href="README.md">English</a> ·
  <img src="docs/flags/de.svg" height="13" alt=""> <b>Deutsch</b>
</p>

---

<p align="center">
  <img src="docs/christophorus.png" width="200" alt="Christophorus-Logo">
</p>

Eine Terminal-Anwendung für das Fahrtenbuch, für geleaste wie für gekaufte Fahrzeuge.
Christophorus erfasst jede Fahrt, hält die Kilometerkette stimmig, prüft die
Einträge auf Plausibilität und exportiert das Fahrtenbuch als Excel, JSON oder
Markdown.

Die Oberfläche gibt es auf Deutsch und Englisch.

Projektseite: [michaelblaess.github.io/christophorus](https://michaelblaess.github.io/christophorus/de/)

Der Name stammt vom heiligen Christophorus, dem Schutzpatron der Reisenden und
Autofahrer. Im Terminal geht es kürzer: `christo` startet dasselbe Programm.
Bis Version 1.2.1 hieß das Projekt "Death Proof", davor "fahrtenbuch". Beim
ersten Start übernimmt Christophorus Einstellungen und Fahrtenbücher unter den
alten Namen von selbst.

> **Hinweis:** Ob ein Fahrtenbuch steuerlich anerkannt wird, entscheidet allein
> das Finanzamt. Christophorus sichert diese Anerkennung nicht zu und ersetzt keine
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
- **Anonymisieren** für Screenshots: Ziele, Zwecke, Fahrzeug, Kennzeichen und
  Ordner werden in der Anzeige ersetzt. Datenbank und Export bleiben unberührt,
  Dialoge mit echten Daten sind solange gesperrt.
- **Themes** aus [textual-themes](https://github.com/michaelblaess/textual-themes).

## Screenshots

Alle Screenshots zeigen erfundene Daten.

| Monatsliste | Kalender |
|---|---|
| ![Monatsliste](docs/screenshots/de/01-month-list.png) | ![Kalender](docs/screenshots/de/02-calendar.png) |
| **Jahresübersicht** | **Plausicheck** |
| ![Jahresübersicht](docs/screenshots/de/03-year-overview.png) | ![Plausicheck](docs/screenshots/de/04-plausicheck.png) |
| **Neue Fahrt** | |
| ![Neue Fahrt](docs/screenshots/de/05-new-trip.png) | |

## Installation

### Installation mit einem Befehl

Der Installer lädt das fertige Paket des neuesten Releases. Python und git
brauchst du dafür nicht. Ein zweiter Aufruf aktualisiert das Programm, deine
Einstellungen und Fahrtenbücher bleiben unberührt.

**Windows (PowerShell):**

```powershell
irm https://raw.githubusercontent.com/michaelblaess/christophorus/main/install.ps1 | iex
```

**Linux (x86_64) und macOS (Apple Silicon):**

```bash
curl -fsSL https://raw.githubusercontent.com/michaelblaess/christophorus/main/install.sh | bash
```

Danach startest du `christophorus` oder kurz `christo`. Unter Windows vorher ein
neues Terminal öffnen, damit der erweiterte PATH greift.

### Manuell herunterladen

Jedes Release auf der [Releases-Seite](https://github.com/michaelblaess/christophorus/releases)
enthält eigenständige Builds für Windows (x64), Linux (x86_64) und macOS (Apple Silicon).
Archiv entpacken und `christophorus` starten.

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
christophorus                 # öffnet das zuletzt benutzte Fahrtenbuch, sonst den Startbildschirm
christophorus --year 2024     # in einem bestimmten Jahr starten
christophorus --lang en       # Sprache wechseln (wird für den nächsten Start gemerkt)
christophorus --version
```

## Tastenbelegung

Den Stil wählst du unter Einstellungen -> Tastatur. Mit F-Tasten bleiben die
Buchstaben erhalten, nur das Log zieht von `L` auf `F4`.

| Aktion | Klassisch | Mit F-Tasten |
|---|---|---|
| Info | `I` | `F1` |
| Einstellungen | `S` | `F2` |
| Fahrtenbücher verwalten | `V` | `F3` |
| Log ein/aus | `L` | `F4` / `Alt+L` |
| Aktualisieren | `F5` | `F5` |
| Kilometerkette reparieren | `R` | `F6` |
| Neue Fahrt | `N` | `F7` |
| Plausicheck | `P` | `F8` |
| Blacklist ein/aus | `B` | `F9` |
| Export | `E` | `F10` |
| Fahrt löschen | `DEL` | `DEL` |
| Nächstes Theme | `T` | `T` |
| Anzeige anonymisieren | `A` | `A` |
| Vorheriger / nächster Monat | `<` / `>` | `<` / `>` |
| Tastenübersicht | `?` | `?` |
| Beenden | `Q` | `Q` |

Eigene Belegungen trägst du in der `config.json` unter `keymap_custom` ein, zum
Beispiel `{"toggle_log": ["alt+l"]}`.

## Wo die Daten liegen

| Was | Wo |
|---|---|
| Programmeinstellungen | `~/.christo/config.json` |
| Zustimmung zum Hinweis | `~/.christo/disclaimer.json` |
| Fahrtenbuch | ein Ordner deiner Wahl mit `christo.db` und einem Ordner `belege/` für Belege |

## Web-Oberfläche (Vorschau)

Neben der TUI gibt es eine Weboberfläche, gebaut zum Ausprobieren von Tabler, Tabulator und
FastHTML. Sie deckt dasselbe ab wie die TUI: die Fahrten eines Monats oder Jahres, Kalender,
Jahresübersicht, Sperrtage, Belege, Arbeitszeit, Einstellungen und den Export nach Excel, JSON
oder Markdown.

```bash
uv sync --extra web
uv run python -m christo.web            # zuletzt geöffnetes Fahrtenbuch
uv run python -m christo.web <ordner>   # bestimmtes Fahrtenbuch
```

- **Sie arbeitet immer auf einer Kopie** unter `~/.christo/web/<name>/`. Die Datei, die die TUI
  benutzt, wird nie verändert. `--neu-kopieren` holt den aktuellen Stand und verwirft die Kopie.
- Läuft nur auf `127.0.0.1:5056`, ohne Anmeldung, und lädt nichts aus dem Netz.
- Die Farben kommen aus [web-themes](https://github.com/michaelblaess/web-themes), dieselben
  Themes wie in der TUI.
- Was beim Bauen an übertragbaren Mustern herauskam, steht in
  [docs/WEB-MUSTER.md](docs/WEB-MUSTER.md).

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
