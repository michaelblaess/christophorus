# Angleich an jira-timesheet (September 2026)

death-proof und jira-timesheet teilen denselben Unterbau (textual-widgets,
textual-themes, i18n, Einstellungsdialog). Bis zum Theme Hercules (textual-themes
v0.14.0) liefen beide gleich, danach kamen in jira-timesheet 19 Commits dazu. Dieser
Plan hält fest, was davon nach death-proof gewandert ist.

Stand 14.09.2026: alle drei Punkte umgesetzt, je Punkt ein Commit.

## Übernommen

1. **Prüfungen** (jira-timesheet `b558adc`)
   - textual-widgets auf `b880b28` gehoben (enthält `textual_widgets.keymap`).
   - `mypy src` von 86 Fehlern auf 0. Dazu `types-openpyxl` als Dev-Abhängigkeit und
     ein Override für `textual_widgets.*`, das keinen `py.typed`-Marker liefert.
   - import-linter mit zwei Verträgen: Schichten `app > screens > widgets > services >
     models`, und der Kern (`services`, `models`) zieht weder Oberfläche noch Textual.
     Gegenprobe gemacht: ein Textual-Import in `services/formatting.py` bricht den
     zweiten Vertrag.
   - mypy und import-linter laufen in der CI, import-linter zusätzlich im pre-commit.
2. **Umschaltbare Tastenbelegung** (`beabcda`, `3166393`, `0a6aae2`, `1b9abc0`)
   - `keymap.py` mit Bestandsstil, F-Tasten-Stil und Vim-Navigation in allen vier
     Tabellen (`widgets/navigable_data_table.py`).
   - Übersicht auf `?`, Reiter "Tastatur" im Einstellungsdialog. Stil und Vim-Schalter
     liegen in `~/.death-proof/config.json` und gelten ab dem nächsten Start.
   - F1 Info, F2 Einstellungen, F4 Log, F5 Aktualisieren, F7 Neue Fahrt,
     F8 Plausibilität, F9 Blacklist, F10 Export. F3 und F6 bleiben frei, einen Filter
     und eine Detailansicht gibt es hier nicht.
   - Das Log zieht im F-Tasten-Stil von `l` auf F4 bzw. alt+l.
   - Die Hinweise auf V, S und N tragen jetzt den Platzhalter `{shortcut}`.
   - Aktionen umbenannt: `export_excel` heißt `export`, `refresh_view` heißt `refresh`,
     `show_info` heißt `show_about`. Die gemeinsame F-Tasten-Konvention greift nur über
     diese Namen.
3. **Export-Dialog mit Formatwahl** (`1224435`, `0ab7268`)
   - Speichern-Dialog (textual-fspicker) statt stiller Ablage neben der Datenbank. Das
     Format folgt der Endung: Excel (Vorgabe), JSON, Markdown.
   - Startverzeichnis der Reihe nach: letzter Export, Verzeichnis des Fahrtenbuchs,
     Schreibtisch, Heimatverzeichnis.
   - Markdown folgt dem Excel Zeile für Zeile, die gemeinsamen Zeilenregeln liegen in
     `services/export_rows.py`. JSON schreibt jede Fahrt mit allen Feldern.

## Nebenbei

- Die Tests lesen nicht mehr die echte `config.json`: `DEATH_PROOF_HOME` biegt das
  Konfigurationsverzeichnis um, `tests/conftest.py` setzt es für jeden Test.
- `holidays.Germany` durch `holidays.country_holidays("DE", ...)` ersetzt. Für 16 Länder
  und 21 Jahre wurden beide Varianten verglichen, das Ergebnis war identisch.

## Offen

- `models/fahrtenbuch.py` importiert `services/database.py` und verletzt damit die
  Schichtung. Im Vertrag steht die Kante als einzige erlaubte Ausnahme. Sauber wäre,
  `Fahrtenbuch` nach `services/` zu ziehen.
- `mypy src tests` meldet 11 Fehler, alle `unused-ignore` auf Pyright-Kommentaren
  (`reportPrivateUsage`) in den Bestandstests. Die CI prüft nur `src`.

## Nicht übernommen

- Bearbeiter-Spalte, Bearbeiter-Filter, F5 lädt den Stundenzettel, Ticket-Schlüssel
  aus Verweis-URLs: fachlich Jira.
- Zertifikatsprüfung und HTTP-Tests des Jira-Clients: death-proof spricht kein HTTP.
- Kalender-Fix im Liegezeit-Test: in death-proof hängt kein Test an `date.today()`.
