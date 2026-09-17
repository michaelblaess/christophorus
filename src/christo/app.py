"""Fahrtenbuch TUI — Hauptanwendung."""

import contextlib
import dataclasses
from datetime import date
from pathlib import Path
from typing import Any

from textual.app import App, ComposeResult
from textual.widgets import ContentSwitcher, Footer, Header, Tab, Tabs
from textual_widgets import (
    DISCLAIMER_VERSION,
    CrashGuard,
    DisclaimerScreen,
    DisclaimerStore,
    HorizontalSplitter,
    LogPanel,
    LogRouter,
)

from christo import __author__, __version__, __year__, keymap
from christo.i18n import current_language, month_name, t
from christo.models.export_job import ExportJob
from christo.models.settings import GlobalConfig, config_dir
from christo.models.trip import (
    Trip,
    set_business_categories,
    set_informational_categories,
)
from christo.models.vehicle import Vehicle
from christo.screens.keymap_screen import KeymapScreen
from christo.services.anonymizer import Anonymizer
from christo.services.database import Database
from christo.services.fahrtenbuch import Fahrtenbuch
from christo.services.formatting import format_km
from christo.services.holiday_service import HolidayService
from christo.widgets.blacklist_view import BlacklistView
from christo.widgets.calendar_view import CalendarView
from christo.widgets.config_panel import ConfigPanel
from christo.widgets.documents_view import DocumentsView
from christo.widgets.summary_panel import SummaryPanel
from christo.widgets.trip_table import TripTable
from christo.widgets.worktimes_view import WorktimesView
from christo.widgets.year_view import YearView


