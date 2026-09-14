# Death Proof

<p align="center">
  <img src="docs/flags/gb.svg" height="13" alt=""> <b>English</b> ·
  <img src="docs/flags/de.svg" height="13" alt=""> <a href="README.de.md">Deutsch</a>
</p>

---

A terminal application for keeping a vehicle logbook (German: *Fahrtenbuch*),
built for leased company cars. Death Proof records every trip, keeps the
odometer chain consistent, checks the entries for plausibility and exports
the logbook as Excel, JSON or Markdown.

The user interface is available in German and English.

> **Note:** Whether a logbook is accepted for tax purposes is decided solely by
> the tax office. Death Proof does not guarantee that acceptance and does not
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
- **Themes** from [textual-themes](https://github.com/michaelblaess/textual-themes).

## Installation

### Prebuilt binaries

Every release on the [Releases page](https://github.com/michaelblaess/death-proof/releases)
contains standalone builds for Windows (x64), Linux (x86_64) and macOS (Apple Silicon).
Unpack the archive and start `death-proof`.

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
death-proof                 # opens the last logbook, otherwise the start screen
death-proof --year 2024     # start in a specific year
death-proof --lang en       # switch the language (saved for the next start)
death-proof --version
```

## Key bindings

The style is chosen under Settings -> Keyboard. With function keys the letters
stay available, only the log moves from `L` to `F4`.

| Action | Classic | With function keys |
|---|---|---|
| Info | `I` | `F1` |
| Settings | `S` | `F2` |
| Log on/off | `L` | `F4` / `Alt+L` |
| Refresh | `F5` | `F5` |
| New trip | `N` | `F7` |
| Plausibility check | `P` | `F8` |
| Blacklist on/off | `B` | `F9` |
| Export | `E` | `F10` |
| Delete trip | `DEL` | `DEL` |
| Manage logbooks | `V` | `V` |
| Repair odometer chain | `R` | `R` |
| Next theme | `T` | `T` |
| Previous / next month | `<` / `>` | `<` / `>` |
| Key overview | `?` | `?` |
| Quit | `Q` | `Q` |

Custom bindings go into `config.json` under `keymap_custom`, for example
`{"toggle_log": ["alt+l"]}`.

## Where the data lives

| What | Where |
|---|---|
| Application settings | `~/.death-proof/config.json` |
| Acceptance of the notice | `~/.death-proof/disclaimer.json` |
| Logbook | a folder of your choice with `death-proof.db` and a `belege/` folder for receipts |

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
