"""Fahrtenbuch TUI — Hauptanwendung."""

import contextlib
import re
from datetime import date, datetime
from pathlib import Path

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import ContentSwitcher, Footer, Header, RichLog, Tab, Tabs

from death_proof import __version__, __year__
from death_proof.models.fahrtenbuch import Fahrtenbuch
from death_proof.models.settings import GlobalConfig
from death_proof.models.trip import (
    Trip,
    set_business_categories,
    set_informational_categories,
)
from death_proof.models.vehicle import Vehicle
from death_proof.services.database import Database
from death_proof.services.formatting import format_km
from death_proof.services.holiday_service import HolidayService
from death_proof.widgets.blacklist_view import BlacklistView
from death_proof.widgets.calendar_view import CalendarView
from death_proof.widgets.config_panel import ConfigPanel
from death_proof.widgets.documents_view import DocumentsView
from death_proof.widgets.summary_panel import SummaryPanel
from death_proof.widgets.trip_table import TripTable
from death_proof.widgets.worktimes_view import WorktimesView
from death_proof.widgets.year_view import YearView

_MARKUP_RE = re.compile(r"\[/?[^\]]*\]")


def _strip_markup(text: str) -> str:
    """Entfernt Rich/Textual-Markup-Tags fuer Plaintext-Ausgabe."""
    return _MARKUP_RE.sub("", text)