class FahrtenbuchApp(CrashGuard, LogRouter, App[None]):  # type: ignore[misc]
    """Fahrtenbuch als Terminal-Anwendung für geleaste und gekaufte Fahrzeuge."""

    CSS_PATH = "app.tcss"
    TITLE = f"Christophorus v{__version__} ({__year__})"

    # Kein class-level BINDINGS: welche Taste welche Aktion ausloest, haengt
    # am Stil aus der Konfiguration und wird in __init__ gebunden - siehe
    # _apply_keymap und christo.keymap.

    def __init__(self, year_override: int | None = None, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._config = GlobalConfig.load()
        # Zustimmung zum Haftungshinweis liegt neben der Konfiguration.
        self._disclaimer = DisclaimerStore(config_dir() / "disclaimer.json")
        # CrashGuard liest dieses Attribut fuer den Fehler-Dialog
        self.crash_guard_lang = current_language()

        try:
            from textual_themes import register_all

            register_all(self)
        except ImportError:
            pass

        # Ein Theme aus der Konfiguration kann verschwunden sein: die Bibliothek
        # wurde herabgestuft, das Theme umbenannt, oder es kam aus einer noch
        # nicht veroeffentlichten Fassung. Ohne diese Pruefung wirft Textual
        # InvalidThemeError und die Anwendung startet gar nicht mehr.
        self._verworfenes_theme = ""
        if self._config.theme in self.available_themes:
            self.theme = self._config.theme
        elif self._config.theme:
            self._verworfenes_theme = self._config.theme

        self._year = year_override or date.today().year
        self._month = date.today().month
        self._year_override = year_override
        self._current_view = "list"  # "list" | "calendar" | "year" | "blacklist"
        self._fahrtenbuch: Fahrtenbuch | None = None
        self._selected_trip_index: int = -1
        self._selected_trip_id: int = 0
        self._holiday_service = HolidayService("BB")  # Brandenburg
        self._log_file_map: dict[int, Path] = {}
        self._log_file_counter: int = 0
        # Plausi-Zustand: trip_ids mit Problemen + Monats-Stats fuer Markierung
        self._problem_trip_ids: set[int] = set()
        self._problem_months: dict[int, int] = {}  # month -> count (nur aktuelles Jahr)
        self._log_height: int = 10
        # Auftrag, der auf den Speichern-Dialog wartet. Zusammengestellt wird
        # er beim Oeffnen, damit der Dialog nur mit echten Fahrten aufgeht.
        self._pending_export: ExportJob | None = None
        # Anonymisierung fuer Screenshots. None heisst aus. Nur die Anzeige wird
        # verfremdet, Datenbank und Exporte bleiben echt.
        self._anonymizer: Anonymizer | None = None

        # Beanstandungen aus der Tastenbelegung. Sie gehoeren ins Log, nicht in
        # einen Dialog - sie betreffen die Konfigurationsdatei, nicht den
        # Vorgang. Beim Binden gibt es das LogPanel noch nicht, deshalb erst
        # in on_mount.
        self._keymap_problems: tuple[Any, ...] = ()
        self._keymap: dict[str, Any] = {}
        self._apply_keymap()

    def compose(self) -> ComposeResult:
        """Erstellt das UI-Layout."""
        yield Header()
        yield ConfigPanel(
            vehicle=None,
            year=self._year,
            month=self._month,
            fb_path="",
            id="config-panel",
        )
        yield Tabs(
            Tab(t("tab.list_month"), id="tab-list"),
            Tab(t("tab.list_year"), id="tab-list-year"),
            Tab(t("tab.calendar"), id="tab-calendar"),
            Tab(t("tab.year"), id="tab-year"),
            Tab(t("tab.blacklist"), id="tab-blacklist"),
            Tab(t("tab.documents"), id="tab-documents"),
            Tab(t("tab.worktimes"), id="tab-worktimes"),
            id="view-tabs",
        )
        with ContentSwitcher(initial="trip-table", id="view-switcher"):
            yield TripTable(id="trip-table")
            yield TripTable(id="trip-table-year")
            yield CalendarView(id="calendar-view")
            yield YearView(id="year-view")
            yield BlacklistView(id="blacklist-view")
            yield DocumentsView(id="documents-view")
            yield WorktimesView(id="worktimes-view")
        yield SummaryPanel(hint=t("summary.empty_hint", shortcut=self._key_hint("new_trip")), id="summary-panel")
        yield HorizontalSplitter(target_id="main", min_size=10, id="log-splitter")
        yield LogPanel(lang=current_language(), export_name="christophorus", id="log-panel")
        yield Footer()

    def on_mount(self) -> None:
        """Wird nach dem Starten aufgerufen."""
        if not self._config.log_visible:
            self.query_one("#log-panel").add_class("hidden")
            self.query_one("#log-splitter").add_class("hidden")

        self._write_log(t("log.app_started", version=__version__))
        self._log_theme()
        self._log_keymap_problems()

        # Versuche zuletzt geoeffnetes Fahrtenbuch zu oeffnen
        last_path = self._config.last_opened_path
        if last_path and Path(last_path).exists():
            self._open_fahrtenbuch(last_path)
        else:
            self._show_start_screen()

        # Zuletzt, damit der Hinweis ueber dem Start-Screen liegt.
        self._ask_disclaimer()

    def _ask_disclaimer(self) -> None:
        """Holt den Haftungshinweis ein, solange er in dieser Fassung nicht bestaetigt ist."""
        if self._disclaimer.accepted_version == DISCLAIMER_VERSION:
            return
        self.push_screen(
            DisclaimerScreen(
                app_name=f"Christophorus {__version__}",
                lang=current_language(),
                author=__author__,
                # Der Standardtext des Widgets beschreibt Scanner, die Last auf
                # fremden Servern erzeugen. Hier geht es um steuerliche
                # Anerkennung und personenbezogene Daten - daher eigener Wortlaut.
                title=t("disclaimer.title"),
                intro=t("disclaimer.intro"),
                duties=(
                    t("disclaimer.duty_entries"),
                    t("disclaimer.duty_personal_data"),
                    t("disclaimer.duty_backup"),
                ),
                footer=f"© {__year__} {__author__} · github.com/michaelblaess/christophorus",
            ),
            callback=self._on_disclaimer,
        )

    def _on_disclaimer(self, accepted: bool | None) -> None:
        """Ohne Zustimmung wird das Programm beendet - der Hinweis ist nicht optional."""
        if not accepted:
            self.exit()
            return
        self._disclaimer.record()

    @property
    def vim_navigation(self) -> bool:
        """Ob die Vim-Navigation in Tabellen aktiv ist.

        Die Tabellen fragen das beim Einhaengen ueber `self.app` ab, statt die
        Konfiguration selbst zu laden - so bleibt der Zustand an einer Stelle.
        """
        return bool(self._config.keymap_vim)

    def _key_hint(self, action: str) -> str:
        """Liefert die Taste einer Aktion, so wie sie in einer Meldung stehen soll.

        Meldungen wie "Druecke S um das Fahrzeug zu konfigurieren" duerfen die
        Taste nicht fest eingebaut haben - sie haengt am gewaehlten Stil und an
        den eigenen Belegungen.

        Args:
            action: Der Name der Aktion.

        Returns:
            Die erste Taste der Aktion in Footer-Schreibweise, einzelne
            Buchstaben gross. Leer, wenn die Aktion keine Taste hat - dann
            steht in der Meldung nichts statt einer falschen Taste.
        """
        binding = self._keymap.get(action)
        if binding is None:
            return ""
        taste = keymap.key_display(binding.keys[0])
        return taste.upper() if len(taste) == 1 else taste

    def _apply_keymap(self) -> None:
        """Bindet die Tasten der aktiven Belegung.

        Class-level ``BINDINGS`` scheiden aus zwei Gruenden aus: Sie koennen
        kein ``t()`` nutzen, und der Stil steht erst fest, wenn die
        Konfiguration geladen ist.
        """
        resolved = keymap.resolve(self._config)
        self._keymap_problems = tuple(resolved.problems)
        self._keymap = dict(resolved.bindings)
        # Stand beim Binden. Aendert er sich im Einstellungsdialog, gilt die
        # neue Belegung erst nach einem Neustart - das sagt das Log dann auch.
        self._keymap_signature: tuple[str, bool] = (self._config.keymap_style, self._config.keymap_vim)

        for action, binding in resolved.bindings.items():
            self._bindings.bind(
                ",".join(binding.keys),
                action,
                t(keymap.LABEL_KEYS.get(action, action)),
                key_display=keymap.key_display(binding.keys[0]),
                show=binding.show,
                priority=binding.priority,
            )
        self._apply_binding_tooltips()

    def _apply_binding_tooltips(self) -> None:
        """Ergaenzt jedes Binding um seinen lokalisierten Tooltip.

        ``BindingsMap.bind()`` akzeptiert kein ``tooltip``-Argument, also wird
        nachtraeglich ueber ``key_to_bindings`` iteriert und das Feld via
        ``dataclasses.replace`` ersetzt (``Binding`` ist frozen).
        """
        tooltips = {action: t(key) for action, key in keymap.TOOLTIP_KEYS.items()}
        for key, bindings_list in self._bindings.key_to_bindings.items():
            for i, binding in enumerate(bindings_list):
                tooltip = tooltips.get(binding.action)
                if tooltip:
                    self._bindings.key_to_bindings[key][i] = dataclasses.replace(binding, tooltip=tooltip)

    def action_keymap_overview(self) -> None:
        """Zeigt die aktuell geltende Tastenbelegung.

        Die Seite bekommt das fertige Ergebnis mit, nicht die Konfiguration -
        so zeigt sie zwangslaeufig das, was tatsaechlich gebunden ist.
        """
        self.push_screen(
            KeymapScreen(
                keymap.resolve(self._config),
                keymap.style_from_settings(self._config),
                self.vim_navigation,
            )
        )

    def _log_keymap_problems(self) -> None:
        """Meldet, was beim Zusammenbau der Tastenbelegung auffiel.

        Typische Faelle: eine eigene Belegung nennt eine Aktion, die es nicht
        gibt, oder die Vim-Navigation verdeckt eine Aktion der Anwendung. Beides
        waere sonst unsichtbar - die Taste tut dann einfach nichts.
        """
        for problem in self._keymap_problems:
            self._write_log(f"[!] {problem.message}", level="warning")

    def _show_start_screen(self) -> None:
        """Zeigt den Start-Screen zum Oeffnen/Erstellen/Sichern eines Fahrtenbuchs."""
        from christo.screens.start_screen import StartScreen

        current_path: str | None = None
        on_backup = None
        if self._fahrtenbuch is not None and self._fahrtenbuch.is_open:
            current_path = str(self._fahrtenbuch.path)
            on_backup = self._backup_current_db

        self.push_screen(
            StartScreen(
                self._config,
                current_path=current_path,
                on_backup=on_backup,
            ),
            callback=self._on_start_screen_closed,
        )

    def _backup_current_db(self) -> Path:
        """Sichert die aktuell geoeffnete Datenbank mit Timestamp."""
        if self._fahrtenbuch is None or not self._fahrtenbuch.is_open:
            raise RuntimeError("Kein Fahrtenbuch geoeffnet")
        backup_path = self._fahrtenbuch.database.backup_to_file()
        self._write_log(t("log.backup_done", path=backup_path), level="success")
        return backup_path

    def _on_start_screen_closed(self, result: tuple[str, str | None] | None) -> None:
        """Callback nach dem StartScreen.

        result ist None bei Abbruch, sonst (ziel_pfad, clone_source_oder_None).
        """
        if result is None:
            if self._fahrtenbuch is None:
                self._write_log(
                    t("log.fahrtenbuch_closed_hint", shortcut=self._key_hint("open_fahrtenbuch")),
                    level="warning",
                )
            return
        target_path, clone_source = result
        self._open_fahrtenbuch(target_path, clone_source=clone_source)

    def _open_fahrtenbuch(self, path_str: str, clone_source: str | None = None) -> None:
        """Oeffnet oder erstellt ein Fahrtenbuch am angegebenen Pfad.

        Wenn clone_source gesetzt ist und ein neues Fahrtenbuch angelegt
        wird, werden Einstellungen/Adressen/Kategorien/Blacklist/
        Arbeitszeit aus der Quelle uebernommen.
        """
        path = Path(path_str)

        # Altes Fahrtenbuch schliessen
        if self._fahrtenbuch is not None:
            self._fahrtenbuch.close()
            self._fahrtenbuch = None

        try:
            if Database.has_logbook(path):
                self._fahrtenbuch = Fahrtenbuch.open(path)
                self._write_log(t("log.fahrtenbuch_opened", path=path))
            else:
                # Neues Fahrtenbuch anlegen — Fahrzeug wird spaeter ueber Settings konfiguriert
                self._fahrtenbuch = Fahrtenbuch.create(path, Vehicle())
                self._write_log(t("log.fahrtenbuch_created", path=path), level="success")
                if clone_source is not None:
                    try:
                        self._fahrtenbuch.database.clone_settings_from(Path(clone_source))
                        self._write_log(t("log.clone_done", source=clone_source), level="success")
                    except Exception as exc:
                        self._write_log(t("log.clone_failed", error=exc), level="error")
                        self.notify(t("notify.clone_failed", error=exc), severity="error")
                self._write_log(
                    t("log.configure_vehicle_hint", shortcut=self._key_hint("show_settings")),
                    level="warning",
                )
        except Exception as exc:
            self._write_log(t("log.open_failed", error=exc), level="error")
            self.notify(t("notify.error_generic", error=exc), severity="error")
            return

        # GlobalConfig aktualisieren
        self._config.last_opened_path = path_str
        self._config.add_recent(path_str)
        self._config.save()

        # Monat bestimmen: gespeichert > erster Trip > heute
        db = self._fahrtenbuch.database
        if not self._year_override:
            saved_year = db.get_setting("last_viewed_year", "")
            saved_month = db.get_setting("last_viewed_month", "")
            if saved_year and saved_month:
                self._year = int(saved_year)
                self._month = int(saved_month)
            else:
                first = db.get_first_trip_date()
                if first:
                    self._year, self._month = first

        # Business-Kategorien aus DB laden
        set_business_categories(db.get_business_category_names())
        set_informational_categories(db.get_informational_category_names())

        # HolidayService mit gespeichertem Bundesland
        federal_state = db.get_setting("federal_state", "BB")
        self._holiday_service = HolidayService(federal_state)

        # ID-Spalte in Tabellen auf aktuellen Setting-Wert synchronisieren
        self._apply_show_id_setting()

        # UI aktualisieren
        vehicle = self._fahrtenbuch.vehicle
        config_panel = self.query_one("#config-panel", ConfigPanel)
        config_panel.update_vehicle(*self._display_vehicle(vehicle, path_str))
        config_panel.update_month(self._year, self._month)

        if vehicle and vehicle.name:
            self._write_log(t("log.vehicle_info", name=vehicle.name, plate=vehicle.plate))

        self._refresh_data()

    def _apply_show_id_setting(self) -> None:
        """Liest die ID-Spalten-Einstellung aus der DB und wendet sie auf
        alle Tabellen-Widgets an.
        """
        if self._fahrtenbuch is None:
            return
        db = self._fahrtenbuch.database
        show_id = db.get_setting("show_id_column", "0") == "1"
        show_id_widgets: tuple[tuple[str, type[TripTable | BlacklistView | DocumentsView]], ...] = (
            ("#trip-table", TripTable),
            ("#trip-table-year", TripTable),
            ("#blacklist-view", BlacklistView),
            ("#documents-view", DocumentsView),
        )
        for widget_id, cls in show_id_widgets:
            with contextlib.suppress(Exception):
                self.query_one(widget_id, cls).set_show_id(show_id)

        # Kategorie-Code- und Tankliter-Spalte (nur TripTable)
        show_code = db.get_setting("show_code_column", "0") == "1"
        show_fuel = db.get_setting("show_fuel_column", "0") == "1"
        category_codes = db.get_category_codes()
        for widget_id in ("#trip-table", "#trip-table-year"):
            try:
                tt = self.query_one(widget_id, TripTable)
                tt.set_category_codes(category_codes)
                tt.set_show_code(show_code)
                tt.set_show_fuel(show_fuel)
            except Exception:
                pass

    def _refresh_data(self) -> None:
        """Laedt und zeigt die Daten fuer den aktuellen Monat."""
        if self._fahrtenbuch is None or not self._fahrtenbuch.is_open:
            return

        db = self._fahrtenbuch.database
        month_data = db.get_month_data(self._year, self._month)
        if self._anonymizer is not None:
            month_data = self._anonymizer.month_data(month_data)
        lease_km = 1500
        vehicle = self._fahrtenbuch.vehicle
        if vehicle:
            lease_km = vehicle.lease_km_per_month

        holidays_map = self._holiday_service.get_holidays_in_month(self._year, self._month)

        category_colors = db.get_category_colors()

        # Blacklist laden (fuer Kalenderansicht und Blacklist-Tab)
        blacklist_entries = db.get_blacklist()
        if self._anonymizer is not None:
            blacklist_entries = self._anonymizer.blacklist_entries(blacklist_entries)
        blacklist_map: dict[date, str] = {}
        for entry in blacklist_entries:
            try:
                parts = str(entry.get("date", "")).split("-")
                d = date(int(parts[0]), int(parts[1]), int(parts[2]))
                blacklist_map[d] = str(entry.get("reason", ""))
            except (ValueError, IndexError):
                pass

        table = self.query_one("#trip-table", TripTable)
        table.load_data(month_data, holidays_map, category_colors, blacklist_map, blacklist_entries)
        table.set_problem_trip_ids(self._problem_trip_ids)

        calendar_view = self.query_one("#calendar-view", CalendarView)
        calendar_view.load_data(month_data, holidays_map, category_colors, blacklist_map)

        bl_view = self.query_one("#blacklist-view", BlacklistView)
        bl_view.load_data(blacklist_entries)

        summary = self.query_one("#summary-panel", SummaryPanel)
        summary.update_data(month_data, lease_km)

        # Warnungen nur fuer reine Business-Fahrten an Feiertagen/Wochenenden
        # (Tanken/Service/Geschaeftsessen duerfen auch am Wochenende stattfinden).
        warnings = 0
        for trip in month_data.trips:
            if trip.category != "business":
                continue
            if "geschaeftsessen" in trip.purpose.lower():
                continue
            try:
                parts = trip.date.split("-")
                d = date(int(parts[0]), int(parts[1]), int(parts[2]))
            except (ValueError, IndexError):
                continue
            holiday_name = holidays_map.get(d, "")
            if holiday_name:
                self._write_log(
                    t(
                        "log.warn_holiday",
                        date=d.strftime("%d.%m.%Y"),
                        holiday=holiday_name,
                        purpose=trip.purpose,
                    ),
                    level="error",
                )
                warnings += 1
            elif d.weekday() >= 5:
                self._write_log(
                    t(
                        "log.warn_weekend",
                        date=d.strftime("%d.%m.%Y"),
                        purpose=trip.purpose,
                    ),
                    level="error",
                )
                warnings += 1

        if warnings:
            self._write_log(
                t(
                    "log.data_loaded_with_warnings",
                    trips=len(month_data.trips),
                    km=format_km(month_data.km_total),
                    warnings=warnings,
                )
            )
        else:
            self._write_log(
                t(
                    "log.data_loaded",
                    trips=len(month_data.trips),
                    km=format_km(month_data.km_total),
                )
            )

    def _write_log(self, message: str, level: str = "info") -> None:
        """Schreibt eine Nachricht ins LogPanel."""
        if self._anonymizer is not None:
            message = self._anonymizer.censor(message)
        with contextlib.suppress(Exception):
            self.query_one("#log-panel", LogPanel).write_log(message, level=level)

    def action_log_bigger(self) -> None:
        """Vergroessert das Log-Fenster um 5 Zeilen (max 40)."""
        self._log_height = min(self._log_height + 5, 40)
        self._apply_log_height()

    def action_log_smaller(self) -> None:
        """Verkleinert das Log-Fenster um 5 Zeilen (min 3)."""
        self._log_height = max(self._log_height - 5, 3)
        self._apply_log_height()

    def _apply_log_height(self) -> None:
        """Setzt die aktuelle Log-Hoehe auf das Widget."""
        try:
            log = self.query_one("#log-panel", LogPanel)
            log.styles.height = self._log_height
        except Exception:
            pass

    def action_copy_log(self) -> None:
        """Kopiert den gesamten Log-Inhalt in die Zwischenablage."""
        try:
            self.query_one("#log-panel", LogPanel).copy_log()
        except Exception:
            self.notify(t("notify.log_empty"), severity="warning")

    def action_clear_log(self) -> None:
        """Leert das Log-Fenster."""
        with contextlib.suppress(Exception):
            self.query_one("#log-panel", LogPanel).clear_log()
        self._write_log(t("log.cleared"))

    def action_open_log_file(self, file_id: int) -> None:
        """Oeffnet eine im Log registrierte Datei im Standard-Programm."""
        path = self._log_file_map.get(file_id)
        if path is None:
            self.notify(t("notify.file_unavailable"), severity="warning")
            return
        from christo.services.os_utils import open_file_in_system

        try:
            open_file_in_system(path)
        except FileNotFoundError:
            self.notify(t("notify.file_not_found", path=path), severity="error")
        except Exception as exc:
            self.notify(t("notify.open_file_failed", error=exc), severity="error")

    def _register_log_file(self, path: Path) -> int:
        """Registriert eine Datei fuer klickbare Log-Links und gibt die ID zurueck."""
        self._log_file_counter += 1
        file_id = self._log_file_counter
        self._log_file_map[file_id] = path
        return file_id

    async def action_quit(self) -> None:
        """Speichert den aktuellen Monat und beendet die App."""
        if self._fahrtenbuch is not None and self._fahrtenbuch.is_open:
            db = self._fahrtenbuch.database
            db.set_setting("last_viewed_year", str(self._year))
            db.set_setting("last_viewed_month", str(self._month))
        self.exit()

    def watch_theme(self, theme_name: str) -> None:
        """Speichert das Theme bei Aenderung persistent und meldet es im Log."""
        if not hasattr(self, "_config"):
            return
        if self._config.theme == theme_name:
            return
        self._config.theme = theme_name
        self._config.save()
        self._log_theme()

    def _log_theme(self) -> None:
        """Schreibt das aktive Theme ins Log.

        Textual zeigt nirgends an, welches Theme gerade laeuft - nach einem
        Neustart weiss man also nicht, was man vor sich hat. Der technische
        Name steht mit dabei, weil er in den Einstellungen und in der
        Befehlspalette auftaucht.
        """
        with contextlib.suppress(Exception):
            from textual_themes import THEME_DISPLAY_NAMES

            name = self.theme or ""
            anzeige = THEME_DISPLAY_NAMES.get(name, name)
            beschriftung = f"{anzeige} ({name})" if anzeige != name else name
            self._write_log(t("log.theme_active", name=beschriftung))
            if self._verworfenes_theme:
                self._write_log(t("log.theme_unknown", name=self._verworfenes_theme), "warning")
                self._verworfenes_theme = ""

    def on_log_panel_hidden(self, event: LogPanel.Hidden) -> None:  # noqa: ARG002
        """LogPanel meldet Hide ueber Kontextmenue — Splitter mit ausblenden."""
        with contextlib.suppress(Exception):
            self.query_one("#log-splitter").add_class("hidden")
        self._config.log_visible = False
        self._config.save()

    def on_config_panel_month_changed(self, event: ConfigPanel.MonthChanged) -> None:
        """Reagiert auf Monatswechsel."""
        self._year = event.year
        self._month = event.month
        self._refresh_data()

    def on_trip_table_trip_selected(self, event: TripTable.TripSelected) -> None:
        """Reagiert auf Auswahl einer Fahrt — oeffnet den Editor."""
        if self._blocked_while_anonymized():
            return
        if event.trip is None or self._fahrtenbuch is None:
            return
        self._selected_trip_index = event.index
        self._selected_trip_id = event.trip.id

        from christo.screens.trip_screen import TripScreen

        self.push_screen(
            TripScreen(
                database=self._fahrtenbuch.database,
                trip=event.trip,
            ),
            callback=self._on_trip_edited,
        )

    def on_calendar_view_trip_edit_requested(self, event: CalendarView.TripEditRequested) -> None:
        """Oeffnet den TripScreen bei Klick auf eine Kalender-Kachel.

        WICHTIG: _selected_trip_id wird gesetzt, damit ein anschliessendes
        'd' die Kalender-Fahrt loescht und nicht eine stale Tabellen-Auswahl.
        """
        if self._blocked_while_anonymized():
            return
        if self._fahrtenbuch is None:
            return
        self._selected_trip_id = event.trip.id
        self._selected_trip_index = -1
        from christo.screens.trip_screen import TripScreen

        self.push_screen(
            TripScreen(
                database=self._fahrtenbuch.database,
                trip=event.trip,
            ),
            callback=self._on_trip_edited,
        )

    def on_calendar_view_new_trip_requested(self, event: CalendarView.NewTripRequested) -> None:
        """Oeffnet den TripScreen fuer eine neue Fahrt am angeklickten Tag."""
        if self._blocked_while_anonymized():
            return
        if self._fahrtenbuch is None:
            return
        from christo.screens.trip_screen import TripScreen

        db = self._fahrtenbuch.database
        last_km = db.get_last_km_end(self._year, self._month)
        default_date = event.day.strftime("%Y-%m-%d")

        self.push_screen(
            TripScreen(
                database=db,
                last_km_end=last_km,
                default_date=default_date,
            ),
            callback=self._on_trip_created,
        )

    def _on_trip_edited(self, trip: "Trip | None | object") -> None:
        """Callback nach dem Bearbeiten einer Fahrt."""
        # Loesch-Anforderung aus dem TripScreen → in den normalen
        # Loesch-Pfad mit Confirm-Alert umlenken.
        from christo.screens.trip_screen import DELETE_REQUESTED

        if trip is DELETE_REQUESTED:
            self.action_delete_trip()
            return
        if trip is None or self._fahrtenbuch is None:
            return
        assert isinstance(trip, Trip), f"Unerwartetes Ergebnis aus dem TripScreen: {trip!r}"
        # Trip hat eine ID — direkt in der DB aktualisieren
        if trip.id > 0:
            try:
                self._fahrtenbuch.database.update_trip(trip.id, trip)
            except ValueError as exc:
                self._write_log(t("log.trip_update_rejected", error=exc), level="error")
                self.notify(t("notify.update_rejected", error=exc), severity="error")
                return
            except Exception as exc:
                self._write_log(t("log.trip_update_failed", error=exc), level="error")
                self.notify(t("notify.update_failed", error=exc), severity="error")
                return
        self._write_log(t("log.trip_updated", date=trip.date, purpose=trip.purpose), level="success")
        self._refresh_data()
        if self._current_view == "tab-list-year":
            self._refresh_year_trip_table()

    def on_blacklist_view_entry_selected(self, event: "BlacklistView.EntrySelected") -> None:
        """Oeffnet Blacklist-Detail beim Auswaehlen eines Eintrags im Blacklist-Tab."""
        self._show_blacklist_detail(event.entry_id, event.date_str, event.reason)

    def on_trip_table_blacklist_entry_activated(self, event: "TripTable.BlacklistEntryActivated") -> None:
        """Oeffnet Blacklist-Detail beim Auswaehlen einer Blacklist-Zeile in der Liste."""
        self._show_blacklist_detail(event.entry_id, event.date_str, event.reason)

    def _show_blacklist_detail(self, entry_id: int, date_str: str, reason: str) -> None:
        """Oeffnet den Blacklist-Detail-Screen."""
        if self._blocked_while_anonymized():
            return
        if self._fahrtenbuch is None:
            return
        from christo.screens.blacklist_detail_screen import BlacklistDetailScreen

        self.push_screen(
            BlacklistDetailScreen(
                database=self._fahrtenbuch.database,
                entry_id=entry_id,
                date_str=date_str,
                reason=reason,
            ),
            callback=self._on_blacklist_detail_closed,
        )

    def _on_blacklist_detail_closed(self, changed: bool | None) -> None:
        """Callback nach dem BlacklistDetailScreen.

        Der Screen uebernimmt Speichern, Aktualisieren und Loeschen selbst per
        DB-Aufruf. Hier reicht es, bei Aenderungen die Ansichten neu zu laden.
        """
        if not changed or self._fahrtenbuch is None:
            return
        self._write_log(t("log.blacklist_updated"), level="success")
        self._refresh_data()
        if self._current_view == "tab-list-year":
            self._refresh_year_trip_table()

    def action_delete_trip(self) -> None:
        """Loescht die ausgewaehlte Fahrt (funktioniert in Monats- und Jahresliste).

        Zeigt IMMER einen Confirm-Dialog mit Datum + Reisezweck, um versehent-
        liches Loeschen nach stale Selektionen (z.B. Kalender -> Edit -> d)
        zu verhindern.
        """
        if self._blocked_while_anonymized():
            return
        if self._fahrtenbuch is None or self._selected_trip_id <= 0:
            self.notify(t("notify.no_trip_selected"), severity="warning")
            return

        db = self._fahrtenbuch.database
        # Trip anhand der ID finden (Monat oder Jahr — egal welche Liste aktiv ist)
        trip = db.get_trip_by_id(self._selected_trip_id)
        if trip is None:
            self.notify(t("notify.trip_not_found"), severity="warning")
            return

        from christo.screens.confirm_screen import ConfirmScreen

        # Datum deutsch formatieren
        date_de = trip.date
        try:
            parts = trip.date.split("-")
            if len(parts) == 3:
                date_de = f"{parts[2]}.{parts[1]}.{parts[0]}"
        except (ValueError, IndexError):
            pass

        purpose = trip.purpose.strip() or t("trip.no_purpose")
        destination = trip.destination.split("\n")[0].strip() if trip.destination else ""
        if destination:
            trip_label = f"{date_de}\n{purpose}\n{t('confirm.destination_prefix')} {destination}"
        else:
            trip_label = f"{date_de}\n{purpose}"

        documents = db.get_documents(trip_id=trip.id)
        if documents:
            count = len(documents)
            beleg_word = t("confirm.beleg_singular") if count == 1 else t("confirm.beleg_plural")
            linker = t("confirm.beleg_link_n") if count == 1 else t("confirm.beleg_link_")
            message = t(
                "confirm.delete_trip_with_docs_msg",
                label=trip_label,
                count=count,
                s=linker,
                word=beleg_word,
            )
            title = t("confirm.delete_trip_with_docs_title")
        else:
            message = t("confirm.delete_trip_msg", label=trip_label)
            title = t("confirm.delete_trip_title")

        self.push_screen(
            ConfirmScreen(
                title=title,
                message=message,
                confirm_label=t("confirm.confirm_label_delete"),
            ),
            callback=lambda confirmed: self._finalize_delete_trip(trip.id, bool(confirmed)),
        )

    def _finalize_delete_trip(self, trip_id: int, confirmed: bool) -> None:
        """Callback nach dem Bestaetigungsdialog."""
        if not confirmed:
            self.notify(t("notify.delete_cancelled"), severity="information")
            return
        self._do_delete_trip(trip_id)

    def _do_delete_trip(self, trip_id: int) -> None:
        """Fuehrt das eigentliche Loeschen aus."""
        if self._fahrtenbuch is None:
            return
        db = self._fahrtenbuch.database
        trip = db.get_trip_by_id(trip_id)
        if trip is None:
            self.notify(t("notify.trip_not_present"), severity="warning")
            return
        db.delete_trip(trip.id)
        self._write_log(t("log.trip_deleted", date=trip.date, purpose=trip.purpose), level="error")
        self._selected_trip_index = -1
        self._selected_trip_id = 0
        self._refresh_data()
        self._refresh_year_trip_table()

    def action_prev_month(self) -> None:
        """Wechselt zum vorherigen Monat."""
        config = self.query_one("#config-panel", ConfigPanel)
        config.prev_month()

    def action_next_month(self) -> None:
        """Wechselt zum naechsten Monat."""
        config = self.query_one("#config-panel", ConfigPanel)
        config.next_month()

    def on_tabs_tab_activated(self, event: Tabs.TabActivated) -> None:
        """Reagiert auf Tab-Wechsel. Laedt immer die Daten des Ziel-Views neu,
        damit keine View veraltete km-Staende nach einer Cascade-Aktualisierung
        anzeigt."""
        tab_map = {
            "tab-list": "trip-table",
            "tab-list-year": "trip-table-year",
            "tab-calendar": "calendar-view",
            "tab-year": "year-view",
            "tab-blacklist": "blacklist-view",
            "tab-documents": "documents-view",
            "tab-worktimes": "worktimes-view",
        }
        view_id = tab_map.get(event.tab.id or "", "trip-table")
        switcher = self.query_one("#view-switcher", ContentSwitcher)
        switcher.current = view_id
        self._current_view = event.tab.id or "tab-list"

        # SummaryPanel nur dort anzeigen, wo sie zur jeweiligen Ansicht passt
        # (Monats-/Jahres-Fahrtenliste, Kalender). Auf Jahr/Blacklist/Belege/
        # Arbeitszeit wuerde sie nur veraltete Monatsdaten zeigen.
        summary_panel = self.query_one("#summary-panel", SummaryPanel)
        if view_id in ("trip-table", "trip-table-year", "calendar-view"):
            summary_panel.remove_class("hidden")
        else:
            summary_panel.add_class("hidden")

        # Immer Monats-Daten neu laden (refresht Liste, Kalender, Blacklist,
        # Summary). Zusaetzlich die view-spezifischen Daten fuer Jahresliste,
        # Jahresview, Belege und Arbeitszeit.
        self._refresh_data()
        if view_id == "trip-table-year":
            self._refresh_year_trip_table()
        elif view_id == "year-view":
            self._refresh_year_view()
        elif view_id == "documents-view":
            self._refresh_documents_view()
        elif view_id == "worktimes-view":
            self._refresh_worktimes_view()

    def action_toggle_blacklist(self) -> None:
        """Schaltet Blacklist-Markierung in Liste und Kalender ein/aus."""
        if self._fahrtenbuch is None:
            self.notify(t("notify.no_fahrtenbuch"), severity="warning")
            return

        trip_table = self.query_one("#trip-table", TripTable)
        trip_table_year = self.query_one("#trip-table-year", TripTable)
        calendar_view = self.query_one("#calendar-view", CalendarView)
        is_on = trip_table.toggle_blacklist()
        trip_table_year.toggle_blacklist()
        calendar_view.toggle_blacklist()

        status_text = t("log.blacklist_on") if is_on else t("log.blacklist_off")
        status = f"[bold red]{status_text}[/bold red]" if is_on else f"[dim]{status_text}[/dim]"
        self._write_log(t("log.blacklist_status", status=status))
        self.notify(
            t("notify.blacklist_active") if is_on else t("notify.blacklist_inactive"),
            severity="information" if is_on else "warning",
        )

    def _refresh_year_view(self) -> None:
        """Laedt die Jahresdaten in die YearView."""
        if self._fahrtenbuch is None or not self._fahrtenbuch.is_open:
            return
        db = self._fahrtenbuch.database
        month_data = db.get_all_month_data(self._year)
        lease_km = 1500
        vehicle = self._fahrtenbuch.vehicle
        if vehicle:
            lease_km = vehicle.lease_km_per_month
        year_view = self.query_one("#year-view", YearView)
        year_view.load_data(self._year, month_data, lease_km, self._problem_months)

    def _refresh_year_trip_table(self) -> None:
        """Laedt alle Fahrten des Jahres in die Jahres-Liste."""
        if self._fahrtenbuch is None or not self._fahrtenbuch.is_open:
            return
        db = self._fahrtenbuch.database
        year_data = db.get_year_data(self._year)
        if self._anonymizer is not None:
            year_data = self._anonymizer.month_data(year_data)

        # Feiertage fuers ganze Jahr sammeln
        holidays_map: dict[date, str] = {}
        for month in range(1, 13):
            holidays_map.update(self._holiday_service.get_holidays_in_month(self._year, month))

        category_colors = db.get_category_colors()

        blacklist_entries = db.get_blacklist()
        if self._anonymizer is not None:
            blacklist_entries = self._anonymizer.blacklist_entries(blacklist_entries)
        blacklist_map: dict[date, str] = {}
        for entry in blacklist_entries:
            try:
                parts = str(entry.get("date", "")).split("-")
                d = date(int(parts[0]), int(parts[1]), int(parts[2]))
                blacklist_map[d] = str(entry.get("reason", ""))
            except (ValueError, IndexError):
                pass

        year_table = self.query_one("#trip-table-year", TripTable)
        year_table.load_data(
            year_data,
            holidays_map,
            category_colors,
            blacklist_map,
            blacklist_entries,
            year_mode=True,
        )
        year_table.set_problem_trip_ids(self._problem_trip_ids)

        # SummaryPanel mit Jahresdaten aktualisieren
        lease_km = 1500
        vehicle = self._fahrtenbuch.vehicle
        if vehicle:
            lease_km = vehicle.lease_km_per_month
        summary = self.query_one("#summary-panel", SummaryPanel)
        summary.update_data(year_data, lease_km * 12)

    def _refresh_documents_view(self) -> None:
        """Laedt alle Belege in die DocumentsView."""
        if self._fahrtenbuch is None or not self._fahrtenbuch.is_open:
            return
        db = self._fahrtenbuch.database
        docs = db.get_all_documents()
        if self._anonymizer is not None:
            docs = self._anonymizer.documents(docs)
        docs_view = self.query_one("#documents-view", DocumentsView)
        docs_view.load_data(docs, Path(db.path))

    def on_documents_view_document_opened(
        self,
        event: "DocumentsView.DocumentOpened",
    ) -> None:
        """Oeffnet den angeklickten Beleg im Standard-Programm."""
        from christo.services.os_utils import open_file_in_system

        try:
            open_file_in_system(event.path)
        except FileNotFoundError:
            self.notify(t("notify.file_not_found", path=event.path), severity="error")
            self._write_log(t("log.file_not_found", path=event.path), level="error")
        except Exception as exc:
            self.notify(t("notify.open_file_failed", error=exc), severity="error")
            self._write_log(t("log.open_file_failed", error=exc), level="error")

    def _refresh_worktimes_view(self) -> None:
        """Laedt die Arbeitsstunden in die WorktimesView."""
        if self._fahrtenbuch is None or not self._fahrtenbuch.is_open:
            return
        worktimes = self._fahrtenbuch.database.get_worktimes(self._year)
        wt_view = self.query_one("#worktimes-view", WorktimesView)
        wt_view.load_data(self._year, worktimes)

    def on_worktimes_view_worktime_changed(self, event: "WorktimesView.WorktimeChanged") -> None:
        """Speichert geaenderte Arbeitsstunden in der DB."""
        if self._fahrtenbuch is None:
            return
        self._fahrtenbuch.database.save_worktime(
            event.year,
            event.month,
            event.hours,
        )
        self._write_log(
            t("log.worktime_saved", month=event.month, year=event.year, hours=event.hours),
            level="success",
        )

    def action_toggle_log(self) -> None:
        """Blendet das Log-Panel ein/aus."""
        log = self.query_one("#log-panel")
        splitter = self.query_one("#log-splitter")
        log.toggle_class("hidden")
        splitter.toggle_class("hidden")
        self._config.log_visible = not log.has_class("hidden")
        self._config.save()

    def action_new_trip(self) -> None:
        """Oeffnet den Dialog fuer eine neue Fahrt bzw. einen neuen Blacklist-Eintrag.

        Kontextabhaengig: auf dem Blacklist-Tab wird statt des Trip-Dialogs
        der Blacklist-Detail-Screen im Neu-Modus geoeffnet.
        """
        if self._blocked_while_anonymized():
            return
        if self._fahrtenbuch is None:
            self.notify(t("notify.no_fahrtenbuch"), severity="warning")
            return

        if self._current_view == "tab-blacklist":
            self._open_new_blacklist_entry()
            return

        from christo.screens.trip_screen import TripScreen

        db = self._fahrtenbuch.database
        last_km = db.get_last_km_end(self._year, self._month)

        default_date = f"{self._year}-{self._month:02d}-"

        self.push_screen(
            TripScreen(
                database=db,
                last_km_end=last_km,
                default_date=default_date,
            ),
            callback=self._on_trip_created,
        )

    def _open_new_blacklist_entry(self) -> None:
        """Oeffnet den Blacklist-Detail-Screen im Neu-Modus."""
        if self._fahrtenbuch is None:
            return
        from christo.screens.blacklist_detail_screen import BlacklistDetailScreen

        # Voreinstellung: aktueller Monat, 1. Tag — hilft beim schnellen Eintragen
        default_iso = f"{self._year}-{self._month:02d}-01"
        self.push_screen(
            BlacklistDetailScreen(
                database=self._fahrtenbuch.database,
                entry_id=0,
                date_str=default_iso,
                reason="",
            ),
            callback=self._on_blacklist_detail_closed,
        )

    def _on_trip_created(self, trip: "Trip | None") -> None:
        """Callback nach dem TripScreen."""
        if trip is None or self._fahrtenbuch is None:
            return
        try:
            self._fahrtenbuch.database.add_trip(trip)
        except ValueError as exc:
            self._write_log(t("log.trip_create_rejected", error=exc), level="error")
            self.notify(t("notify.create_rejected", error=exc), severity="error")
            return
        except Exception as exc:
            self._write_log(t("log.trip_create_failed", error=exc), level="error")
            self.notify(t("notify.create_failed", error=exc), severity="error")
            return
        self._write_log(t("log.trip_created", date=trip.date, purpose=trip.purpose), level="success")
        self._refresh_data()
        if self._current_view == "tab-list-year":
            self._refresh_year_trip_table()

    def action_export(self) -> None:
        """Oeffnet den Speichern-Dialog fuer die aktuelle Liste (Monat oder Jahr).

        Das Format waehlt der Anwender im Dialog: Excel, JSON oder Markdown.
        Bis v1.2.1 schrieb die Taste ohne Rueckfrage eine Excel-Datei neben die
        Datenbank - das Verzeichnis des Fahrtenbuchs ist deshalb weiterhin der
        Startpunkt, solange noch kein Export woanders hin ging.
        """
        if self._blocked_while_anonymized():
            return
        from christo.models.export_format import DEFAULT_FORMAT, suggested_name
        from christo.screens.export_save_screen import ExportSaveScreen

        prepared = self._build_export_job()
        if prepared is None:
            return
        job, stem = prepared
        self._pending_export = job
        self.push_screen(
            ExportSaveScreen(
                location=self._save_dialog_location(),
                default_file=suggested_name(DEFAULT_FORMAT, stem),
                start_format=DEFAULT_FORMAT,
            ),
            callback=self._do_export,
        )

    def _save_dialog_location(self) -> str:
        """Das Verzeichnis, in dem der Speichern-Dialog aufgeht.

        Der Reihe nach: das zuletzt genutzte Ziel, das Verzeichnis des
        Fahrtenbuchs, der Schreibtisch, das Heimatverzeichnis. Geprueft wird
        jedes Mal, ob es den Pfad wirklich gibt - `textual_fspicker` geht bei
        einem nicht vorhandenen Startverzeichnis mit einem Fehlerbildschirm
        hoch. In jira-timesheet ist genau das auf dem Linux-Runner der CI
        passiert, wo es kein Verzeichnis "Desktop" gibt.

        Returns:
            Ein Verzeichnis, das existiert.
        """
        kandidaten = [self._config.last_export_dir]
        if self._fahrtenbuch is not None:
            kandidaten.append(str(self._fahrtenbuch.path))
        kandidaten += [str(Path.home() / "Desktop"), str(Path.home())]
        for kandidat in kandidaten:
            if kandidat and Path(kandidat).is_dir():
                return kandidat
        return str(Path.cwd())

    def _do_export(self, path: Path | None) -> None:
        """Schreibt den wartenden Auftrag im Format, das die Endung vorgibt.

        Args:
            path: Der im Dialog gewaehlte Pfad, oder None beim Abbrechen.
        """
        from christo.models.export_format import DEFAULT_FORMAT, format_for_path
        from christo.services.exporters import write_export

        job = self._pending_export
        self._pending_export = None
        if path is None or job is None:
            return

        export_format = format_for_path(path) or DEFAULT_FORMAT
        format_name = t(export_format.name_key)
        try:
            write_export(export_format, job, path)
        except Exception as exc:
            self._write_log(t("log.export_failed", format=format_name, error=exc), level="error")
            self.notify(t("notify.export_error", error=exc), severity="error")
            return

        self._config.last_export_dir = str(path.parent)
        self._config.save()

        scope_label = t("log.export_scope_year") if job.month is None else t("log.export_scope_month")
        file_id = self._register_log_file(path)
        header = t("log.export_ok", format=format_name, scope=scope_label, count=len(job.trips))
        self._write_log(
            f"{header}[@click=app.open_log_file({file_id})]{path.name}[/]",
            level="success",
        )
        self.notify(t("notify.export_saved", format=format_name, file=path.name), severity="information")

    def _build_export_job(self) -> tuple[ExportJob, str] | None:
        """Stellt zusammen, was exportiert wird, samt sprechendem Dateinamen.

        Returns:
            Auftrag und Namensstamm, oder None wenn es nichts zu exportieren
            gibt - der Hinweis dazu ist dann schon ausgegeben.
        """
        if self._fahrtenbuch is None or not self._fahrtenbuch.is_open:
            self.notify(t("notify.no_fahrtenbuch"), severity="warning")
            return None

        db = self._fahrtenbuch.database
        vehicle = self._fahrtenbuch.vehicle

        # Fahrzeug-Info fuer Titel
        if vehicle and vehicle.name and vehicle.plate:
            title_line1 = f"Fahrtenbuch {vehicle.name} ({vehicle.plate})"
            plate_part = f" ({vehicle.name} - {vehicle.plate})"
        elif vehicle and vehicle.name:
            title_line1 = f"Fahrtenbuch {vehicle.name}"
            plate_part = f" ({vehicle.name})"
        else:
            title_line1 = "Fahrtenbuch"
            plate_part = ""

        lease_km = vehicle.lease_km_per_month if vehicle else 1500
        lease_info = f"{format_km(lease_km)} km / Monat Leasing"

        # Aktuell aktiver Tab bestimmt den Export-Scope
        is_year_export = self._current_view == "tab-list-year"

        if is_year_export:
            trips = db.get_trips_for_year(self._year)
            # Optional Dezember des Vorjahrs vorn anhaengen, damit die
            # Steuerberaterin den Kettenstart sieht.
            if db.get_setting("export_include_prev_december", "0") == "1":
                prev_trips = db.get_trips_for_month(self._year - 1, 12)
                if prev_trips:
                    trips = prev_trips + trips
            subtitle = f"{self._year} — {lease_info}"
            stem = f"Fahrtenbuch {self._year}{plate_part}"
            group_by_month = True
        else:
            trips = db.get_trips_for_month(self._year, self._month)
            month_label = f"{month_name(self._month, lang='de')} {self._year}"
            subtitle = f"{month_label} — {lease_info}"
            stem = f"Fahrtenbuch {self._year}-{self._month:02d}{plate_part}"
            group_by_month = False

        if not trips:
            self.notify(t("notify.export_no_trips"), severity="warning")
            self._write_log(t("log.export_cancelled_no_trips"), level="warning")
            return None

        job = ExportJob(
            trips=trips,
            title=title_line1,
            subtitle=subtitle,
            year=self._year,
            month=None if is_year_export else self._month,
            group_by_month=group_by_month,
            # Anzeige-Labels der Kategorien fuer informationelle Trip-Zeilen
            category_labels={code: label for label, code in db.get_category_options()},
            vehicle_name=vehicle.name if vehicle else "",
            vehicle_plate=vehicle.plate if vehicle else "",
        )
        return job, stem

    def action_show_settings(self) -> None:
        """Oeffnet die Einstellungen."""
        if self._blocked_while_anonymized():
            return
        if self._fahrtenbuch is None:
            self.notify(t("notify.no_fahrtenbuch"), severity="warning")
            return

        from christo.screens.settings_screen import SettingsScreen

        self.push_screen(
            SettingsScreen(self._fahrtenbuch.database, self._config),
            callback=self._on_settings_closed,
        )

    def _on_settings_closed(self, result: dict[str, object] | None) -> None:
        """Callback nach dem SettingsScreen.

        ``BaseSettingsScreen`` liefert das geaenderte Settings-Dict (oder
        None bei Abbruch). Wir interessieren uns nur fuer "wurde gespeichert" —
        Adressen/Kategorien/Fahrzeug schreibt der Screen direkt in die DB.
        Die Sprache hat der Screen schon in GlobalConfig persistiert.
        """
        if result is None or self._fahrtenbuch is None:
            return

        # Fahrzeug-Daten und Bundesland aus DB neu laden
        db = self._fahrtenbuch.database
        self._fahrtenbuch._vehicle = db.get_vehicle()
        vehicle = self._fahrtenbuch.vehicle

        # Business-Kategorien aus DB neu laden
        set_business_categories(db.get_business_category_names())
        set_informational_categories(db.get_informational_category_names())

        federal_state = db.get_setting("federal_state", "BB")
        self._holiday_service = HolidayService(federal_state)

        self._write_log(t("log.settings_saved"), level="success")
        if (self._config.keymap_style, self._config.keymap_vim) != self._keymap_signature:
            self._write_log(t("log.keymap_changed"), level="warning")

        if vehicle:
            self._write_log(t("log.vehicle_info", name=vehicle.name, plate=vehicle.plate))

        config_panel = self.query_one("#config-panel", ConfigPanel)
        config_panel.update_vehicle(*self._display_vehicle(vehicle, str(self._fahrtenbuch.path)))
        self._apply_show_id_setting()
        self._refresh_data()

    def action_open_fahrtenbuch(self) -> None:
        """Oeffnet den Start-Screen zum Wechseln des Fahrtenbuchs."""
        if self._blocked_while_anonymized():
            return
        self._show_start_screen()

    def action_show_year(self) -> None:
        """Wechselt direkt zur Jahresuebersicht."""
        tabs = self.query_one("#view-tabs", Tabs)
        tabs.active = "tab-year"

    def action_toggle_anon(self) -> None:
        """Schaltet die Anonymisierung für Screenshots ein oder aus.

        Beim Einschalten wird das Log geleert, weil ältere Zeilen echte Namen
        tragen. Datenbank und Exporte bleiben unberührt.
        """
        if self._anonymizer is None:
            anonymizer = Anonymizer()
            self._prime_anonymizer(anonymizer)
            self._anonymizer = anonymizer
            with contextlib.suppress(Exception):
                self.query_one("#log-panel", LogPanel).clear_log()
            self.sub_title = t("subtitle.anonymized")
            self._write_log(t("log.anonymized_on"), level="warning")
            self.notify(t("notify.anonymized_on"))
        else:
            self._anonymizer = None
            self.sub_title = ""
            self._write_log(t("log.anonymized_off"))
            self.notify(t("notify.anonymized_off"))
        self._refresh_all_views()

    def _prime_anonymizer(self, anonymizer: Anonymizer) -> None:
        """Lässt den Anonymizer alle echten Werte einmal sehen.

        Erst danach kann censor() sie in freien Texten ersetzen - auch solche aus
        Monaten, die gerade nicht angezeigt werden (Prüfmeldungen, Log).
        """
        if self._fahrtenbuch is None or not self._fahrtenbuch.is_open:
            return
        db = self._fahrtenbuch.database
        anonymizer.vehicle(self._fahrtenbuch.vehicle)
        anonymizer.path(str(self._fahrtenbuch.path))
        for trip in db.get_all_trips_ordered():
            anonymizer.trip(trip)
        anonymizer.blacklist_entries(db.get_blacklist())
        anonymizer.documents(db.get_all_documents())

    def _display_vehicle(self, vehicle: Vehicle | None, path: str) -> tuple[Vehicle | None, str]:
        """Fahrzeug und Ordner so, wie sie angezeigt werden - im anonymen Modus verfremdet."""
        if self._anonymizer is None:
            return vehicle, path
        return self._anonymizer.vehicle(vehicle), self._anonymizer.path(path)

    def _blocked_while_anonymized(self) -> bool:
        """Sperrt Dialoge, die echte Daten zeigen oder verfremdete speichern würden."""
        if self._anonymizer is None:
            return False
        self.notify(t("notify.anonymized_blocked"), severity="warning")
        return True

    def _refresh_all_views(self) -> None:
        """Lädt alle Ansichten neu, die Daten oder Fahrzeug zeigen."""
        if self._fahrtenbuch is None or not self._fahrtenbuch.is_open:
            return
        config_panel = self.query_one("#config-panel", ConfigPanel)
        config_panel.update_vehicle(*self._display_vehicle(self._fahrtenbuch.vehicle, str(self._fahrtenbuch.path)))
        self._refresh_data()
        self._refresh_year_trip_table()
        self._refresh_year_view()
        self._refresh_documents_view()
        self._refresh_worktimes_view()
        if self._current_view != "tab-list-year":
            # Die Jahresliste setzt das SummaryPanel auf Jahreswerte - zurueck auf den Monat.
            self._refresh_data()

    def action_refresh(self) -> None:
        """Aktualisiert die aktuelle Ansicht (F5)."""
        self._refresh_data()
        view = self._current_view
        if view == "tab-list-year":
            self._refresh_year_trip_table()
        elif view == "tab-year":
            self._refresh_year_view()
        elif view == "tab-documents":
            self._refresh_documents_view()
        elif view == "tab-worktimes":
            self._refresh_worktimes_view()
        self.notify(t("notify.view_refreshed"), severity="information")

    def action_check_plausibility(self) -> None:
        """Fuehrt die Plausibilitaetspruefung durch."""
        if self._fahrtenbuch is None or not self._fahrtenbuch.is_open:
            self.notify(t("notify.no_fahrtenbuch"), severity="warning")
            return

        from christo.services.plausibility import (
            CAT_GHOST_BUSINESS_TRIP,
            SEVERITY_ERROR,
            SEVERITY_WARNING,
            run_all_checks,
        )

        db = self._fahrtenbuch.database
        holidays_map = self._holiday_service.get_holidays_in_year(self._year)
        skip: set[str] = set()
        if db.get_setting("check_ghost_trips", "0") != "1":
            skip.add(CAT_GHOST_BUSINESS_TRIP)
        report = run_all_checks(db, holidays_by_date=holidays_map, skip_checks=skip)

        # Problem-Trip-IDs fuer die Liste neu setzen
        new_problem_ids: set[int] = set()
        new_problem_months: dict[int, int] = {}
        for issue in report.issues:
            if issue.trip_id is not None and issue.trip_id > 0:
                new_problem_ids.add(issue.trip_id)
            if issue.year == self._year and issue.month is not None:
                new_problem_months[issue.month] = new_problem_months.get(issue.month, 0) + 1
        self._problem_trip_ids = new_problem_ids
        self._problem_months = new_problem_months

        self._write_log("")
        self._write_log(
            t(
                "log.plausi_header",
                errors=report.error_count,
                warnings=report.warning_count,
                infos=report.info_count,
            )
        )
        if not report.has_issues:
            self._write_log(t("log.plausi_clean"), level="success")
            self.notify(t("notify.plausi_ok"), severity="information")
        else:
            severity_order = {SEVERITY_ERROR: 0, SEVERITY_WARNING: 1}
            sorted_issues = sorted(
                report.issues,
                key=lambda i: (severity_order.get(i.severity, 9), i.trip_date, i.trip_id or 0),
            )
            err_label = t("log.plausi_severity_error")
            warn_label = t("log.plausi_severity_warning")
            for issue in sorted_issues:
                date_de = ""
                if issue.trip_date:
                    try:
                        parts = issue.trip_date.split("-")
                        date_de = f"{parts[2]}.{parts[1]}.{parts[0]}"
                    except IndexError:
                        date_de = issue.trip_date
                prefix = (
                    f"[red]{err_label}[/red]" if issue.severity == SEVERITY_ERROR else f"[yellow]{warn_label}[/yellow]"
                )
                id_part = t("log.plausi_trip", id=issue.trip_id) if issue.trip_id else t("log.plausi_global")
                self._write_log(f"  {prefix} {date_de} {id_part}: {issue.message}")
            self.notify(
                t("notify.plausi_summary", errors=report.error_count, warnings=report.warning_count),
                severity="warning" if report.error_count == 0 else "error",
            )

        self._refresh_data()
        self._refresh_year_view()
        self._refresh_year_trip_table()

    def action_rebuild_km(self) -> None:
        """Baut die km-Kette nach (Datum, Uhrzeit, id) neu auf."""
        if self._fahrtenbuch is None or not self._fahrtenbuch.is_open:
            self.notify(t("notify.no_fahrtenbuch"), severity="warning")
            return

        from christo.screens.confirm_screen import ConfirmScreen

        self.push_screen(
            ConfirmScreen(
                title=t("confirm.rebuild_title"),
                message=t("confirm.rebuild_msg"),
                confirm_label=t("confirm.rebuild_label"),
            ),
            callback=lambda confirmed: self._finalize_rebuild_km(bool(confirmed)),
        )

    def _finalize_rebuild_km(self, confirmed: bool) -> None:
        """Callback nach dem Rebuild-Bestaetigungsdialog."""
        if not confirmed:
            self.notify(t("notify.rebuild_cancelled"), severity="information")
            return
        if self._fahrtenbuch is None or not self._fahrtenbuch.is_open:
            return
        db = self._fahrtenbuch.database
        try:
            # force=True: Ueberschreitung des Vertragslimits blockiert den
            # Rebuild nicht mehr — die Ueber-Limit-Warnung uebernimmt der
            # Plausi-Check (check_vehicle_end_limit) separat.
            changed, final_km = db.rebuild_all_km(force=True)
        except Exception as exc:
            self._write_log(t("log.rebuild_failed", error=exc), level="error")
            self.notify(t("notify.rebuild_failed"), severity="error")
            return
        vehicle = self._fahrtenbuch.vehicle
        over_limit = vehicle.end_km > 0 and final_km > vehicle.end_km if vehicle else False
        self._write_log(t("log.rebuild_done", changed=changed, km=final_km), level="success")
        if over_limit:
            assert vehicle is not None, "over_limit setzt ein Fahrzeug voraus"
            self._write_log(
                t("log.rebuild_over_limit", km=final_km, limit=vehicle.end_km),
                level="warning",
            )
        self.notify(
            t("notify.rebuild_done", changed=changed, km=final_km),
            severity="information",
        )
        self._refresh_data()
        self._refresh_year_view()
        self._refresh_year_trip_table()

    def action_show_about(self) -> None:
        """Zeigt den Info-Dialog."""
        from christo.screens.info_screen import InfoScreen

        self.push_screen(InfoScreen())

    def action_cycle_theme(self) -> None:
        """Wechselt zum naechsten Theme (alphabetisch). Persistenz via watch_theme."""
        names = sorted(self.available_themes.keys())
        if not names:
            return
        try:
            idx = names.index(self.theme)
        except ValueError:
            idx = -1
        next_theme = names[(idx + 1) % len(names)]
        self.theme = next_theme
        try:
            from textual_themes import THEME_DISPLAY_NAMES

            display = THEME_DISPLAY_NAMES.get(next_theme, next_theme)
        except ImportError:
            display = next_theme
        self.notify(t("notify.theme_changed", name=display))

    def check_action(self, action: str, parameters: tuple[object, ...]) -> bool | None:
        """Blendet Aktionen aus wenn ModalScreen offen oder nicht verfuegbar."""
        # ModalScreen offen → alle App-Bindings deaktivieren
        if len(self.screen_stack) > 1:
            return None
        if action == "export" and self._fahrtenbuch is None:
            return None
        if action == "rebuild_km" and self._fahrtenbuch is None:
            return None
        return True
