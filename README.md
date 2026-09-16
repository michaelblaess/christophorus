# Christophorus

<p align="center">
  <img src="docs/flags/gb.svg" height="13" alt=""> <b>English</b> ·
  <img src="docs/flags/de.svg" height="13" alt=""> <a href="README.de.md">Deutsch</a>
</p>

---

<p align="center">
  <img src="docs/christophorus.png" width="200" alt="Christophorus logo">
</p>

A terminal application for keeping a vehicle logbook (German: *Fahrtenbuch*),
for leased and owned vehicles alike. Christophorus records every trip, keeps the
odometer chain consistent, checks the entries for plausibility and exports
the logbook as Excel, JSON or Markdown.

The user interface is available in German and English.

The name comes from Saint Christopher, the patron saint of travellers and
drivers. In the terminal it is shorter: `christo` starts the same program.
Up to version 1.2.1 the project was called "Death Proof", before that
"fahrtenbuch". On the first start Christophorus picks up settings and logbooks
stored under the old names on its own.

> **Note:** Whether a logbook is accepted for tax purposes is decided solely by
> the tax office. Christophorus does not guarantee that acceptance and does not
> replace tax advice. On first start the program asks you to confirm this notice.

## Features

- **Trips:** date, travel time, destination, purpose, odometer start and end,
  business and private kilometres, category, round trip, fuel in litres.
- **Views:** list per month and per year, calendar, year overview, blocked days
  (blacklist), receipts and working hours.
- **Plausibility checks:** odometer chain, fuel consumption against the vehicle
  data, business trips on weekends and public holidays, suspected duplicate
  entries, yearly share of business kilometres.
- **Repair the odometer chain:** rebuilds start and end values chronologically
  without changing the distance of any trip.
- **Export** through a save dialog: Excel with live formulas, JSON with every
  field, Markdown table. The format follows the file extension.
- **Several logbooks:** each logbook is a folder with its own SQLite database.
  Open, create, back up, or copy the settings of an existing logbook.
- **Settings:** vehicle and lease data, home address, customers, petrol
  stations, shops, tax adviser, restaurants, categories, federal state for
  public holidays, SQLite journal mode (safe for Dropbox and OneDrive).
- **Keyboard:** classic letters or function keys F1 to F10, optional Vim
  navigation in tables, overview on `?`.
- **Anonymize** for screenshots: destinations, purposes, vehicle, number plate
  and folder are replaced in the display. Database and export stay untouched,
  dialogs showing real data are locked while it is on.
- **Themes** from [textual-themes](https://github.com/michaelblaess/textual-themes).

## Installation

### Prebuilt binaries

Every release on the [Releases page](https://github.com/michaelblaess/christophorus/releases)
contains standalone builds for Windows (x64), Linux (x86_64) and macOS (Apple Silicon).
Unpack the archive and start `christophorus`.

### From source

Requires Python 3.12 or newer and [uv](https://docs.astral.sh/uv/).

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

## Usage

```bash
christophorus                 # opens the last logbook, otherwise the start screen
christophorus --year 2024     # start in a specific year
christophorus --lang en       # switch the language (saved for the next start)
christophorus --version
```

## Key bindings

The style is chosen under Settings -> Keyboard. With function keys the letters
stay available, only the log moves from `L` to `F4`.

| Action | Classic | With function keys |
|---|---|---|
| Info | `I` | `F1` |
| Settings | `S` | `F2` |
| Manage logbooks | `V` | `F3` |
| Log on/off | `L` | `F4` / `Alt+L` |
| Refresh | `F5` | `F5` |
| Repair odometer chain | `R` | `F6` |
| New trip | `N` | `F7` |
| Plausibility check | `P` | `F8` |
| Blacklist on/off | `B` | `F9` |
| Export | `E` | `F10` |
| Delete trip | `DEL` | `DEL` |
| Next theme | `T` | `T` |
| Anonymize display | `A` | `A` |
| Previous / next month | `<` / `>` | `<` / `>` |
| Key overview | `?` | `?` |
| Quit | `Q` | `Q` |

Custom bindings go into `config.json` under `keymap_custom`, for example
`{"toggle_log": ["alt+l"]}`.

## Where the data lives

| What | Where |
|---|---|
| Application settings | `~/.christo/config.json` |
| Acceptance of the notice | `~/.christo/disclaimer.json` |
| Logbook | a folder of your choice with `christo.db` and a `belege/` folder for receipts |

## Development

```bash
uv run poe lint        # ruff
uv run poe typecheck   # mypy strict
uv run poe layers      # import-linter: layer boundaries
uv run poe test        # pytest
```

The core (`services`, `models`) does not import the user interface or Textual.
import-linter enforces this in CI and in the pre-commit hook.

## Tech stack

[Textual](https://textual.textualize.io/), SQLite, [openpyxl](https://openpyxl.readthedocs.io/),
[holidays](https://github.com/vacanza/holidays),
[textual-fspicker](https://github.com/davep/textual-fspicker),
[textual-widgets](https://github.com/michaelblaess/textual-widgets) and
[textual-themes](https://github.com/michaelblaess/textual-themes).

## License

[Apache License 2.0](./LICENSE)

## Author

Michael Blaess