class FahrtenbuchApp(App):
    """Fahrtenbuch TUI fuer Finanzamt-konforme Fahrtenbuecher."""

    CSS_PATH = "app.tcss"
    TITLE = f"Death Proof v{__version__} ({__year__})"

    BINDINGS = [
        Binding("q,Q", "quit", "Beenden", key_display="q"),
        Binding("n,N", "new_trip", "Neue Fahrt", key_display="n"),
        Binding("d,D", "delete_trip", "Loeschen", key_display="d"),
        Binding("e,E", "export_excel", "Excel", key_display="e"),
        Binding("s,S", "show_settings", "Settings", key_display="s"),
        Binding("v,V", "open_fahrtenbuch", "Verwalten", key_display="v"),
        Binding("b,B", "toggle_blacklist", "Blacklist", key_display="b"),
        Binding("comma", "prev_month", "Monat", key_display="<"),
        Binding("full_stop", "next_month", "Monat", key_display=">"),
        Binding("f5", "refresh_view", "Aktualisieren"),
        Binding("p,P", "check_plausibility", "Plausibilitaet", key_display="p"),
        Binding("r,R", "rebuild_km", "km reparieren", key_display="r"),
        Binding("l,L", "toggle_log", "Log", key_display="l"),
        Binding("plus", "log_bigger", "Log +", key_display="+"),
        Binding("minus", "log_smaller", "Log -", key_display="-"),
        Binding("c,C", "copy_log", "Log kopieren", key_display="c"),
        Binding("ctrl+l", "clear_log", "Log leeren"),
        Binding("i,I", "show_info", "Info", key_display="i"),
    ]

    def __init__(self, year_override: int | None = None, **kwargs: object) -> None:
        super().__init__(**kwargs)
        self._config = GlobalConfig.load()

        try:
            from textual_themes import register_all

            register_all(self)
        except ImportError:
            pass

        self.theme = self._config.theme

        self._year = year_override or date.today().year
        self._month = date.today().month
        self._year_override = year_override
        self._current_view = "list"  # "list" | "calendar" | "year" | "blacklist"
        self._fahrtenbuch: Fahrtenbuch | None = None
        self._selected_trip_index: int = -1
        self._selected_trip_id: int = 0
        self._holiday_service = HolidayService("BB")  # Brandenburg
        self._log_lines: list[str] = []
        self._log_file_map: dict[int, Path] = {}
        self._log_file_counter: int = 0
        # Plausi-Zustand: trip_ids mit Problemen + Monats-Stats fuer Markierung
        self._problem_trip_ids: set[int] = set()
        self._problem_months: dict[int, int] = {}  # month -> count (nur aktuelles Jahr)
        self._log_height: int = 10

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
            Tab("Liste (Monat)", id="tab-list"),
            Tab("Liste (Jahr)", id="tab-list-year"),
            Tab("Kalender", id="tab-calendar"),
            Tab("Jahr", id="tab-year"),
            Tab("Blacklist", id="tab-blacklist"),
            Tab("Belege", id="tab-documents"),
            Tab("Arbeitszeit", id="tab-worktimes"),
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
        yield SummaryPanel(id="summary-panel")
        yield RichLog(id="log-panel", highlight=True, markup=True)
        yield Footer()

    def on_mount(self) -> None:
        """Wird nach dem Starten aufgerufen."""
        if not self._config.log_visible:
            self.query_one("#log-panel").add_class("hidden")

        self._write_log(f"Death Proof v{__version__} gestartet")

        # Versuche zuletzt geoeffnetes Fahrtenbuch zu oeffnen
        last_path = self._config.last_opened_path
        if last_path and Path(last_path).exists():
            self._open_fahrtenbuch(last_path)
        else:
            self._show_start_screen()

    def _show_start_screen(self) -> None:
        """Zeigt den Start-Screen zum Oeffnen/Erstellen/Sichern eines Fahrtenbuchs."""
        from death_proof.screens.start_screen import StartScreen

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
        self._write_log(f"[green]Datenbank gesichert: {backup_path}[/green]")
        return backup_path

    def _on_start_screen_closed(self, result: tuple[str, str | None] | None) -> None:
        """Callback nach dem StartScreen.

        result ist None bei Abbruch, sonst (ziel_pfad, clone_source_oder_None).
        """
        if result is None:
            if self._fahrtenbuch is None:
                self._write_log("[yellow]Kein Fahrtenbuch geoeffnet. Druecke [V] zum Verwalten.[/yellow]")
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
                self._write_log(f"Fahrtenbuch geoeffnet: {path}")
            else:
                # Neues Fahrtenbuch anlegen — Fahrzeug wird spaeter ueber Settings konfiguriert
                self._fahrtenbuch = Fahrtenbuch.create(path, Vehicle())
                self._write_log(f"[green]Neues Fahrtenbuch erstellt: {path}[/green]")
                if clone_source is not None:
                    try:
                        self._fahrtenbuch.database.clone_settings_from(Path(clone_source))
                        self._write_log(f"[green]Einstellungen uebernommen aus: {clone_source}[/green]")
                    except Exception as exc:
                        self._write_log(f"[red]Clone fehlgeschlagen: {exc}[/red]")
                        self.notify(f"Clone fehlgeschlagen: {exc}", severity="error")
                self._write_log("[yellow]Druecke [S] um das Fahrzeug zu konfigurieren.[/yellow]")
        except Exception as exc:
            self._write_log(f"[red]Fehler beim Oeffnen: {exc}[/red]")
            self.notify(f"Fehler: {exc}", severity="error")
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
        config_panel.update_vehicle(vehicle, path_str)
        config_panel.update_month(self._year, self._month)

        if vehicle and vehicle.name:
            self._write_log(f"Fahrzeug: {vehicle.name} ({vehicle.plate})")

        self._refresh_data()

    def _apply_show_id_setting(self) -> None:
        """Liest die ID-Spalten-Einstellung aus der DB und wendet sie auf
        alle Tabellen-Widgets an.
        """
        if self._fahrtenbuch is None:
            return
        db = self._fahrtenbuch.database
        show_id = db.get_setting("show_id_column", "0") == "1"
        for widget_id, cls in (
            ("#trip-table", TripTable),
            ("#trip-table-year", TripTable),
            ("#blacklist-view", BlacklistView),
            ("#documents-view", DocumentsView),
        ):
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
        lease_km = 1500
        vehicle = self._fahrtenbuch.vehicle
        if vehicle:
            lease_km = vehicle.lease_km_per_month

        holidays_map = self._holiday_service.get_holidays_in_month(self._year, self._month)

        category_colors = db.get_category_colors()

        # Blacklist laden (fuer Kalenderansicht und Blacklist-Tab)
        blacklist_entries = db.get_blacklist()
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
                    f"[bold red]WARNUNG: Geschaeftliche Fahrt am Feiertag "
                    f"{d.strftime('%d.%m.%Y')} ({holiday_name}): "
                    f"{trip.purpose}[/bold red]"
                )
                warnings += 1
            elif d.weekday() >= 5:
                self._write_log(
                    f"[bold red]WARNUNG: Geschaeftliche Fahrt am Wochenende "
                    f"{d.strftime('%d.%m.%Y')}: {trip.purpose}[/bold red]"
                )
                warnings += 1

        self._write_log(
            f"Daten geladen: {len(month_data.trips)} Fahrten, "
            f"{format_km(month_data.km_total)} km gesamt"
            + (f", [bold red]{warnings} Warnungen[/bold red]" if warnings else "")
        )

    def _write_log(self, message: str) -> None:
        """Schreibt eine Nachricht ins Log mit Zeitstempel."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        log = self.query_one("#log-panel", RichLog)
        log.write(f"[dim]{timestamp}[/dim] {message}")
        # Plain-Text-Fassung fuer "Log kopieren" mithalten
        self._log_lines.append(f"{timestamp} {_strip_markup(message)}")

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
            log = self.query_one("#log-panel", RichLog)
            log.styles.height = self._log_height
        except Exception:
            pass

    def action_copy_log(self) -> None:
        """Kopiert den gesamten Log-Inhalt in die Zwischenablage."""
        if not self._log_lines:
            self.notify("Log ist leer", severity="warning")
            return
        text = "\n".join(self._log_lines)
        self.copy_to_clipboard(text)
        self.notify(
            f"{len(self._log_lines)} Log-Zeilen kopiert",
            severity="information",
        )

    def action_clear_log(self) -> None:
        """Leert das Log-Fenster und den internen Puffer."""
        try:
            log = self.query_one("#log-panel", RichLog)
            log.clear()
        except Exception:
            pass
        self._log_lines.clear()
        self._write_log("Log geleert")

    def action_open_log_file(self, file_id: int) -> None:
        """Oeffnet eine im Log registrierte Datei im Standard-Programm."""
        path = self._log_file_map.get(file_id)
        if path is None:
            self.notify("Datei nicht mehr verfuegbar", severity="warning")
            return
        from death_proof.services.os_utils import open_file_in_system

        try:
            open_file_in_system(path)
        except FileNotFoundError:
            self.notify(f"Datei nicht gefunden: {path}", severity="error")
        except Exception as exc:
            self.notify(f"Konnte Datei nicht oeffnen: {exc}", severity="error")

    def _register_log_file(self, path: Path) -> int:
        """Registriert eine Datei fuer klickbare Log-Links und gibt die ID zurueck."""
        self._log_file_counter += 1
        file_id = self._log_file_counter
        self._log_file_map[file_id] = path
        return file_id

    def action_quit(self) -> None:
        """Speichert den aktuellen Monat und beendet die App."""
        if self._fahrtenbuch is not None and self._fahrtenbuch.is_open:
            db = self._fahrtenbuch.database
            db.set_setting("last_viewed_year", str(self._year))
            db.set_setting("last_viewed_month", str(self._month))
        self.exit()

    def watch_theme(self, theme_name: str) -> None:
        """Speichert das Theme bei Aenderung persistent."""
        self._config.theme = theme_name
        self._config.save()

    def on_config_panel_month_changed(self, event: ConfigPanel.MonthChanged) -> None:
        """Reagiert auf Monatswechsel."""
        self._year = event.year
        self._month = event.month
        self._refresh_data()

    def on_trip_table_trip_selected(self, event: TripTable.TripSelected) -> None:
        """Reagiert auf Auswahl einer Fahrt — oeffnet den Editor."""
        if event.trip is None or self._fahrtenbuch is None:
            return
        self._selected_trip_index = event.index
        self._selected_trip_id = event.trip.id

        from death_proof.screens.trip_screen import TripScreen

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
        if self._fahrtenbuch is None:
            return
        self._selected_trip_id = event.trip.id
        self._selected_trip_index = -1
        from death_proof.screens.trip_screen import TripScreen

        self.push_screen(
            TripScreen(
                database=self._fahrtenbuch.database,
                trip=event.trip,
            ),
            callback=self._on_trip_edited,
        )

    def on_calendar_view_new_trip_requested(self, event: CalendarView.NewTripRequested) -> None:
        """Oeffnet den TripScreen fuer eine neue Fahrt am angeklickten Tag."""
        if self._fahrtenbuch is None:
            return
        from death_proof.screens.trip_screen import TripScreen

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
        from death_proof.screens.trip_screen import DELETE_REQUESTED

        if trip is DELETE_REQUESTED:
            self.action_delete_trip()
            return
        if trip is None or self._fahrtenbuch is None:
            return
        # Trip hat eine ID — direkt in der DB aktualisieren
        if trip.id > 0:
            try:
                self._fahrtenbuch.database.update_trip(trip.id, trip)
            except ValueError as exc:
                self._write_log(f"[red]Aktualisierung abgelehnt: {exc}[/red]")
                self.notify(f"Aktualisierung abgelehnt: {exc}", severity="error")
                return
            except Exception as exc:
                self._write_log(f"[red]Fehler beim Aktualisieren: {exc}[/red]")
                self.notify(f"Fehler: {exc}", severity="error")
                return
        self._write_log(f"[green]Fahrt aktualisiert: {trip.date} — {trip.purpose}[/green]")
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
        if self._fahrtenbuch is None:
            return
        from death_proof.screens.blacklist_detail_screen import BlacklistDetailScreen

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
        self._write_log("[green]Blacklist aktualisiert[/green]")
        self._refresh_data()
        if self._current_view == "tab-list-year":
            self._refresh_year_trip_table()

    def action_delete_trip(self) -> None:
        """Loescht die ausgewaehlte Fahrt (funktioniert in Monats- und Jahresliste).

        Zeigt IMMER einen Confirm-Dialog mit Datum + Reisezweck, um versehent-
        liches Loeschen nach stale Selektionen (z.B. Kalender -> Edit -> d)
        zu verhindern.
        """
        if self._fahrtenbuch is None or self._selected_trip_id <= 0:
            self.notify("Keine Fahrt ausgewaehlt", severity="warning")
            return

        db = self._fahrtenbuch.database
        # Trip anhand der ID finden (Monat oder Jahr — egal welche Liste aktiv ist)
        trip = db.get_trip_by_id(self._selected_trip_id)
        if trip is None:
            self.notify("Fahrt nicht gefunden", severity="warning")
            return

        from death_proof.screens.confirm_screen import ConfirmScreen

        # Datum deutsch formatieren
        date_de = trip.date
        try:
            parts = trip.date.split("-")
            if len(parts) == 3:
                date_de = f"{parts[2]}.{parts[1]}.{parts[0]}"
        except (ValueError, IndexError):
            pass

        purpose = trip.purpose.strip() or "(kein Reisezweck)"
        destination = trip.destination.split("\n")[0].strip() if trip.destination else ""
        trip_label = f"{date_de}\n{purpose}\nZiel: {destination}" if destination else f"{date_de}\n{purpose}"

        documents = db.get_documents(trip_id=trip.id)
        if documents:
            count = len(documents)
            beleg_word = "Beleg" if count == 1 else "Belege"
            message = (
                f"Folgende Fahrt wirklich loeschen?\n\n"
                f"{trip_label}\n\n"
                f"[yellow]Die Fahrt hat {count} verknuepfte{'n' if count == 1 else ''} "
                f"{beleg_word} — Beleg-Eintraege werden mitentfernt, "
                f"die Dateien auf der Platte bleiben.[/yellow]"
            )
            title = "Fahrt mit Belegen loeschen?"
        else:
            message = f"Folgende Fahrt wirklich loeschen?\n\n{trip_label}"
            title = "Fahrt loeschen?"

        self.push_screen(
            ConfirmScreen(
                title=title,
                message=message,
                confirm_label="Loeschen",
            ),
            callback=lambda confirmed: self._finalize_delete_trip(trip.id, bool(confirmed)),
        )

    def _finalize_delete_trip(self, trip_id: int, confirmed: bool) -> None:
        """Callback nach dem Bestaetigungsdialog."""
        if not confirmed:
            self.notify("Loeschen abgebrochen", severity="information")
            return
        self._do_delete_trip(trip_id)

    def _do_delete_trip(self, trip_id: int) -> None:
        """Fuehrt das eigentliche Loeschen aus."""
        if self._fahrtenbuch is None:
            return
        db = self._fahrtenbuch.database
        trip = db.get_trip_by_id(trip_id)
        if trip is None:
            self.notify("Fahrt nicht mehr vorhanden", severity="warning")
            return
        db.delete_trip(trip.id)
        self._write_log(f"[red]Fahrt geloescht: {trip.date} — {trip.purpose}[/red]")
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
            self.notify("Kein Fahrtenbuch geoeffnet", severity="warning")
            return

        trip_table = self.query_one("#trip-table", TripTable)
        trip_table_year = self.query_one("#trip-table-year", TripTable)
        calendar_view = self.query_one("#calendar-view", CalendarView)
        is_on = trip_table.toggle_blacklist()
        trip_table_year.toggle_blacklist()
        calendar_view.toggle_blacklist()

        status = "[bold red]EIN[/bold red]" if is_on else "[dim]AUS[/dim]"
        self._write_log(f"Blacklist-Anzeige: {status}")
        self.notify(
            f"Blacklist {'aktiv' if is_on else 'deaktiviert'}",
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

        # Feiertage fuers ganze Jahr sammeln
        holidays_map: dict[date, str] = {}
        for month in range(1, 13):
            holidays_map.update(self._holiday_service.get_holidays_in_month(self._year, month))

        category_colors = db.get_category_colors()

        blacklist_entries = db.get_blacklist()
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
        docs_view = self.query_one("#documents-view", DocumentsView)
        docs_view.load_data(docs, Path(db.path))

    def on_documents_view_document_opened(
        self,
        event: "DocumentsView.DocumentOpened",
    ) -> None:
        """Oeffnet den angeklickten Beleg im Standard-Programm."""
        from death_proof.services.os_utils import open_file_in_system

        try:
            open_file_in_system(event.path)
        except FileNotFoundError:
            self.notify(f"Datei nicht gefunden: {event.path}", severity="error")
            self._write_log(f"[red]Datei nicht gefunden: {event.path}[/red]")
        except Exception as exc:
            self.notify(f"Konnte Datei nicht oeffnen: {exc}", severity="error")
            self._write_log(f"[red]Fehler beim Oeffnen: {exc}[/red]")

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
            f"[green]Arbeitszeit gespeichert: {event.month:02d}/{event.year} — {event.hours:.1f} Std[/green]"
        )

    def action_toggle_log(self) -> None:
        """Blendet das Log-Panel ein/aus."""
        log = self.query_one("#log-panel")
        log.toggle_class("hidden")
        self._config.log_visible = not log.has_class("hidden")
        self._config.save()

    def action_new_trip(self) -> None:
        """Oeffnet den Dialog fuer eine neue Fahrt bzw. einen neuen Blacklist-Eintrag.

        Kontextabhaengig: auf dem Blacklist-Tab wird statt des Trip-Dialogs
        der Blacklist-Detail-Screen im Neu-Modus geoeffnet.
        """
        if self._fahrtenbuch is None:
            self.notify("Kein Fahrtenbuch geoeffnet", severity="warning")
            return

        if self._current_view == "tab-blacklist":
            self._open_new_blacklist_entry()
            return

        from death_proof.screens.trip_screen import TripScreen

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
        from death_proof.screens.blacklist_detail_screen import BlacklistDetailScreen

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
            self._write_log(f"[red]Anlegen abgelehnt: {exc}[/red]")
            self.notify(f"Anlegen abgelehnt: {exc}", severity="error")
            return
        except Exception as exc:
            self._write_log(f"[red]Fehler beim Anlegen: {exc}[/red]")
            self.notify(f"Fehler: {exc}", severity="error")
            return
        self._write_log(f"[green]Fahrt angelegt: {trip.date} — {trip.purpose}[/green]")
        self._refresh_data()
        if self._current_view == "tab-list-year":
            self._refresh_year_trip_table()

    def action_export_excel(self) -> None:
        """Exportiert die aktuelle Liste (Monat oder Jahr) als Excel-Datei."""
        if self._fahrtenbuch is None or not self._fahrtenbuch.is_open:
            self.notify("Kein Fahrtenbuch geoeffnet", severity="warning")
            return

        db = self._fahrtenbuch.database
        vehicle = self._fahrtenbuch.vehicle

        from death_proof.services.excel_export import export_trips, month_name_de

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

        # Timestamp-Suffix vermeidet Permission-Denied, falls eine
        # vorherige Export-Datei noch in Excel offen ist.
        ts = datetime.now().strftime("%Y%m%d-%H%M%S")

        if is_year_export:
            trips = db.get_trips_for_year(self._year)
            # Optional Dezember des Vorjahrs vorn anhaengen, damit die
            # Steuerberaterin den Kettenstart sieht.
            if db.get_setting("export_include_prev_december", "0") == "1":
                prev_trips = db.get_trips_for_month(self._year - 1, 12)
                if prev_trips:
                    trips = prev_trips + trips
            subtitle = f"{self._year} — {lease_info}"
            filename = f"Fahrtenbuch {self._year}{plate_part} {ts}.xlsx"
            group_by_month = True
        else:
            trips = db.get_trips_for_month(self._year, self._month)
            month_label = f"{month_name_de(self._month)} {self._year}"
            subtitle = f"{month_label} — {lease_info}"
            filename = f"Fahrtenbuch {self._year}-{self._month:02d}{plate_part} {ts}.xlsx"
            group_by_month = False

        if not trips:
            self.notify("Keine Fahrten zum Exportieren", severity="warning")
            self._write_log("[yellow]Export abgebrochen: keine Fahrten[/yellow]")
            return

        # Anzeige-Labels der Kategorien fuer informationelle Trip-Zeilen
        category_labels = {code: label for label, code in db.get_category_options()}

        out_path = Path(db.path) / filename
        try:
            export_trips(
                trips=trips,
                out_path=out_path,
                title_line1=title_line1,
                subtitle=subtitle,
                group_by_month=group_by_month,
                category_labels=category_labels,
            )
        except Exception as exc:
            self._write_log(f"[red]Excel-Export fehlgeschlagen: {exc}[/red]")
            self.notify(f"Export-Fehler: {exc}", severity="error")
            return

        scope_label = "Jahr" if is_year_export else "Monat"
        file_id = self._register_log_file(out_path)
        self._write_log(
            f"[green]Excel-Export ({scope_label}) erfolgreich: "
            f"{len(trips)} Fahrten → "
            f"[@click=app.open_log_file({file_id})]{out_path.name}[/][/green]"
        )
        self.notify(f"Excel-Export gespeichert: {out_path.name}", severity="information")

    def action_show_settings(self) -> None:
        """Oeffnet die Einstellungen."""
        if self._fahrtenbuch is None:
            self.notify("Kein Fahrtenbuch geoeffnet", severity="warning")
            return

        from death_proof.screens.settings_screen import SettingsScreen

        self.push_screen(
            SettingsScreen(self._fahrtenbuch.database),
            callback=self._on_settings_closed,
        )

    def _on_settings_closed(self, changed: bool | None) -> None:
        """Callback nach dem SettingsScreen."""
        if not changed or self._fahrtenbuch is None:
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

        self._write_log("[green]Einstellungen gespeichert[/green]")

        if vehicle:
            self._write_log(f"Fahrzeug: {vehicle.name} ({vehicle.plate})")

        config_panel = self.query_one("#config-panel", ConfigPanel)
        config_panel.update_vehicle(vehicle, str(self._fahrtenbuch.path))
        self._apply_show_id_setting()
        self._refresh_data()

    def action_open_fahrtenbuch(self) -> None:
        """Oeffnet den Start-Screen zum Wechseln des Fahrtenbuchs."""
        self._show_start_screen()

    def action_show_year(self) -> None:
        """Wechselt direkt zur Jahresuebersicht."""
        tabs = self.query_one("#view-tabs", Tabs)
        tabs.active = "tab-year"

    def action_refresh_view(self) -> None:
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
        self.notify("Ansicht aktualisiert", severity="information")

    def action_check_plausibility(self) -> None:
        """Fuehrt die Plausibilitaetspruefung durch.

        Laedt alle Issues aus run_all_checks, schreibt sie ins Log und
        markiert die betroffenen Trip-IDs in Monats- und Jahreslisten rot.
        Erneutes Druecken nach Reparatur raeumt die Markierungen wieder ab,
        falls keine Probleme mehr gefunden werden.
        """
        if self._fahrtenbuch is None or not self._fahrtenbuch.is_open:
            self.notify("Kein Fahrtenbuch geoeffnet", severity="warning")
            return

        from death_proof.services.plausibility import (
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
            f"[bold]Plausibilitaetspruefung[/bold]: "
            f"[red]{report.error_count} Fehler[/red], "
            f"[yellow]{report.warning_count} Warnungen[/yellow], "
            f"[dim]{report.info_count} Hinweise[/dim]"
        )
        if not report.has_issues:
            self._write_log("[green]Alle Pruefungen ohne Befund — saubere Daten.[/green]")
            self.notify("Plausibilitaet: keine Probleme gefunden", severity="information")
        else:
            # Issues nach Severity, dann nach Datum ausgeben
            severity_order = {SEVERITY_ERROR: 0, SEVERITY_WARNING: 1}
            sorted_issues = sorted(
                report.issues,
                key=lambda i: (severity_order.get(i.severity, 9), i.trip_date, i.trip_id or 0),
            )
            for issue in sorted_issues:
                date_de = ""
                if issue.trip_date:
                    try:
                        parts = issue.trip_date.split("-")
                        date_de = f"{parts[2]}.{parts[1]}.{parts[0]}"
                    except IndexError:
                        date_de = issue.trip_date
                prefix = "[red]FEHLER[/red]" if issue.severity == SEVERITY_ERROR else "[yellow]WARNUNG[/yellow]"
                id_part = f"Trip #{issue.trip_id}" if issue.trip_id else "Global"
                self._write_log(f"  {prefix} {date_de} {id_part}: {issue.message}")
            self.notify(
                f"Plausibilitaet: {report.error_count} Fehler, {report.warning_count} Warnungen",
                severity="warning" if report.error_count == 0 else "error",
            )

        # Views mit neuen Problem-Markierungen neu laden
        self._refresh_data()
        self._refresh_year_view()
        self._refresh_year_trip_table()

    def action_rebuild_km(self) -> None:
        """Baut die km-Kette nach (Datum, Uhrzeit, id) neu auf.

        Die Distanzen (km_end - km_start) der einzelnen Trips bleiben erhalten;
        es werden nur km_start und km_end so zugewiesen, dass die Kette in
        chronologischer Reihenfolge (inkl. time_from innerhalb eines Tages)
        lueckenlos ist. Vorher wird per ConfirmScreen abgesichert.
        """
        if self._fahrtenbuch is None or not self._fahrtenbuch.is_open:
            self.notify("Kein Fahrtenbuch geoeffnet", severity="warning")
            return

        from death_proof.screens.confirm_screen import ConfirmScreen

        message = (
            "Die km-Kette wird nach Datum und Uhrzeit neu aufgebaut.\n\n"
            "Die Distanz jeder einzelnen Fahrt bleibt unveraendert — es werden "
            "nur km_Anfang und km_Ende so zugewiesen, dass die Kette lueckenlos "
            "in zeitlicher Reihenfolge ist.\n\n"
            "Diese Aktion kann nicht automatisch rueckgaengig gemacht werden."
        )
        self.push_screen(
            ConfirmScreen(
                title="km-Kette neu aufbauen?",
                message=message,
                confirm_label="Neu aufbauen",
            ),
            callback=lambda confirmed: self._finalize_rebuild_km(bool(confirmed)),
        )

    def _finalize_rebuild_km(self, confirmed: bool) -> None:
        """Callback nach dem Rebuild-Bestaetigungsdialog."""
        if not confirmed:
            self.notify("km-Rebuild abgebrochen", severity="information")
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
            self._write_log(f"[red]Rebuild fehlgeschlagen: {exc}[/red]")
            self.notify("Rebuild fehlgeschlagen", severity="error")
            return
        vehicle = self._fahrtenbuch.vehicle
        over_limit = vehicle.end_km > 0 and final_km > vehicle.end_km if vehicle else False
        self._write_log(f"[green]km-Kette neu aufgebaut: {changed} Fahrten, Endstand {final_km} km[/green]")
        if over_limit:
            self._write_log(
                f"[yellow]Hinweis: Endstand {final_km} km liegt ueber dem Vertragslimit {vehicle.end_km} km[/yellow]"
            )
        self.notify(
            f"{changed} Fahrten neu verkettet (Endstand {final_km} km)",
            severity="information",
        )
        self._refresh_data()
        self._refresh_year_view()
        self._refresh_year_trip_table()

    def action_show_info(self) -> None:
        """Zeigt den Info-Dialog."""
        from death_proof.screens.info_screen import InfoScreen

        self.push_screen(InfoScreen())

    def check_action(self, action: str, parameters: tuple) -> bool | None:  # type: ignore[override]
        """Blendet Aktionen aus wenn ModalScreen offen oder nicht verfuegbar."""
        # ModalScreen offen → alle App-Bindings deaktivieren
        if len(self.screen_stack) > 1:
            return None
        if action == "export_excel" and self._fahrtenbuch is None:
            return None
        if action == "rebuild_km" and self._fahrtenbuch is None:
            return None
        return True
